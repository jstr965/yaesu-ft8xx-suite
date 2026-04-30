"""
Integrated Digital Modes Panel
Full FT8/FT4/JS8/WSPR operating interface.
Drives a hidden WSJT-X process — user never needs to open WSJT-X.
"""

import datetime
import time
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QPushButton, QComboBox, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QSplitter, QTextEdit, QFrame, QProgressBar,
    QCheckBox, QSpinBox, QSizePolicy, QGridLayout, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSlot, QTimer
from PyQt6.QtGui import QColor, QFont, QBrush

from core.wsjtx_engine import WSJTXEngine
from core.wsjtx_interface import WSJTXDecode, WSJTXStatus
from core.cat817 import CAT817
from core.logger import ContactLogger, QSOContact
from ui.wsjtx_settings import WSJTXSettingsDialog, load_settings, save_settings


# ─── Band / Frequency tables ──────────────────────────────────────────────────

MODE_FREQS = {
    "FT8": {
        "160m":  1840000, "80m":  3573000, "60m":  5357000,
        "40m":   7074000, "30m": 10136000, "20m": 14074000,
        "17m":  18100000, "15m": 21074000, "12m": 24915000,
        "10m":  28074000, "6m":  50313000, "2m": 144174000,
    },
    "FT4": {
        "80m":  3575000, "40m":  7047500, "30m": 10140000,
        "20m": 14080000, "17m": 18104000, "15m": 21140000,
        "12m": 24919000, "10m": 28180000, "6m":  50318000,
    },
    "JS8": {
        "80m":  3578000, "40m":  7078000, "30m": 10130000,
        "20m": 14078000, "17m": 18104000, "15m": 21078000,
        "10m": 28078000, "6m":  50318000,
    },
    "WSPR": {
        "160m":  1836600, "80m":  3592600, "60m":  5287200,
        "40m":   7038600, "30m": 10138700, "20m": 14095600,
        "17m":  18104600, "15m": 21094600, "12m": 24924600,
        "10m":  28124600, "6m":  50293000,
    },
}

MODE_PERIODS = {
    "FT8": 15, "FT4": 7.5, "JS8": 15, "WSPR": 120,
    "JT65": 60, "JT9": 60,
}

SNR_BG = {
    "great": QColor("#0d2b1a"),
    "good":  QColor("#1a2b0d"),
    "fair":  QColor("#2b2a0d"),
    "weak":  QColor("#2a1a0d"),
    "vweak": QColor("#1a1a2b"),
}

def snr_color(snr: int) -> QColor:
    if snr > 0:   return SNR_BG["great"]
    if snr > -10: return SNR_BG["good"]
    if snr > -15: return SNR_BG["fair"]
    if snr > -20: return SNR_BG["weak"]
    return SNR_BG["vweak"]


# ─── TX Period Timer ──────────────────────────────────────────────────────────

