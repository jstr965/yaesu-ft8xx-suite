"""
WSJT-X Engine Settings Dialog
Configure all parameters needed to run WSJT-X silently in the background.
"""

import os
import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QFormLayout, QLabel, QLineEdit, QComboBox, QPushButton,
    QGroupBox, QCheckBox, QSpinBox, QDialogButtonBox, QFileDialog,
    QMessageBox, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from core.wsjtx_engine import WSJTXConfig, WSJTX_SEARCH_PATHS, WSJTX_CONFIG_FILE
from core.audio_engine import AudioEngine

SETTINGS_FILE = Path("ft817_settings.json")

MODES_AVAILABLE = ["FT8", "FT4", "JS8", "WSPR", "JT65", "JT9", "Q65", "MSK144"]

BAUD_RATES = ["4800", "9600", "19200", "38400"]

# Standard FT8 frequencies by band for quick reference
FT8_QUICK_FREQS = {
    "40m":  "7.074",
    "20m":  "14.074",
    "17m":  "18.100",
    "15m":  "21.074",
    "10m":  "28.074",
    "6m":   "50.313",
}


def load_settings() -> dict:
    """Load persisted settings from JSON file."""
    defaults = {
        "wsjtx_exe":   "",
        "callsign":    "",
        "grid":        "",
        "radio_model": "FT-817",
        "cat_port":    "COM1",
        "baud":        "9600",
        "audio_in":    "",
        "audio_out":   "",
        "mode":        "FT8",
        "udp_port":    "2237",
        "tx_df":       "1500",
        "rx_df":       "1500",
        "freq_tol":    "50",
        "auto_log":    True,
        "auto_qsy":    True,
        "split_mode":  False,
        "tx_first":    False,
    }
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE) as f:
                saved = json.load(f)
            defaults.update(saved)
        except Exception:
            pass
    return defaults


def save_settings(settings: dict):
    """Persist settings to JSON file."""
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        print(f"Settings save error: {e}")


