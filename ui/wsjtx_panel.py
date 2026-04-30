"""
WSJT-X Digital Modes Panel
FT8, FT4, JS8, WSPR, JT65 integration
"""

import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QPushButton, QComboBox, QLineEdit, QTableWidget, QTableWidgetItem,
    QTextEdit, QSplitter, QHeaderView, QCheckBox, QSpinBox, QFrame
)
from PyQt6.QtCore import Qt, pyqtSlot, QTimer
from PyQt6.QtGui import QColor, QFont

from core.wsjtx_interface import WSJTXInterface, DIGITAL_MODES, WSJTXDecode, WSJTXStatus
from core.cat817 import CAT817
from core.logger import ContactLogger, QSOContact


# Colour coding for decode table
SNR_COLORS_DARK = {
    "great":  "#1a4731",   # > 0 dB  — green
    "good":   "#1a3a1a",   # > -10
    "fair":   "#2d2a1a",   # > -15
    "weak":   "#2a1a1a",   # > -20
    "vweak":  "#1a1a2a",   # ≤ -20
}


class DecodeTable(QTableWidget):
    """Decoded signals table."""
    COLS = ["Time", "SNR", "ΔT", "ΔF", "Mode", "Message"]

    def __init__(self, parent=None):
        super().__init__(0, len(self.COLS), parent)
        self.setHorizontalHeaderLabels(self.COLS)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.setWordWrap(False)
        self.setShowGrid(True)

        hh = self.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)

    def add_decode(self, d: WSJTXDecode):
        """Add a decode to the table (newest at top)."""
        self.insertRow(0)

        t = d.time
        time_str = f"{t//10000:02d}:{(t%10000)//100:02d}:{t%100:02d}"
        snr_str  = f"{d.snr:+d}"
        dt_str   = f"{d.delta_time:+.1f}"
        df_str   = f"{d.delta_freq}"

        values = [time_str, snr_str, dt_str, df_str, d.mode, d.message]
        for col, val in enumerate(values):
            item = QTableWidgetItem(str(val))
            item.setFont(QFont("Consolas", 10))
            self.setItem(0, col, item)

        # Colour by SNR
        if d.snr > 0:
            bg = SNR_COLORS_DARK["great"]
        elif d.snr > -10:
            bg = SNR_COLORS_DARK["good"]
        elif d.snr > -15:
            bg = SNR_COLORS_DARK["fair"]
        elif d.snr > -20:
            bg = SNR_COLORS_DARK["weak"]
        else:
            bg = SNR_COLORS_DARK["vweak"]

        color = QColor(bg)
        for col in range(len(self.COLS)):
            if self.item(0, col):
                self.item(0, col).setBackground(color)

        # Keep max 500 rows
        while self.rowCount() > 500:
            self.removeRow(self.rowCount() - 1)