class PeriodTimer(QWidget):
    """Shows the current TX/RX cycle countdown bar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._period = 15
        self._bar = QProgressBar()
        self._bar.setRange(0, 1000)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(10)
        layout.addWidget(self._bar, 1)

        self._lbl = QLabel("--")
        self._lbl.setFixedWidth(36)
        self._lbl.setStyleSheet("font-family:Consolas; font-size:10px;")
        layout.addWidget(self._lbl)

        self._tick = QTimer()
        self._tick.timeout.connect(self._update)
        self._tick.start(100)

    def set_period(self, seconds: float):
        self._period = seconds

    def _update(self):
        now = time.time()
        frac = (now % self._period) / self._period
        self._bar.setValue(int(frac * 1000))
        remaining = self._period - (now % self._period)
        self._lbl.setText(f"{remaining:.1f}")


# ─── Decode Table ─────────────────────────────────────────────────────────────

class DecodeTable(QTableWidget):
    COLS = ["UTC", "dB", "DT", "Freq", "Message"]

    def __init__(self, parent=None):
        super().__init__(0, len(self.COLS), parent)
        self.setHorizontalHeaderLabels(self.COLS)
        self.setAlternatingRowColors(False)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.setFont(QFont("Consolas", 10))
        self.setShowGrid(True)
        self.verticalHeader().setDefaultSectionSize(22)

        hh = self.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

        self._decodes: list[WSJTXDecode] = []

    def add_decode(self, d: WSJTXDecode):
        t = d.time
        utc = f"{t//10000:02d}:{(t%10000)//100:02d}"
        snr_s = f"{d.snr:+d}"
        dt_s  = f"{d.delta_time:+.1f}"
        df_s  = f"{d.delta_freq}"

        self.insertRow(0)
        self._decodes.insert(0, d)

        bg = snr_color(d.snr)
        for col, val in enumerate([utc, snr_s, dt_s, df_s, d.message]):
            item = QTableWidgetItem(str(val))
            item.setBackground(QBrush(bg))
            if col == 4:
                # Highlight CQ calls
                if d.message.startswith("CQ"):
                    item.setForeground(QBrush(QColor("#3fb950")))
                    item.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
                else:
                    item.setForeground(QBrush(QColor("#c9d1d9")))
            else:
                item.setForeground(QBrush(QColor("#8b949e")))
            self.setItem(0, col, item)

        while len(self._decodes) > 300:
            self.removeRow(self.rowCount() - 1)
            self._decodes.pop()

    def get_decode_at(self, row: int) -> WSJTXDecode | None:
        if 0 <= row < len(self._decodes):
            return self._decodes[row]
        return None

    def clear_decodes(self):
        self.setRowCount(0)
        self._decodes.clear()


# ─── Main Digital Panel ───────────────────────────────────────────────────────

class DigitalModesPanel(QWidget):
    """
    Fully integrated digital modes panel.
    Manages the hidden WSJT-X engine and exposes a complete operating UI.
    """

    def __init__(self, cat: CAT817, logger: ContactLogger, parent=None):
        super().__init__(parent)
        self.cat    = cat
        self.logger = logger

        self.engine   = WSJTXEngine(self)
        self._settings = load_settings()
        self._current_status: WSJTXStatus | None = None
        self._selected_call = ""

        self._build_ui()
        self._wire_signals()

    # ─── UI ───────────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(5)

        # ── Top bar: engine control ───────────────────────────────────────────
        top = QHBoxLayout()
        layout.addLayout(top)

        # Engine start/stop
        engine_box = QGroupBox("ENGINE")
        engine_layout = QHBoxLayout(engine_box)

        self.btn_start = QPushButton("▶  START ENGINE")
        self.btn_start.setObjectName("btn_connect")
        self.btn_start.setCheckable(True)
        self.btn_start.setMinimumWidth(150)
        self.btn_start.clicked.connect(self._toggle_engine)
        engine_layout.addWidget(self.btn_start)

        self.engine_status = QLabel("⬤  Stopped")
        self.engine_status.setStyleSheet("color:#666; font-weight:bold;")
        engine_layout.addWidget(self.engine_status)

        self.btn_settings = QPushButton("⚙  Settings")
        self.btn_settings.clicked.connect(self._open_settings)
        engine_layout.addWidget(self.btn_settings)
        top.addWidget(engine_box)

        # Mode + Band
        mode_box = QGroupBox("MODE / BAND")
        mode_layout = QHBoxLayout(mode_box)
        mode_layout.addWidget(QLabel("Mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["FT8", "FT4", "JS8", "WSPR", "JT65", "JT9"])
        self.mode_combo.setCurrentText(self._settings.get("mode", "FT8"))
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        mode_layout.addWidget(self.mode_combo)

        mode_layout.addWidget(QLabel("Band:"))
        self.band_combo = QComboBox()
        self.band_combo.addItems([
            "160m","80m","60m","40m","30m","20m","17m","15m","12m","10m","6m","2m"
        ])
        self.band_combo.setCurrentText("20m")
        self.band_combo.currentTextChanged.connect(self._on_band_changed)
        mode_layout.addWidget(self.band_combo)

        self.btn_qsy = QPushButton("QSY Radio →")
        self.btn_qsy.setToolTip("Tune radio to standard frequency for this mode/band")
        self.btn_qsy.clicked.connect(self._do_qsy)
        mode_layout.addWidget(self.btn_qsy)

        self.freq_label = QLabel("14.074 MHz")
        self.freq_label.setStyleSheet(
            "font-family:Consolas; font-size:13px; font-weight:bold;"
            "color:#58a6ff; padding:0 8px;")
        mode_layout.addWidget(self.freq_label)
        top.addWidget(mode_box)

        # Period timer
        timer_box = QGroupBox("PERIOD")
        timer_layout = QVBoxLayout(timer_box)
        self.period_timer = PeriodTimer()
        timer_layout.addWidget(self.period_timer)
        self.period_label = QLabel("15s / FT8")
        self.period_label.setStyleSheet("font-size:10px; color:#8b949e;")
        self.period_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        timer_layout.addWidget(self.period_label)
        top.addWidget(timer_box)

        # ── Status bar: live WSJT-X state ─────────────────────────────────────
        status_bar = QHBoxLayout()
        layout.addLayout(status_bar)

        for attr, text in [
            ("lbl_s_call",  "DX: —"),
            ("lbl_s_grid",  "Grid: —"),
            ("lbl_s_freq",  "Freq: —"),
            ("lbl_s_mode",  "Mode: —"),
            ("lbl_s_txrx",  "RX"),
        ]:
            lbl = QLabel(text)
            lbl.setFont(QFont("Consolas", 10))
            lbl.setStyleSheet("padding: 2px 10px; border: 1px solid #30363d; border-radius:4px;")
            setattr(self, attr, lbl)
            status_bar.addWidget(lbl)

        self.lbl_s_txrx.setMinimumWidth(60)
        self.lbl_s_txrx.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_bar.addStretch()

        # WSJT-X heartbeat indicator
        self.hb_label = QLabel("◌ WSJT-X")
        self.hb_label.setStyleSheet("color:#444; font-size:10px; font-weight:bold;")
        status_bar.addWidget(self.hb_label)

        # ── Main splitter ──────────────────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        layout.addWidget(splitter, 1)

        # Left: decode table
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(3)

        decode_header = QHBoxLayout()
        decode_header.addWidget(QLabel("📶  DECODED SIGNALS"))

        self.decode_count = QLabel("0 decodes")
        self.decode_count.setStyleSheet("color:#8b949e; font-size:10px;")
        decode_header.addWidget(self.decode_count)
        decode_header.addStretch()

        btn_clear = QPushButton("Clear")
        btn_clear.setFixedWidth(55)
        btn_clear.clicked.connect(self._clear_decodes)
        decode_header.addWidget(btn_clear)
        left_layout.addLayout(decode_header)

        self.decode_table = DecodeTable()
        self.decode_table.cellClicked.connect(self._on_decode_clicked)
        self.decode_table.cellDoubleClicked.connect(self._on_decode_dblclick)
        left_layout.addWidget(self.decode_table)
        splitter.addWidget(left)

        # Right: TX control + log — wrapped in scroll area
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        right_scroll.setMinimumWidth(280)
        right = QWidget()
        right_scroll.setWidget(right)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 4, 4, 4)
        right_layout.setSpacing(5)

        # TX control box
        tx_box = QGroupBox("TX CONTROL")
        tx_layout = QVBoxLayout(tx_box)

        # DX callsign
        dx_row = QHBoxLayout()
        dx_row.addWidget(QLabel("DX Call:"))
        self.dx_call_edit = QLineEdit()
        self.dx_call_edit.setPlaceholderText("Click a CQ decode →")
        self.dx_call_edit.setFont(QFont("Consolas", 11))
        dx_row.addWidget(self.dx_call_edit)

        self.btn_clear_dx = QPushButton("✕")
        self.btn_clear_dx.setFixedWidth(28)
        self.btn_clear_dx.clicked.connect(self.dx_call_edit.clear)
        dx_row.addWidget(self.btn_clear_dx)
        tx_layout.addLayout(dx_row)

        # DX grid
        grid_row = QHBoxLayout()
        grid_row.addWidget(QLabel("DX Grid:"))
        self.dx_grid_edit = QLineEdit()
        self.dx_grid_edit.setPlaceholderText("e.g. EM72")
        self.dx_grid_edit.setMaximumWidth(80)
        grid_row.addWidget(self.dx_grid_edit)
        grid_row.addStretch()
        tx_layout.addLayout(grid_row)

        # Free text
        ft_row = QHBoxLayout()
        ft_row.addWidget(QLabel("Free Text:"))
        self.free_text_edit = QLineEdit()
        self.free_text_edit.setPlaceholderText("73 de K1ABC EM72")
        ft_row.addWidget(self.free_text_edit)
        btn_send_ft = QPushButton("Send")
        btn_send_ft.setFixedWidth(55)
        btn_send_ft.clicked.connect(self._send_free_text)
        ft_row.addWidget(btn_send_ft)
        tx_layout.addLayout(ft_row)

        # TX enable + halt
        tx_btn_row = QHBoxLayout()
        self.btn_enable_tx = QPushButton("📡  ENABLE TX")
        self.btn_enable_tx.setCheckable(True)
        self.btn_enable_tx.setObjectName("btn_ptt")
        self.btn_enable_tx.setMinimumHeight(48)
        self.btn_enable_tx.clicked.connect(self._toggle_tx)
        tx_btn_row.addWidget(self.btn_enable_tx)

        self.btn_halt_tx = QPushButton("⛔  HALT TX")
        self.btn_halt_tx.setMinimumHeight(48)
        self.btn_halt_tx.setStyleSheet(
            "background:#4a1a1a; color:#f85149; border:1px solid #f85149;"
            "font-weight:bold; border-radius:6px;")
        self.btn_halt_tx.clicked.connect(lambda: self.engine.halt_tx())
        tx_btn_row.addWidget(self.btn_halt_tx)
        tx_layout.addLayout(tx_btn_row)

        right_layout.addWidget(tx_box)

        # Quick-log box
        log_box = QGroupBox("QUICK LOG")
        log_layout = QVBoxLayout(log_box)

        ql_grid = QGridLayout()
        ql_grid.addWidget(QLabel("Call:"), 0, 0)
        self.ql_call = QLineEdit()
        self.ql_call.setFont(QFont("Consolas", 10))
        ql_grid.addWidget(self.ql_call, 0, 1)

        ql_grid.addWidget(QLabel("RST S/R:"), 1, 0)
        rst_row_w = QWidget()
        rst_row_l = QHBoxLayout(rst_row_w)
        rst_row_l.setContentsMargins(0,0,0,0)
        self.ql_rst_s = QLineEdit("-10")
        self.ql_rst_s.setMaximumWidth(60)
        self.ql_rst_r = QLineEdit("-10")
        self.ql_rst_r.setMaximumWidth(60)
        rst_row_l.addWidget(self.ql_rst_s)
        rst_row_l.addWidget(QLabel("/"))
        rst_row_l.addWidget(self.ql_rst_r)
        rst_row_l.addStretch()
        ql_grid.addWidget(rst_row_w, 1, 1)

        ql_grid.addWidget(QLabel("Notes:"), 2, 0)
        self.ql_notes = QLineEdit()
        ql_grid.addWidget(self.ql_notes, 2, 1)

        log_layout.addLayout(ql_grid)

        btn_log = QPushButton("📒  Log QSO")
        btn_log.setObjectName("btn_connect")
        btn_log.clicked.connect(self._log_qso)
        log_layout.addWidget(btn_log)
        right_layout.addWidget(log_box)

        # Activity log
        act_box = QGroupBox("ACTIVITY")
        act_layout = QVBoxLayout(act_box)
        self.activity_log = QTextEdit()
        self.activity_log.setReadOnly(True)
        self.activity_log.setFont(QFont("Consolas", 9))
        act_layout.addWidget(self.activity_log)
        right_layout.addWidget(act_box, 1)

        splitter.addWidget(right_scroll)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        # ── Bottom: config reminder if not set up ─────────────────────────────
        self.setup_banner = QLabel(
            "⚠  Engine not configured — click  ⚙ Settings  to set your callsign, "
            "WSJT-X path, COM port and audio devices, then click  ▶ START ENGINE"
        )
        self.setup_banner.setStyleSheet(
            "background:#2d1f00; color:#e3b341; padding:8px 12px;"
            "border:1px solid #9e6a03; border-radius:5px; font-size:11px;"
        )
        self.setup_banner.setWordWrap(True)
        layout.addWidget(self.setup_banner)
        self._update_banner()

        # Update freq label for defaults
        self._update_freq_label()

    # ─── Signal Wiring ────────────────────────────────────────────────────────

    def _wire_signals(self):
        e = self.engine
        e.engine_started.connect(self._on_engine_started)
        e.engine_stopped.connect(self._on_engine_stopped)
        e.engine_error.connect(self._on_engine_error)
        e.connected.connect(self._on_wsjt_connected)
        e.heartbeat.connect(self._on_heartbeat)
        e.decode_received.connect(self._on_decode)
        e.status_received.connect(self._on_status)
        e.qso_logged.connect(self._on_qso_logged)
        e.status_message.connect(self._log)
        e.error_occurred.connect(lambda m: self._log(f"⚠ {m}"))

    # ─── Engine Control ───────────────────────────────────────────────────────

    def _toggle_engine(self, checked: bool):
        if checked:
            # Validate settings first
            if not self._settings.get("callsign"):
                self._open_settings()
                self.btn_start.setChecked(False)
                return
            exe = self._settings.get("wsjtx_exe", "")
            if not exe:
                self._open_settings()
                self.btn_start.setChecked(False)
                return

            ok = self.engine.start(exe, self._settings)
            if not ok:
                self.btn_start.setChecked(False)
        else:
            self.engine.stop()

    def _open_settings(self):
        dlg = WSJTXSettingsDialog(self._settings, self)
        if dlg.exec():
            self._settings = dlg.get_settings()
            save_settings(self._settings)
            self._log("Settings saved")
            self._update_banner()
            # Update mode combo to match settings
            self.mode_combo.setCurrentText(self._settings.get("mode", "FT8"))

    # ─── Mode / Band ──────────────────────────────────────────────────────────

    def _on_mode_changed(self, mode: str):
        period = MODE_PERIODS.get(mode, 15)
        self.period_timer.set_period(period)
        self.period_label.setText(f"{period}s / {mode}")
        self._update_freq_label()

    def _on_band_changed(self, band: str):
        self._update_freq_label()

    def _update_freq_label(self):
        mode = self.mode_combo.currentText()
        band = self.band_combo.currentText()
        freq = MODE_FREQS.get(mode, {}).get(band)
        if freq:
            self.freq_label.setText(f"{freq/1e6:.3f} MHz")
        else:
            self.freq_label.setText("—")

    def _do_qsy(self):
        mode = self.mode_combo.currentText()
        band = self.band_combo.currentText()
        freq = MODE_FREQS.get(mode, {}).get(band)
        if freq:
            self.cat.set_frequency(freq)
            self.cat.set_mode("USB")
            self._log(f"QSY → {freq/1e6:.3f} MHz ({mode} {band})")
        else:
            self._log(f"No standard frequency for {mode} on {band}")

    # ─── TX Control ───────────────────────────────────────────────────────────

    def _toggle_tx(self, checked: bool):
        if checked:
            self.btn_enable_tx.setText("📡  TX ENABLED")
            self.btn_enable_tx.setStyleSheet(
                "background:#4a0000; color:#ff6644; border:2px solid #ff4400;"
                "font-weight:bold; font-size:14px; border-radius:6px;")
            call = self.dx_call_edit.text().strip()
            grid = self.dx_grid_edit.text().strip()
            if call:
                self.engine.configure(
                    mode=self.mode_combo.currentText(),
                    dx_call=call,
                    dx_grid=grid,
                    generate_messages=True,
                )
        else:
            self.btn_enable_tx.setText("📡  ENABLE TX")
            self.btn_enable_tx.setStyleSheet("")
            self.engine.halt_tx(auto_only=False)

    def _send_free_text(self):
        text = self.free_text_edit.text().strip()
        if text:
            self.engine.set_free_text(text, send=True)
            self._log(f"Free text sent: {text}")

    # ─── Decode Table ─────────────────────────────────────────────────────────

    @pyqtSlot(object)
    def _on_decode(self, d: WSJTXDecode):
        self.decode_table.add_decode(d)
        count = self.decode_table.rowCount()
        self.decode_count.setText(f"{count} decode{'s' if count != 1 else ''}")

    def _on_decode_clicked(self, row: int, col: int):
        d = self.decode_table.get_decode_at(row)
        if not d:
            return
        # Extract callsign from message
        parts = d.message.strip().split()
        # FT8 message formats: "CQ K1ABC EM72", "W2XYZ K1ABC -10", etc.
        call = ""
        if len(parts) >= 2:
            if parts[0] == "CQ" and len(parts) >= 2:
                call = parts[1]
                if len(parts) >= 3 and len(parts[2]) == 4:
                    self.dx_grid_edit.setText(parts[2])
            elif len(parts) >= 2:
                call = parts[1]

        if call:
            self.dx_call_edit.setText(call)
            self.ql_call.setText(call)
            self.ql_rst_s.setText(str(d.snr))
            self.ql_rst_r.setText(str(d.snr))
            self._selected_call = call

    def _on_decode_dblclick(self, row: int, col: int):
        """Double click = click decode + enable TX to reply."""
        self._on_decode_clicked(row, col)
        if self.dx_call_edit.text():
            self.btn_enable_tx.setChecked(True)
            self._toggle_tx(True)

    def _clear_decodes(self):
        self.decode_table.clear_decodes()
        self.decode_count.setText("0 decodes")

    # ─── Status Updates ───────────────────────────────────────────────────────

    @pyqtSlot(object)
    def _on_status(self, s: WSJTXStatus):
        self._current_status = s

        self.lbl_s_call.setText(f"DX: {s.dx_call or '—'}")
        self.lbl_s_grid.setText(f"Grid: {s.dx_grid or '—'}")
        self.lbl_s_freq.setText(f"Freq: {s.frequency/1e6:.3f}" if s.frequency else "Freq: —")
        self.lbl_s_mode.setText(f"Mode: {s.mode or '—'}")

        if s.transmitting:
            self.lbl_s_txrx.setText(" TX ")
            self.lbl_s_txrx.setStyleSheet(
                "background:#4a0000; color:#ff4400; font-weight:bold;"
                "border:1px solid #ff4400; border-radius:4px; padding:2px 10px;")
            self.cat.set_ptt(True)
        else:
            self.lbl_s_txrx.setText(" RX ")
            self.lbl_s_txrx.setStyleSheet(
                "background:#0d2b1a; color:#3fb950; font-weight:bold;"
                "border:1px solid #3fb950; border-radius:4px; padding:2px 10px;")
            if self.cat.ptt:
                self.cat.set_ptt(False)

        # Sync frequency to radio if enabled
        if self._settings.get("auto_qsy") and s.frequency:
            if abs(s.frequency - self.cat.frequency) > 500:
                self.cat.set_frequency(s.frequency)

        # Update band combo from frequency
        if s.frequency:
            band = CAT817.get_band(s.frequency)
            if band != "OOB":
                idx = self.band_combo.findText(band)
                if idx >= 0:
                    self.band_combo.blockSignals(True)
                    self.band_combo.setCurrentIndex(idx)
                    self.band_combo.blockSignals(False)

    # ─── QSO Logging ──────────────────────────────────────────────────────────

    @pyqtSlot(dict)
    def _on_qso_logged(self, qso: dict):
        """WSJT-X auto-logged a QSO via its internal logger."""
        if not self._settings.get("auto_log", True):
            return
        call = qso.get("callsign", "")
        if not call:
            return
        freq = qso.get("frequency", self.cat.frequency)
        contact = QSOContact(
            callsign  = call,
            frequency = freq,
            mode      = qso.get("mode", self.mode_combo.currentText()),
            band      = CAT817.get_band(freq),
            rst_sent  = qso.get("rst_sent", "-10"),
            rst_rcvd  = qso.get("rst_rcvd", "-10"),
            name      = qso.get("name", ""),
            grid      = qso.get("grid", ""),
            tx_pwr    = qso.get("tx_pwr", "5"),
            notes     = qso.get("notes", ""),
        )
        self.logger.add_contact(contact)
        self._log(f"✓ Auto-logged: {call} {contact.mode} {CAT817.get_band(freq)}")

    def _log_qso(self):
        """Manual quick-log from the Quick Log box."""
        call = self.ql_call.text().strip().upper()
        if not call:
            return
        freq = self.cat.frequency
        mode = self.mode_combo.currentText()
        contact = QSOContact(
            callsign  = call,
            frequency = freq,
            mode      = mode,
            band      = CAT817.get_band(freq),
            rst_sent  = self.ql_rst_s.text().strip() or "-10",
            rst_rcvd  = self.ql_rst_r.text().strip() or "-10",
            grid      = self.dx_grid_edit.text().strip().upper(),
            notes     = self.ql_notes.text().strip(),
            tx_pwr    = "5",
        )
        self.logger.add_contact(contact)
        self._log(f"✓ Logged: {call} {mode} {contact.band}")
        # Clear quick log
        self.ql_call.clear()
        self.ql_notes.clear()

    # ─── Engine Callbacks ─────────────────────────────────────────────────────

    def _on_engine_started(self):
        self.btn_start.setText("■  STOP ENGINE")
        self.engine_status.setText("⬤  Running")
        self.engine_status.setStyleSheet("color:#3fb950; font-weight:bold;")
        self._log("Engine started — waiting for WSJT-X to connect…")

    def _on_engine_stopped(self):
        self.btn_start.setText("▶  START ENGINE")
        self.btn_start.setChecked(False)
        self.engine_status.setText("⬤  Stopped")
        self.engine_status.setStyleSheet("color:#666; font-weight:bold;")
        self.hb_label.setText("◌ WSJT-X")
        self.hb_label.setStyleSheet("color:#444; font-size:10px; font-weight:bold;")
        self._log("Engine stopped")

    def _on_engine_error(self, msg: str):
        self.engine_status.setText(f"⚠  {msg[:40]}")
        self.engine_status.setStyleSheet("color:#f85149; font-weight:bold;")
        self.btn_start.setChecked(False)
        self._log(f"⚠ Error: {msg}")

    def _on_wsjt_connected(self, connected: bool):
        if connected:
            self.engine_status.setText("⬤  Connected")
            self.engine_status.setStyleSheet("color:#3fb950; font-weight:bold;")
            self._log("WSJT-X engine connected via UDP")
        else:
            self.engine_status.setText("⬤  Disconnected")
            self.engine_status.setStyleSheet("color:#d29922; font-weight:bold;")

    def _on_heartbeat(self, version: str):
        self.hb_label.setText(f"● WSJT-X {version}")
        self.hb_label.setStyleSheet("color:#3fb950; font-size:10px; font-weight:bold;")

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _log(self, msg: str):
        ts = datetime.datetime.utcnow().strftime("%H:%M:%S")
        self.activity_log.append(f"[{ts}] {msg}")
        doc = self.activity_log.document()
        while doc.blockCount() > 300:
            cursor = self.activity_log.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.select(cursor.SelectionType.LineUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()

    def _update_banner(self):
        has_call = bool(self._settings.get("callsign"))
        has_exe  = bool(self._settings.get("wsjtx_exe"))
        self.setup_banner.setVisible(not (has_call and has_exe))

    def closeEvent(self, event):
        if self.engine.is_running():
            self.engine.stop()
        super().closeEvent(event)
