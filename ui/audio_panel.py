"""
Audio Panel
Computer soundcard as radio mic/speaker interface
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel,
    QPushButton, QComboBox, QSlider, QProgressBar, QCheckBox,
    QDoubleSpinBox, QScrollArea, QFrame, QSizePolicy, QFileDialog,
    QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSlot, QTimer
from PyQt6.QtGui import QFont
from core.audio_engine import AudioEngine, AUDIO_AVAILABLE, SAMPLE_RATE
from core.cat817 import CAT817


class LevelMeter(QWidget):
    """Vertical VU meter widget."""
    def __init__(self, label="", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        lbl = QLabel(label)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("font-size: 9px; color: #888;")
        layout.addWidget(lbl)

        self.bar = QProgressBar()
        self.bar.setOrientation(Qt.Orientation.Vertical)
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.bar.setFixedWidth(28)
        self.bar.setMinimumHeight(120)
        layout.addWidget(self.bar, 1)

        self.peak_label = QLabel("0%")
        self.peak_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.peak_label.setStyleSheet("font-size: 9px; font-family: Consolas;")
        layout.addWidget(self.peak_label)

    def set_level(self, value: float):
        pct = int(min(100, value * 200))
        self.bar.setValue(pct)
        self.peak_label.setText(f"{pct}%")
        if pct > 90:
            self.bar.setStyleSheet("QProgressBar::chunk { background: #f85149; }")
        elif pct > 70:
            self.bar.setStyleSheet("QProgressBar::chunk { background: #d29922; }")
        else:
            self.bar.setStyleSheet("")


class AudioPanel(QWidget):
    def __init__(self, audio: AudioEngine, cat: CAT817, parent=None):
        super().__init__(parent)
        self.audio = audio
        self.cat   = cat
        self._build_ui()
        self._wire_signals()
        self._populate_devices()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)
        container = QWidget()
        scroll.setWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        if not AUDIO_AVAILABLE:
            warn = QLabel(
                "⚠  sounddevice not installed.\n\n"
                "Install with:\n  pip install sounddevice\n\nThen restart Yaesu FT-8XX Suite by K3LH."
            )
            warn.setStyleSheet("color: #d29922; font-size: 13px; padding: 20px;")
            warn.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(warn)
            return

        top_row = QHBoxLayout()
        layout.addLayout(top_row)

        # ── Device Selection ──────────────────────────────────────────────────
        dev_box = QGroupBox("AUDIO DEVICES")
        dev_layout = QGridLayout(dev_box)

        dev_layout.addWidget(QLabel("Input (Mic/RX):"),  0, 0)
        self.in_combo = QComboBox()
        self.in_combo.setMinimumWidth(220)
        dev_layout.addWidget(self.in_combo, 0, 1)

        dev_layout.addWidget(QLabel("Output (Speaker/TX):"), 1, 0)
        self.out_combo = QComboBox()
        self.out_combo.setMinimumWidth(220)
        dev_layout.addWidget(self.out_combo, 1, 1)

        btn_refresh = QPushButton("⟳ Refresh")
        btn_refresh.clicked.connect(self._populate_devices)
        dev_layout.addWidget(btn_refresh, 0, 2)

        self.btn_start = QPushButton("▶ START AUDIO")
        self.btn_start.setObjectName("btn_connect")
        self.btn_start.clicked.connect(self._toggle_audio)
        self.btn_start.setCheckable(True)
        dev_layout.addWidget(self.btn_start, 1, 2)

        top_row.addWidget(dev_box)

        # ── Level Meters ──────────────────────────────────────────────────────
        meter_box = QGroupBox("LEVELS")
        meter_layout = QHBoxLayout(meter_box)

        self.in_meter  = LevelMeter("IN")
        self.out_meter = LevelMeter("OUT")
        meter_layout.addWidget(self.in_meter)
        meter_layout.addWidget(self.out_meter)
        top_row.addWidget(meter_box)

        # ── Gain Controls ─────────────────────────────────────────────────────
        gain_box = QGroupBox("GAIN")
        gain_layout = QVBoxLayout(gain_box)

        in_gain_row = QHBoxLayout()
        in_gain_row.addWidget(QLabel("Input:"))
        self.in_gain_slider = QSlider(Qt.Orientation.Horizontal)
        self.in_gain_slider.setRange(0, 400)
        self.in_gain_slider.setValue(100)
        self.in_gain_slider.setToolTip("Input gain (100% = unity)")
        self.in_gain_slider.valueChanged.connect(
            lambda v: self.audio.set_input_gain(v / 100.0))
        self.in_gain_label = QLabel("100%")
        self.in_gain_label.setFixedWidth(40)
        self.in_gain_slider.valueChanged.connect(
            lambda v: self.in_gain_label.setText(f"{v}%"))
        in_gain_row.addWidget(self.in_gain_slider)
        in_gain_row.addWidget(self.in_gain_label)
        gain_layout.addLayout(in_gain_row)

        out_gain_row = QHBoxLayout()
        out_gain_row.addWidget(QLabel("Output:"))
        self.out_gain_slider = QSlider(Qt.Orientation.Horizontal)
        self.out_gain_slider.setRange(0, 400)
        self.out_gain_slider.setValue(100)
        self.out_gain_slider.setToolTip("Output gain (100% = unity)")
        self.out_gain_slider.valueChanged.connect(
            lambda v: self.audio.set_output_gain(v / 100.0))
        self.out_gain_label = QLabel("100%")
        self.out_gain_label.setFixedWidth(40)
        self.out_gain_slider.valueChanged.connect(
            lambda v: self.out_gain_label.setText(f"{v}%"))
        out_gain_row.addWidget(self.out_gain_slider)
        out_gain_row.addWidget(self.out_gain_label)
        gain_layout.addLayout(out_gain_row)

        top_row.addWidget(gain_box)

        # ── VOX ───────────────────────────────────────────────────────────────
        vox_box = QGroupBox("VOX  (Voice-Operated TX)")
        vox_layout = QVBoxLayout(vox_box)

        vox_en_row = QHBoxLayout()
        self.chk_vox = QCheckBox("Enable VOX")
        self.chk_vox.toggled.connect(self._toggle_vox)
        vox_en_row.addWidget(self.chk_vox)
        vox_layout.addLayout(vox_en_row)

        vox_thresh_row = QHBoxLayout()
        vox_thresh_row.addWidget(QLabel("Threshold:"))
        self.vox_thresh = QSlider(Qt.Orientation.Horizontal)
        self.vox_thresh.setRange(1, 100)
        self.vox_thresh.setValue(10)
        self.vox_thresh_label = QLabel("5%")
        self.vox_thresh_label.setFixedWidth(40)
        self.vox_thresh.valueChanged.connect(
            lambda v: self.vox_thresh_label.setText(f"{v//2}%"))
        vox_thresh_row.addWidget(self.vox_thresh)
        vox_thresh_row.addWidget(self.vox_thresh_label)
        vox_layout.addLayout(vox_thresh_row)

        vox_status_row = QHBoxLayout()
        vox_status_row.addWidget(QLabel("Status:"))
        self.vox_status = QLabel("IDLE")
        self.vox_status.setStyleSheet("font-weight: bold; color: #666;")
        vox_status_row.addWidget(self.vox_status)
        vox_layout.addLayout(vox_status_row)

        layout.addWidget(vox_box)

        # ── Audio Monitor / Passthrough ───────────────────────────────────────
        mon_box = QGroupBox("MONITOR")
        mon_layout = QHBoxLayout(mon_box)

        self.chk_passthrough = QCheckBox("Audio Passthrough (monitor mic)")
        self.chk_passthrough.setToolTip("Routes microphone audio to speaker output")
        self.chk_passthrough.toggled.connect(self.audio.set_passthrough)
        mon_layout.addWidget(self.chk_passthrough)

        self.audio_status = QLabel("● Stopped")
        self.audio_status.setStyleSheet("color: #666; font-weight: bold;")
        mon_layout.addWidget(self.audio_status)
        mon_layout.addStretch()

        layout.addWidget(mon_box)

        # ── Digital Audio Wiring Info ──────────────────────────────────────────
        info_box = QGroupBox("WSJT-X AUDIO WIRING GUIDE")
        info_layout = QVBoxLayout(info_box)
        info_text = QLabel(
            "For WSJT-X digital modes, use Virtual Audio Cable (VAC) or VB-CABLE:\n\n"
            "  FT-817 → [USB Audio Interface] → Computer Input Device\n"
            "  Computer Output Device → [USB Audio Interface] → FT-817\n\n"
            "  1. Set WSJT-X audio input  = your USB interface input\n"
            "  2. Set WSJT-X audio output = your USB interface output\n"
            "  3. Enable CAT control in WSJT-X: Rig = Hamlib NET rigctl\n"
            "     Host: localhost  Port: 4532\n\n"
            "  Alternatively, run rigctld from Hamlib and point WSJT-X to it.\n"
            "  Yaesu FT-8XX Suite by K3LH will auto-sync frequency/mode with WSJT-X via UDP."
        )
        info_text.setStyleSheet("font-family: Consolas; font-size: 10px; line-height: 1.6;")
        info_text.setWordWrap(True)
        info_layout.addWidget(info_text)
        layout.addWidget(info_box)

        # ── Voice Recorder ────────────────────────────────────────────────────
        rec_box = QGroupBox("VOICE RECORDER  —  Record & Transmit")
        rec_outer = QVBoxLayout(rec_box)
        rec_outer.setSpacing(6)

        # Status bar
        rec_status_row = QHBoxLayout()
        self.rec_status_label = QLabel("● No clip")
        self.rec_status_label.setStyleSheet(
            "font-family: Consolas; font-size: 10px; color: #888;")
        rec_status_row.addWidget(self.rec_status_label)
        rec_status_row.addStretch()
        self.rec_duration_label = QLabel("")
        self.rec_duration_label.setStyleSheet(
            "font-family: Consolas; font-size: 10px; color: #aaa;")
        rec_status_row.addWidget(self.rec_duration_label)
        rec_outer.addLayout(rec_status_row)

        # Record timer (updates every second while recording)
        self._rec_elapsed = 0
        self._rec_timer = QTimer()
        self._rec_timer.setInterval(1000)
        self._rec_timer.timeout.connect(self._tick_rec_timer)

        # Recording progress bar (max 120 s)
        self.rec_progress = QProgressBar()
        self.rec_progress.setRange(0, 120)
        self.rec_progress.setValue(0)
        self.rec_progress.setTextVisible(True)
        self.rec_progress.setFormat("%vs")
        self.rec_progress.setFixedHeight(14)
        self.rec_progress.setStyleSheet(
            "QProgressBar::chunk { background: #f85149; }")
        rec_outer.addWidget(self.rec_progress)

        # Button row 1: Record / Stop
        btn_row1 = QHBoxLayout()
        self.btn_record = QPushButton("⏺  Record")
        self.btn_record.setCheckable(True)
        self.btn_record.setMinimumHeight(36)
        self.btn_record.setToolTip(
            "Start capturing microphone audio into a clip")
        self.btn_record.clicked.connect(self._toggle_record)
        btn_row1.addWidget(self.btn_record)

        self.btn_play_local = QPushButton("▶  Preview")
        self.btn_play_local.setMinimumHeight(36)
        self.btn_play_local.setEnabled(False)
        self.btn_play_local.setToolTip(
            "Play the clip through your speakers (no TX)")
        self.btn_play_local.clicked.connect(self._preview_clip)
        btn_row1.addWidget(self.btn_play_local)

        rec_outer.addLayout(btn_row1)

        # Button row 2: TX / Stop TX
        btn_row2 = QHBoxLayout()
        self.btn_tx_clip = QPushButton("📡  Transmit Clip")
        self.btn_tx_clip.setMinimumHeight(40)
        self.btn_tx_clip.setEnabled(False)
        self.btn_tx_clip.setToolTip(
            "Key PTT, play clip over the radio, then un-key PTT")
        self.btn_tx_clip.setStyleSheet(
            "QPushButton { font-weight: bold; } "
            "QPushButton:enabled { color: #3fb950; }")
        self.btn_tx_clip.clicked.connect(self._transmit_clip)
        btn_row2.addWidget(self.btn_tx_clip)

        self.btn_stop_tx = QPushButton("■  Stop TX")
        self.btn_stop_tx.setMinimumHeight(40)
        self.btn_stop_tx.setEnabled(False)
        self.btn_stop_tx.setStyleSheet("QPushButton:enabled { color: #f85149; }")
        self.btn_stop_tx.setToolTip("Abort clip TX immediately and drop PTT")
        self.btn_stop_tx.clicked.connect(self._stop_tx)
        btn_row2.addWidget(self.btn_stop_tx)

        rec_outer.addLayout(btn_row2)

        # Button row 3: Save / Load
        btn_row3 = QHBoxLayout()
        self.btn_save_clip = QPushButton("💾  Save WAV…")
        self.btn_save_clip.setEnabled(False)
        self.btn_save_clip.setToolTip("Save clip as a WAV file")
        self.btn_save_clip.clicked.connect(self._save_clip)
        btn_row3.addWidget(self.btn_save_clip)

        self.btn_load_clip = QPushButton("📂  Load WAV…")
        self.btn_load_clip.setToolTip("Load a WAV file as the clip to transmit")
        self.btn_load_clip.clicked.connect(self._load_clip)
        btn_row3.addWidget(self.btn_load_clip)

        rec_outer.addLayout(btn_row3)

        # PTT mode note
        ptt_note = QLabel(
            "ℹ  PTT is keyed automatically via CAT when you press Transmit.\n"
            "   If radio is not connected, enable VOX or key PTT manually.")
        ptt_note.setStyleSheet(
            "font-size: 9px; color: #666; padding: 2px 0 0 0;")
        ptt_note.setWordWrap(True)
        rec_outer.addWidget(ptt_note)

        layout.addWidget(rec_box)

        layout.addStretch()

    # ─── Device Population ────────────────────────────────────────────────────

    def _populate_devices(self):
        if not AUDIO_AVAILABLE:
            return
        self.in_combo.clear()
        self.out_combo.clear()

        for idx, name in AudioEngine.list_input_devices():
            self.in_combo.addItem(name, idx)

        for idx, name in AudioEngine.list_output_devices():
            self.out_combo.addItem(name, idx)

    # ─── Audio Start/Stop ─────────────────────────────────────────────────────

    def _toggle_audio(self, checked: bool):
        if checked:
            in_idx  = self.in_combo.currentData()
            out_idx = self.out_combo.currentData()
            success = self.audio.start(in_idx, out_idx)
            if success:
                self.btn_start.setText("■ STOP AUDIO")
                self.audio_status.setText("● Running")
                self.audio_status.setStyleSheet("color: #3fb950; font-weight: bold;")
            else:
                self.btn_start.setChecked(False)
        else:
            self.audio.stop()
            self.btn_start.setText("▶ START AUDIO")
            self.audio_status.setText("● Stopped")
            self.audio_status.setStyleSheet("color: #666; font-weight: bold;")

    def _toggle_vox(self, enabled: bool):
        threshold = self.vox_thresh.value() / 200.0
        self.audio.set_vox(enabled, threshold)

    # ─── Signal Wiring ────────────────────────────────────────────────────────

    def _wire_signals(self):
        self.audio.level_updated.connect(self._on_levels)
        self.audio.vox_triggered.connect(self._on_vox)
        self.audio.recording_started.connect(self._on_rec_started)
        self.audio.recording_stopped.connect(self._on_rec_stopped)
        self.audio.playback_started.connect(self._on_playback_started)
        self.audio.playback_finished.connect(self._on_playback_finished)
        self.audio.clip_saved.connect(lambda p: self._rec_status(f"Saved: {p}"))
        self.audio.clip_loaded.connect(lambda p, d: self._update_clip_info(p, d))

    @pyqtSlot(float, float)
    def _on_levels(self, in_lvl: float, out_lvl: float):
        if hasattr(self, 'in_meter'):
            self.in_meter.set_level(in_lvl)
            self.out_meter.set_level(out_lvl)

    @pyqtSlot(bool)
    def _on_vox(self, active: bool):
        if hasattr(self, 'vox_status'):
            if active:
                self.vox_status.setText("● TX")
                self.vox_status.setStyleSheet("color: #f85149; font-weight: bold;")
            else:
                self.vox_status.setText("IDLE")
                self.vox_status.setStyleSheet("color: #666; font-weight: bold;")

    # ─── Voice Recorder Slots ─────────────────────────────────────────────────

    def _toggle_record(self, checked: bool):
        if checked:
            if not self.audio.is_running:
                QMessageBox.warning(self, "Audio Not Started",
                    "Start the audio engine first (▶ START AUDIO).")
                self.btn_record.setChecked(False)
                return
            self.audio.start_recording()
        else:
            self.audio.stop_recording()

    def _preview_clip(self):
        """Play clip to local speakers without keying PTT."""
        if not self.audio.has_clip:
            return
        if not self.audio.is_running:
            QMessageBox.warning(self, "Audio Not Started",
                "Start the audio engine first (▶ START AUDIO).")
            return
        import numpy as np
        self.audio.play_audio(self.audio._clip * self.audio._output_gain)
        self._rec_status("Previewing clip…")

    def _transmit_clip(self):
        cat = getattr(self, 'cat', None)
        self.audio.play_clip_over_tx(cat=cat)

    def _stop_tx(self):
        cat = getattr(self, 'cat', None)
        self.audio.stop_clip_playback(cat=cat)

    def _save_clip(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Voice Clip", "voice_clip.wav",
            "WAV Audio (*.wav)")
        if path:
            self.audio.save_clip(path)

    def _load_clip(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Voice Clip", "",
            "WAV Audio (*.wav);;All Files (*)")
        if path:
            self.audio.load_clip(path)

    def _rec_status(self, msg: str):
        if hasattr(self, 'rec_status_label'):
            self.rec_status_label.setText(msg)

    def _update_clip_info(self, path: str, duration: float):
        import os
        self._rec_status(f"● Clip: {os.path.basename(path)}")
        if hasattr(self, 'rec_duration_label'):
            self.rec_duration_label.setText(f"{duration:.1f}s")
        self._set_clip_buttons_enabled(True)

    def _set_clip_buttons_enabled(self, enabled: bool):
        for btn in ('btn_play_local', 'btn_tx_clip', 'btn_save_clip'):
            if hasattr(self, btn):
                getattr(self, btn).setEnabled(enabled)

    def _tick_rec_timer(self):
        self._rec_elapsed += 1
        if hasattr(self, 'rec_progress'):
            self.rec_progress.setValue(min(self._rec_elapsed, 120))

    @pyqtSlot()
    def _on_rec_started(self):
        self._rec_elapsed = 0
        if hasattr(self, 'rec_progress'):
            self.rec_progress.setValue(0)
            self.rec_progress.setStyleSheet(
                "QProgressBar::chunk { background: #f85149; }")
        if hasattr(self, '_rec_timer'):
            self._rec_timer.start()
        self.btn_record.setText("⏹  Stop Recording")
        self._rec_status("● RECORDING…")
        self._set_clip_buttons_enabled(False)

    @pyqtSlot(float)
    def _on_rec_stopped(self, duration: float):
        if hasattr(self, '_rec_timer'):
            self._rec_timer.stop()
        self.btn_record.setText("⏺  Record")
        self.btn_record.setChecked(False)
        if hasattr(self, 'rec_progress'):
            self.rec_progress.setStyleSheet(
                "QProgressBar::chunk { background: #3fb950; }")
        if duration > 0:
            self._rec_status(f"● Clip ready  ({duration:.1f}s)")
            if hasattr(self, 'rec_duration_label'):
                self.rec_duration_label.setText(f"{duration:.1f}s")
            self._set_clip_buttons_enabled(True)
        else:
            self._rec_status("● No audio captured")

    @pyqtSlot()
    def _on_playback_started(self):
        self._rec_status("📡 Transmitting…")
        if hasattr(self, 'btn_tx_clip'):
            self.btn_tx_clip.setEnabled(False)
        if hasattr(self, 'btn_stop_tx'):
            self.btn_stop_tx.setEnabled(True)

    @pyqtSlot()
    def _on_playback_finished(self):
        self._rec_status("● Clip ready")
        if hasattr(self, 'btn_tx_clip'):
            self.btn_tx_clip.setEnabled(self.audio.has_clip)
        if hasattr(self, 'btn_stop_tx'):
            self.btn_stop_tx.setEnabled(False)