class WSJTXPanel(QWidget):
    def __init__(self, wsjtx: WSJTXInterface, cat: CAT817, logger: ContactLogger, parent=None):
        super().__init__(parent)
        self.wsjtx  = wsjtx
        self.cat    = cat
        self.logger = logger
        self._build_ui()
        self._wire_signals()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # ── Top: Connection + Mode ────────────────────────────────────────────
        top_row = QHBoxLayout()
        layout.addLayout(top_row)

        # WSJT-X Connection
        conn_box = QGroupBox("WSJT-X CONNECTION")
        conn_layout = QHBoxLayout(conn_box)

        conn_layout.addWidget(QLabel("UDP Port:"))
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1024, 65535)
        self.port_spin.setValue(2237)
        conn_layout.addWidget(self.port_spin)

        self.btn_listen = QPushButton("▶ START LISTENER")
        self.btn_listen.setObjectName("btn_connect")
        self.btn_listen.setCheckable(True)
        self.btn_listen.clicked.connect(self._toggle_listener)
        conn_layout.addWidget(self.btn_listen)

        self.wsjtx_status = QLabel("⬤ Offline")
        self.wsjtx_status.setStyleSheet("color: #666; font-weight: bold;")
        conn_layout.addWidget(self.wsjtx_status)

        conn_layout.addWidget(QLabel(" | "))

        self.btn_launch = QPushButton("🚀 Launch WSJT-X")
        self.btn_launch.clicked.connect(self._launch_wsjtx)
        conn_layout.addWidget(self.btn_launch)

        wsjtx_path_label = QLabel("Path:")
        conn_layout.addWidget(wsjtx_path_label)
        self.wsjtx_path = QLineEdit(r"C:\WSJT\wsjtx\bin\wsjtx.exe")
        self.wsjtx_path.setMinimumWidth(200)
        conn_layout.addWidget(self.wsjtx_path)
        conn_layout.addStretch()
        top_row.addWidget(conn_box)

        # Mode Info
        mode_box = QGroupBox("MODE REFERENCE")
        mode_layout = QVBoxLayout(mode_box)
        self.mode_select = QComboBox()
        for name in DIGITAL_MODES:
            self.mode_select.addItem(name)
        self.mode_select.currentTextChanged.connect(self._show_mode_info)
        mode_layout.addWidget(self.mode_select)
        self.mode_info = QLabel()
        self.mode_info.setWordWrap(True)
        self.mode_info.setStyleSheet("font-size: 10px; color: #8b949e;")
        mode_layout.addWidget(self.mode_info)

        btn_qsy_mode = QPushButton("QSY to this mode/band →")
        btn_qsy_mode.clicked.connect(self._qsy_to_mode)
        mode_layout.addWidget(btn_qsy_mode)

        top_row.addWidget(mode_box)

        # ── WSJT-X Live Status ────────────────────────────────────────────────
        status_box = QGroupBox("WSJT-X LIVE STATUS")
        status_layout = QHBoxLayout(status_box)

        for label_id, label_text in [
            ("lbl_wfreq",  "Freq: —"),
            ("lbl_wmode",  "Mode: —"),
            ("lbl_wdx",    "DX: —"),
            ("lbl_wgrid",  "Grid: —"),
            ("lbl_wtx",    "TX: —"),
        ]:
            lbl = QLabel(label_text)
            lbl.setStyleSheet("font-family: Consolas; font-size: 11px; padding: 0 8px;")
            setattr(self, label_id, lbl)
            status_layout.addWidget(lbl)
            if label_id != "lbl_wtx":
                sep = QFrame()
                sep.setFrameShape(QFrame.Shape.VLine)
                status_layout.addWidget(sep)
        status_layout.addStretch()
        layout.addWidget(status_box)

        # ── Splitter: Decodes + Log console ───────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter, 1)

        # Decode table
        decode_widget = QWidget()
        decode_layout = QVBoxLayout(decode_widget)
        decode_layout.setContentsMargins(0, 0, 0, 0)

        decode_header = QHBoxLayout()
        decode_header.addWidget(QLabel("📶  DECODED SIGNALS"))
        decode_header.addStretch()

        self.chk_auto_log = QCheckBox("Auto-log CQ replies")
        self.chk_auto_log.setToolTip("Automatically add contacts to log when WSJT-X logs them")
        self.chk_auto_log.setChecked(True)
        decode_header.addWidget(self.chk_auto_log)

        btn_clear = QPushButton("Clear")
        btn_clear.clicked.connect(lambda: self.decode_table.setRowCount(0))
        decode_header.addWidget(btn_clear)
        decode_layout.addLayout(decode_header)

        self.decode_table = DecodeTable()
        decode_layout.addWidget(self.decode_table)
        splitter.addWidget(decode_widget)

        # Activity log
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.addWidget(QLabel("📋  ACTIVITY LOG"))
        self.activity_log = QTextEdit()
        self.activity_log.setReadOnly(True)
        self.activity_log.setFont(QFont("Consolas", 10))
        self.activity_log.setMaximumHeight(150)
        log_layout.addWidget(self.activity_log)
        splitter.addWidget(log_widget)

        splitter.setSizes([400, 150])

        # ── Frequency Quick-Set ────────────────────────────────────────────────
        qsy_box = QGroupBox("QUICK QSY — DIGITAL FREQUENCIES")
        qsy_layout = QHBoxLayout(qsy_box)

        from core.cat817 import CAT817
        quick_freqs = [
            ("FT8 20m",  14074000, "USB"),
            ("FT8 40m",   7074000, "USB"),
            ("FT8 15m",  21074000, "USB"),
            ("FT8 17m",  18100000, "USB"),
            ("FT4 20m",  14080000, "USB"),
            ("WSPR 20m", 14095600, "USB"),
            ("JS8 20m",  14078000, "USB"),
            ("JT65 20m", 14076000, "USB"),
        ]
        for name, freq, mode in quick_freqs:
            btn = QPushButton(name)
            btn.setFixedHeight(32)
            btn.setToolTip(f"{freq/1e6:.3f} MHz — {mode}")
            btn.clicked.connect(lambda chk, f=freq, m=mode: self._qsy(f, m))
            qsy_layout.addWidget(btn)

        layout.addWidget(qsy_box)

        # Initialise mode info
        self._show_mode_info(self.mode_select.currentText())

    # ─── Signal Wiring ────────────────────────────────────────────────────────

    def _wire_signals(self):
        self.wsjtx.connected.connect(self._on_connected)
        self.wsjtx.decode_received.connect(self._on_decode)
        self.wsjtx.status_received.connect(self._on_status)
        self.wsjtx.qso_logged.connect(self._on_qso_logged)
        self.wsjtx.heartbeat.connect(self._on_heartbeat)
        self.wsjtx.status_message.connect(self._log)

    # ─── Actions ──────────────────────────────────────────────────────────────

    def _toggle_listener(self, checked: bool):
        if checked:
            port = self.port_spin.value()
            success = self.wsjtx.start_listening(port)
            if success:
                self.btn_listen.setText("■ STOP LISTENER")
                self._log(f"UDP listener started on port {port}")
            else:
                self.btn_listen.setChecked(False)
        else:
            self.wsjtx.stop_listening()
            self.btn_listen.setText("▶ START LISTENER")
            self._log("UDP listener stopped")

    def _launch_wsjtx(self):
        path = self.wsjtx_path.text().strip()
        self.wsjtx.launch_wsjtx(path)

    def _show_mode_info(self, mode_name: str):
        info = DIGITAL_MODES.get(mode_name, {})
        period = info.get("period")
        bw     = info.get("bandwidth")
        desc   = info.get("description", "")
        parts  = []
        if period:
            parts.append(f"Period: {period}s")
        if bw:
            parts.append(f"BW: {bw}Hz")
        self.mode_info.setText(f"{desc}\n{' | '.join(parts)}" if parts else desc)

    def _qsy_to_mode(self):
        mode_name = self.mode_select.currentText()
        band = CAT817.get_band(self.cat.frequency)
        freq = CAT817.get_digital_freq(band, mode_name)
        if freq:
            self._qsy(freq, "USB")
            self._log(f"QSY to {mode_name} on {band}: {freq/1e6:.3f} MHz")
        else:
            self._log(f"No standard frequency for {mode_name} on {band}")

    def _qsy(self, freq: int, mode: str):
        self.cat.set_frequency(freq)
        self.cat.set_mode(mode)

    # ─── Callbacks ────────────────────────────────────────────────────────────

    @pyqtSlot(bool)
    def _on_connected(self, connected: bool):
        if connected:
            self.wsjtx_status.setText("⬤ Live")
            self.wsjtx_status.setStyleSheet("color: #3fb950; font-weight: bold;")
        else:
            self.wsjtx_status.setText("⬤ Offline")
            self.wsjtx_status.setStyleSheet("color: #666; font-weight: bold;")

    @pyqtSlot(object)
    def _on_decode(self, d: WSJTXDecode):
        self.decode_table.add_decode(d)

    @pyqtSlot(object)
    def _on_status(self, s: WSJTXStatus):
        self.lbl_wfreq.setText(f"Freq: {s.frequency/1e6:.3f} MHz" if s.frequency else "Freq: —")
        self.lbl_wmode.setText(f"Mode: {s.mode or '—'}")
        self.lbl_wdx.setText(f"DX: {s.dx_call or '—'}")
        self.lbl_wgrid.setText(f"Grid: {s.dx_grid or '—'}")
        tx_text = "TX 🔴" if s.transmitting else ("DECODING" if s.decoding else "RX")
        self.lbl_wtx.setText(f"State: {tx_text}")

        # Sync frequency to radio
        if s.frequency and abs(s.frequency - self.cat.frequency) > 100:
            self.cat.set_frequency(s.frequency)

    @pyqtSlot(dict)
    def _on_qso_logged(self, qso: dict):
        call = qso.get("callsign", "?")
        mode = qso.get("mode", "?")
        self._log(f"✓ QSO logged: {call} via {mode}")

    @pyqtSlot(str)
    def _on_heartbeat(self, version: str):
        self._log(f"WSJT-X heartbeat — version {version}")

    def _log(self, message: str):
        ts = datetime.datetime.utcnow().strftime("%H:%M:%S")
        self.activity_log.append(f"[{ts}] {message}")


from core.cat817 import CAT817