class WSJTXSettingsDialog(QDialog):
    """
    Full settings dialog for the embedded WSJT-X engine.
    Covers: WSJT-X path, identity, CAT, audio, operating parameters.
    """

    def __init__(self, current_settings: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙  WSJT-X Engine Settings")
        self.setMinimumWidth(560)
        self.setMinimumHeight(500)
        self._settings = dict(current_settings)
        self._build_ui()
        self._populate()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Header
        header = QLabel("  Configure the hidden WSJT-X engine")
        header.setStyleSheet(
            "font-size: 13px; font-weight: bold; padding: 8px; "
            "background: #1f6feb22; border-radius: 6px;"
        )
        layout.addWidget(header)

        tabs = QTabWidget()
        layout.addWidget(tabs, 1)

        # ── Tab 1: WSJT-X & Identity ──────────────────────────────────────────
        identity_tab = QWidget()
        ident_layout = QVBoxLayout(identity_tab)

        # WSJT-X executable
        exe_box = QGroupBox("WSJT-X EXECUTABLE")
        exe_layout = QVBoxLayout(exe_box)

        exe_row = QHBoxLayout()
        self.exe_edit = QLineEdit()
        self.exe_edit.setPlaceholderText(r"C:\WSJT\wsjtx\bin\wsjtx.exe")
        exe_row.addWidget(self.exe_edit)
        btn_browse = QPushButton("Browse…")
        btn_browse.clicked.connect(self._browse_exe)
        exe_row.addWidget(btn_browse)
        exe_layout.addLayout(exe_row)

        btn_find = QPushButton("🔍 Auto-detect WSJT-X")
        btn_find.clicked.connect(self._auto_find)
        exe_layout.addWidget(btn_find)

        self.exe_status = QLabel("")
        self.exe_status.setStyleSheet("font-size: 10px; color: #8b949e;")
        exe_layout.addWidget(self.exe_status)
        ident_layout.addWidget(exe_box)

        # Station identity
        id_box = QGroupBox("STATION IDENTITY")
        id_form = QFormLayout(id_box)
        self.call_edit = QLineEdit()
        self.call_edit.setPlaceholderText("K1ABC")
        self.call_edit.setMaximumWidth(120)
        id_form.addRow("Callsign *", self.call_edit)

        self.grid_edit = QLineEdit()
        self.grid_edit.setPlaceholderText("EM72")
        self.grid_edit.setMaximumWidth(100)
        id_form.addRow("Grid Square *", self.grid_edit)

        grid_help = QLabel(
            "Grid square is required for digital modes. Use 6-char format (e.g. EM72ab).\n"
            "Look up yours at: qthlocator.free.fr"
        )
        grid_help.setStyleSheet("font-size: 9px; color: #8b949e;")
        grid_help.setWordWrap(True)
        id_form.addRow("", grid_help)
        ident_layout.addWidget(id_box)
        ident_layout.addStretch()
        tabs.addTab(identity_tab, "🪪  Identity")

        # ── Tab 2: CAT / Radio ────────────────────────────────────────────────
        cat_tab = QWidget()
        cat_layout = QVBoxLayout(cat_tab)

        cat_box = QGroupBox("CAT PORT  (Digirig Serial Port)")
        cat_form = QFormLayout(cat_box)

        from core.cat817 import RADIO_MODELS
        self.radio_model_combo = QComboBox()
        for key, info in RADIO_MODELS.items():
            self.radio_model_combo.addItem(info["name"], key)
        cat_form.addRow("Radio Model:", self.radio_model_combo)

        self.port_edit = QLineEdit()
        self.port_edit.setPlaceholderText("COM3")
        self.port_edit.setMaximumWidth(100)
        cat_form.addRow("COM Port", self.port_edit)

        self.baud_combo = QComboBox()
        self.baud_combo.addItems(BAUD_RATES)
        self.baud_combo.setMaximumWidth(100)
        cat_form.addRow("Baud Rate", self.baud_combo)

        port_help = QLabel(
            "Use the COM port shown in Device Manager under\n"
            "'Silicon Labs CP210x' for the Digirig.\n"
            "FT-817/818: menu #14  |  FT-857/897: menu #59\n"
            "Default baud rate is 9600 on all models."
        )
        port_help.setStyleSheet("font-size: 9px; color: #8b949e;")
        port_help.setWordWrap(True)
        cat_form.addRow("", port_help)
        cat_layout.addWidget(cat_box)

        ptt_box = QGroupBox("PTT METHOD")
        ptt_layout = QVBoxLayout(ptt_box)
        ptt_info = QLabel(
            "PTT is controlled via CAT commands through the serial port.\n"
            "No additional wiring needed — Yaesu FT-8XX Suite by K3LH handles PTT\n"
            "automatically for all supported radio models."
        )
        ptt_info.setStyleSheet("font-size: 10px; color: #8b949e;")
        ptt_info.setWordWrap(True)
        ptt_layout.addWidget(ptt_info)
        cat_layout.addWidget(ptt_box)
        cat_layout.addStretch()
        tabs.addTab(cat_tab, "📡  CAT / Radio")

        # ── Tab 3: Audio ──────────────────────────────────────────────────────
        audio_tab = QWidget()
        audio_layout = QVBoxLayout(audio_tab)

        audio_box = QGroupBox("AUDIO DEVICES  (Digirig USB Audio Codec)")
        audio_form = QFormLayout(audio_box)

        self.audio_in_combo = QComboBox()
        self.audio_in_combo.setMinimumWidth(280)
        audio_form.addRow("Input (Radio RX):", self.audio_in_combo)

        self.audio_out_combo = QComboBox()
        self.audio_out_combo.setMinimumWidth(280)
        audio_form.addRow("Output (Radio TX):", self.audio_out_combo)

        btn_refresh_audio = QPushButton("⟳ Refresh Audio Devices")
        btn_refresh_audio.clicked.connect(self._refresh_audio)
        audio_form.addRow("", btn_refresh_audio)

        audio_help = QLabel(
            "Select 'USB Audio Codec' or 'Digirig' for both input and output.\n"
            "This is the Digirig's built-in soundcard that connects to the FT-817's DATA port."
        )
        audio_help.setStyleSheet("font-size: 9px; color: #8b949e;")
        audio_help.setWordWrap(True)
        audio_form.addRow("", audio_help)
        audio_layout.addWidget(audio_box)
        audio_layout.addStretch()

        self._refresh_audio()
        tabs.addTab(audio_tab, "🔊  Audio")

        # ── Tab 4: Operating ──────────────────────────────────────────────────
        op_tab = QWidget()
        op_layout = QVBoxLayout(op_tab)

        mode_box = QGroupBox("DEFAULT MODE")
        mode_form = QFormLayout(mode_box)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(MODES_AVAILABLE)
        self.mode_combo.setMaximumWidth(120)
        mode_form.addRow("Mode:", self.mode_combo)
        op_layout.addWidget(mode_box)

        freq_box = QGroupBox("FREQUENCY SETTINGS")
        freq_form = QFormLayout(freq_box)

        self.tx_df_spin = QSpinBox()
        self.tx_df_spin.setRange(200, 2800)
        self.tx_df_spin.setValue(1500)
        self.tx_df_spin.setSuffix(" Hz")
        freq_form.addRow("TX Audio Freq:", self.tx_df_spin)

        self.rx_df_spin = QSpinBox()
        self.rx_df_spin.setRange(200, 2800)
        self.rx_df_spin.setValue(1500)
        self.rx_df_spin.setSuffix(" Hz")
        freq_form.addRow("RX Audio Freq:", self.rx_df_spin)

        self.freq_tol_spin = QSpinBox()
        self.freq_tol_spin.setRange(10, 500)
        self.freq_tol_spin.setValue(50)
        self.freq_tol_spin.setSuffix(" Hz")
        freq_form.addRow("Freq Tolerance:", self.freq_tol_spin)
        op_layout.addWidget(freq_box)

        options_box = QGroupBox("OPTIONS")
        options_layout = QVBoxLayout(options_box)
        self.chk_auto_log  = QCheckBox("Auto-log QSOs to contact log")
        self.chk_auto_qsy  = QCheckBox("Sync radio frequency with WSJT-X")
        self.chk_tx_first  = QCheckBox("Transmit on first period (even)")
        self.chk_auto_log.setChecked(True)
        self.chk_auto_qsy.setChecked(True)
        options_layout.addWidget(self.chk_auto_log)
        options_layout.addWidget(self.chk_auto_qsy)
        options_layout.addWidget(self.chk_tx_first)
        op_layout.addWidget(options_box)
        op_layout.addStretch()
        tabs.addTab(op_tab, "⚙  Operating")

        # ── Tab 5: Network ────────────────────────────────────────────────────
        net_tab = QWidget()
        net_layout = QVBoxLayout(net_tab)

        net_box = QGroupBox("UDP NETWORK")
        net_form = QFormLayout(net_box)

        self.udp_port_spin = QSpinBox()
        self.udp_port_spin.setRange(1024, 65535)
        self.udp_port_spin.setValue(2237)
        net_form.addRow("UDP Port:", self.udp_port_spin)

        net_help = QLabel(
            "Default port 2237 is standard for WSJT-X.\n"
            "Only change this if you have a port conflict."
        )
        net_help.setStyleSheet("font-size: 9px; color: #8b949e;")
        net_layout.addWidget(net_box)
        net_layout.addWidget(net_help)
        net_layout.addStretch()
        tabs.addTab(net_tab, "🌐  Network")

        # ── Buttons ───────────────────────────────────────────────────────────
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(line)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    # ─── Population ───────────────────────────────────────────────────────────

    def _populate(self):
        s = self._settings
        self.exe_edit.setText(s.get("wsjtx_exe", ""))
        self.call_edit.setText(s.get("callsign", ""))
        self.grid_edit.setText(s.get("grid", ""))
        self.port_edit.setText(s.get("cat_port", "COM1"))

        # Radio model
        saved_model = s.get("radio_model", "FT-817")
        idx = self.radio_model_combo.findData(saved_model)
        self.radio_model_combo.setCurrentIndex(max(0, idx))

        baud = s.get("baud", "9600")
        idx = self.baud_combo.findText(baud)
        self.baud_combo.setCurrentIndex(max(0, idx))

        mode = s.get("mode", "FT8")
        idx = self.mode_combo.findText(mode)
        self.mode_combo.setCurrentIndex(max(0, idx))

        self.tx_df_spin.setValue(int(s.get("tx_df", 1500)))
        self.rx_df_spin.setValue(int(s.get("rx_df", 1500)))
        self.freq_tol_spin.setValue(int(s.get("freq_tol", 50)))
        self.udp_port_spin.setValue(int(s.get("udp_port", 2237)))
        self.chk_auto_log.setChecked(bool(s.get("auto_log", True)))
        self.chk_auto_qsy.setChecked(bool(s.get("auto_qsy", True)))
        self.chk_tx_first.setChecked(bool(s.get("tx_first", False)))

        # Set audio combos to saved values
        saved_in  = s.get("audio_in", "")
        saved_out = s.get("audio_out", "")
        for combo, saved in [(self.audio_in_combo, saved_in),
                              (self.audio_out_combo, saved_out)]:
            idx = combo.findText(saved)
            if idx >= 0:
                combo.setCurrentIndex(idx)

        self._check_exe(self.exe_edit.text())

    # ─── Actions ──────────────────────────────────────────────────────────────

    def _browse_exe(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Find wsjtx.exe", r"C:\WSJT",
            "WSJT-X Executable (wsjtx.exe);;All Files (*)"
        )
        if path:
            self.exe_edit.setText(path)
            self._check_exe(path)

    def _auto_find(self):
        for path in WSJTX_SEARCH_PATHS:
            if os.path.exists(path):
                self.exe_edit.setText(path)
                self._check_exe(path)
                return
        self.exe_status.setText("⚠ Could not auto-detect WSJT-X. Browse manually.")
        self.exe_status.setStyleSheet("color: #d29922; font-size: 10px;")

    def _check_exe(self, path: str):
        if path and os.path.exists(path):
            self.exe_status.setText(f"✓ Found: {path}")
            self.exe_status.setStyleSheet("color: #3fb950; font-size: 10px;")
        elif path:
            self.exe_status.setText(f"✗ Not found: {path}")
            self.exe_status.setStyleSheet("color: #f85149; font-size: 10px;")
        else:
            self.exe_status.setText("No path set — click Browse or Auto-detect")
            self.exe_status.setStyleSheet("color: #8b949e; font-size: 10px;")

    def _refresh_audio(self):
        all_devs = AudioEngine.list_devices()
        inputs  = [d["name"] for d in all_devs if d["inputs"] > 0]
        outputs = [d["name"] for d in all_devs if d["outputs"] > 0]

        saved_in  = self.audio_in_combo.currentText()
        saved_out = self.audio_out_combo.currentText()

        self.audio_in_combo.clear()
        self.audio_out_combo.clear()
        self.audio_in_combo.addItems(inputs)
        self.audio_out_combo.addItems(outputs)

        for combo, saved in [(self.audio_in_combo, saved_in),
                              (self.audio_out_combo, saved_out)]:
            idx = combo.findText(saved)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                # Try to auto-select Digirig/USB Audio
                for i in range(combo.count()):
                    txt = combo.itemText(i).lower()
                    if "usb audio" in txt or "digirig" in txt or "codec" in txt:
                        combo.setCurrentIndex(i)
                        break

    def _on_accept(self):
        # Validate required fields
        if not self.call_edit.text().strip():
            QMessageBox.warning(self, "Required", "Callsign is required.")
            return
        if not self.grid_edit.text().strip():
            QMessageBox.warning(self, "Required", "Grid square is required.")
            return
        if not self.exe_edit.text().strip():
            QMessageBox.warning(self, "Required",
                "Please set the path to wsjtx.exe.\n"
                "WSJT-X must be installed — download from physics.princeton.edu/pulsar/K1JT/wsjtx.html"
            )
            return
        self.accept()

    # ─── Result ───────────────────────────────────────────────────────────────

    def get_settings(self) -> dict:
        return {
            "wsjtx_exe":   self.exe_edit.text().strip(),
            "callsign":    self.call_edit.text().strip().upper(),
            "grid":        self.grid_edit.text().strip().upper(),
            "radio_model": self.radio_model_combo.currentData(),
            "cat_port":    self.port_edit.text().strip().upper(),
            "baud":        self.baud_combo.currentText(),
            "audio_in":    self.audio_in_combo.currentText(),
            "audio_out":   self.audio_out_combo.currentText(),
            "mode":        self.mode_combo.currentText(),
            "tx_df":       str(self.tx_df_spin.value()),
            "rx_df":       str(self.rx_df_spin.value()),
            "freq_tol":    str(self.freq_tol_spin.value()),
            "udp_port":    str(self.udp_port_spin.value()),
            "auto_log":    self.chk_auto_log.isChecked(),
            "auto_qsy":    self.chk_auto_qsy.isChecked(),
            "tx_first":    self.chk_tx_first.isChecked(),
        }
