"""
CAT Control Panel
Full radio control: frequency, mode, PTT, band selection, memory channels
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QPushButton, QComboBox, QLineEdit, QSpinBox,
    QDoubleSpinBox, QCheckBox, QSplitter, QSlider, QProgressBar,
    QFrame, QScrollArea, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSlot, QTimer
from PyQt6.QtGui import QFont

from core.cat817 import CAT817, MODE_NAMES, FT817Mode


BANDS = [
    ("160m",  1800000),
    ("80m",   3500000),
    ("60m",   5330500),
    ("40m",   7000000),
    ("30m",  10100000),
    ("20m",  14000000),
    ("17m",  18068000),
    ("15m",  21000000),
    ("12m",  24890000),
    ("10m",  28000000),
    ("6m",   50000000),
    ("2m",  144000000),
    ("70cm",430000000),
]

FT8_FREQS = {
    "160m":   1840000,
    "80m":    3573000,
    "60m":    5357000,
    "40m":    7074000,
    "30m":   10136000,
    "20m":   14074000,
    "17m":   18100000,
    "15m":   21074000,
    "12m":   24915000,
    "10m":   28074000,
    "6m":    50313000,
    "2m":   144174000,
}


class CATPanel(QWidget):
    def __init__(self, cat: CAT817, parent=None):
        super().__init__(parent)
        self.cat = cat
        self._build_ui()
        self._wire_signals()

    def _build_ui(self):
        # Outer layout holds the scroll area
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        # Inner container that actually holds everything
        container = QWidget()
        scroll.setWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # ── Top row: Connection ───────────────────────────────────────────────
        conn_box = QGroupBox("SERIAL CONNECTION")
        conn_layout = QHBoxLayout(conn_box)

        # Radio model selector
        conn_layout.addWidget(QLabel("Radio:"))
        self.radio_combo = QComboBox()
        from core.cat817 import RADIO_MODELS
        for key, info in RADIO_MODELS.items():
            self.radio_combo.addItem(info["name"], key)
        self.radio_combo.setToolTip("Select your Yaesu radio model")
        self.radio_combo.currentIndexChanged.connect(self._on_radio_changed)
        conn_layout.addWidget(self.radio_combo)

        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(100)
        self.port_combo.setToolTip("COM port for CAT cable")

        self.baud_combo = QComboBox()
        for b in [4800, 9600, 19200, 38400]:
            self.baud_combo.addItem(str(b), b)
        self.baud_combo.setCurrentIndex(1)
        self.baud_combo.setToolTip("Baud rate (default 9600)")

        self.btn_refresh = QPushButton("⟳")
        self.btn_refresh.setFixedWidth(32)
        self.btn_refresh.setToolTip("Rescan COM ports")
        self.btn_refresh.clicked.connect(self._refresh_ports)

        self.btn_connect = QPushButton("▶ CONNECT")
        self.btn_connect.setObjectName("btn_connect")
        self.btn_connect.setCheckable(True)
        self.btn_connect.clicked.connect(self._toggle_connect)

        self.conn_status = QLabel("⬤ Disconnected")
        self.conn_status.setStyleSheet("color: #666; font-weight: bold;")

        conn_layout.addWidget(QLabel("Port:"))
        conn_layout.addWidget(self.port_combo)
        conn_layout.addWidget(QLabel("Baud:"))
        conn_layout.addWidget(self.baud_combo)
        conn_layout.addWidget(self.btn_refresh)
        conn_layout.addWidget(self.btn_connect)
        conn_layout.addWidget(self.conn_status)
        conn_layout.addStretch()
        layout.addWidget(conn_box)

        # Radio info banner
        self.radio_info_label = QLabel("")
        self.radio_info_label.setStyleSheet(
            "font-size: 10px; color: #8b949e; padding: 2px 6px; "
            "background: #161b22; border-radius: 4px;"
        )
        self.radio_info_label.setWordWrap(True)
        layout.addWidget(self.radio_info_label)
        self._update_radio_info()

        # ── Middle: Main control grid ─────────────────────────────────────────
        mid_splitter = QSplitter(Qt.Orientation.Horizontal)
        mid_splitter.setChildrenCollapsible(False)
        layout.addWidget(mid_splitter, 1)

        # Left: Frequency + Mode
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Frequency entry
        freq_box = QGroupBox("FREQUENCY")
        freq_layout = QVBoxLayout(freq_box)

        # Manual frequency entry
        entry_row = QHBoxLayout()
        self.freq_entry = QLineEdit()
        self.freq_entry.setPlaceholderText("14.074000 MHz")
        self.freq_entry.setToolTip("Enter frequency in MHz, then press Enter")
        self.freq_entry.returnPressed.connect(self._set_freq_from_entry)

        self.btn_set_freq = QPushButton("Set →")
        self.btn_set_freq.clicked.connect(self._set_freq_from_entry)

        entry_row.addWidget(QLabel("MHz:"))
        entry_row.addWidget(self.freq_entry)
        entry_row.addWidget(self.btn_set_freq)
        freq_layout.addLayout(entry_row)

        # Band buttons
        band_label = QLabel("QUICK BANDS")
        band_label.setStyleSheet("font-size: 9px; letter-spacing: 1px; color: #888;")
        freq_layout.addWidget(band_label)

        band_grid = QGridLayout()
        band_grid.setSpacing(3)
        row, col = 0, 0
        for name, freq in BANDS:
            btn = QPushButton(name)
            btn.setMinimumHeight(26)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            btn.clicked.connect(lambda checked, f=freq: self._go_to_band(f))
            btn.setToolTip(f"{freq/1e6:.3f} MHz")
            band_grid.addWidget(btn, row, col)
            col += 1
            if col > 3:
                col = 0
                row += 1
        freq_layout.addLayout(band_grid)

        # FT8 quick-go
        ft8_row = QHBoxLayout()
        ft8_row.addWidget(QLabel("FT8:"))
        self.ft8_band_combo = QComboBox()
        for name, _ in BANDS:
            if name in FT8_FREQS:
                self.ft8_band_combo.addItem(name)
        ft8_row.addWidget(self.ft8_band_combo)
        btn_go_ft8 = QPushButton("Go →")
        btn_go_ft8.clicked.connect(self._go_ft8)
        ft8_row.addWidget(btn_go_ft8)
        ft8_row.addStretch()
        freq_layout.addLayout(ft8_row)

        # Tuning step
        step_row = QHBoxLayout()
        step_row.addWidget(QLabel("Step:"))
        self.step_combo = QComboBox()
        steps = ["10 Hz", "100 Hz", "500 Hz", "1 kHz", "5 kHz",
                 "10 kHz", "25 kHz", "100 kHz", "500 kHz", "1 MHz"]
        self.step_combo.addItems(steps)
        self.step_combo.setCurrentIndex(3)  # 1 kHz
        step_row.addWidget(self.step_combo)

        btn_step_dn = QPushButton("◀◀")
        btn_step_dn.setFixedWidth(40)
        btn_step_dn.clicked.connect(self._step_down)

        btn_step_up = QPushButton("▶▶")
        btn_step_up.setFixedWidth(40)
        btn_step_up.clicked.connect(self._step_up)

        step_row.addWidget(btn_step_dn)
        step_row.addWidget(btn_step_up)
        step_row.addStretch()
        freq_layout.addLayout(step_row)

        left_layout.addWidget(freq_box)

        # Mode selection
        mode_box = QGroupBox("MODE")
        mode_layout = QVBoxLayout(mode_box)

        mode_btn_row = QHBoxLayout()
        self.mode_buttons = {}
        modes_row1 = ["LSB", "USB", "CW", "CW-R"]
        modes_row2 = ["AM",  "FM",  "DIG", "PKT"]

        mode_grid = QGridLayout()
        mode_grid.setSpacing(4)
        all_modes = modes_row1 + modes_row2
        for i, mode in enumerate(all_modes):
            btn = QPushButton(mode)
            btn.setMinimumHeight(28)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, m=mode: self._set_mode(m))
            self.mode_buttons[mode] = btn
            mode_grid.addWidget(btn, i // 4, i % 4)
        mode_layout.addLayout(mode_grid)
        left_layout.addWidget(mode_box)
        left_layout.addStretch()
        mid_splitter.addWidget(left)

        # Right: PTT + Meters
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        # PTT
        ptt_box = QGroupBox("PTT CONTROL")
        ptt_layout = QVBoxLayout(ptt_box)

        self.btn_ptt = QPushButton("PTT\nTRANSMIT")
        self.btn_ptt.setObjectName("btn_ptt")
        self.btn_ptt.setCheckable(True)
        self.btn_ptt.setMinimumHeight(90)
        self.btn_ptt.clicked.connect(self._toggle_ptt)
        ptt_layout.addWidget(self.btn_ptt)

        # CW keyer placeholder
        cw_row = QHBoxLayout()
        self.chk_cw_keyer = QCheckBox("CW Keyer (via audio)")
        cw_row.addWidget(self.chk_cw_keyer)
        ptt_layout.addLayout(cw_row)

        right_layout.addWidget(ptt_box)

        # S-Meter
        smeter_box = QGroupBox("S-METER")
        smeter_layout = QVBoxLayout(smeter_box)

        self.smeter_bar = QProgressBar()
        self.smeter_bar.setRange(0, 15)
        self.smeter_bar.setValue(0)
        self.smeter_bar.setFormat("")
        self.smeter_bar.setMinimumHeight(16)
        smeter_layout.addWidget(self.smeter_bar)

        # S-meter scale labels
        scale_row = QHBoxLayout()
        for s in ["S1", "S3", "S5", "S7", "S9", "+20", "+40", "+60"]:
            lbl = QLabel(s)
            lbl.setStyleSheet("font-size: 9px; color: #666;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            scale_row.addWidget(lbl)
        smeter_layout.addLayout(scale_row)

        self.smeter_label = QLabel("S0")
        self.smeter_label.setStyleSheet(
            "font-family: Consolas; font-size: 24px; font-weight: bold; text-align: center;")
        self.smeter_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        smeter_layout.addWidget(self.smeter_label)

        right_layout.addWidget(smeter_box)

        # TX Power control
        pwr_box = QGroupBox("TX POWER")
        pwr_layout = QHBoxLayout(pwr_box)
        pwr_layout.addWidget(QLabel("Power:"))
        self.pwr_combo = QComboBox()
        self._rebuild_power_combo()
        pwr_layout.addWidget(self.pwr_combo)
        pwr_layout.addStretch()
        right_layout.addWidget(pwr_box)

        right_layout.addStretch()
        mid_splitter.addWidget(right)
        mid_splitter.setStretchFactor(0, 3)
        mid_splitter.setStretchFactor(1, 2)

        # ── Bottom: Memory/Quick recall ───────────────────────────────────────
        mem_box = QGroupBox("MEMORY CHANNELS  (Click to QSY)")
        mem_layout = QGridLayout(mem_box)
        mem_layout.setSpacing(4)

        MEMORIES = [
            ("FT8 20m",  14074000, "USB"),
            ("FT8 40m",   7074000, "USB"),
            ("FT8 15m",  21074000, "USB"),
            ("FT8 17m",  18100000, "USB"),
            ("FT4 20m",  14080000, "USB"),
            ("WSPR 20m", 14095600, "USB"),
            ("JS8 20m",  14078000, "USB"),
            ("CW 20m",   14025000, "CW"),
        ]
        for i, (name, freq, mode) in enumerate(MEMORIES):
            btn = QPushButton(f"{name}\n{freq/1e6:.3f}")
            btn.setMinimumHeight(44)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            btn.setToolTip(f"{name} — {freq/1e6:.6f} MHz — {mode}")
            btn.clicked.connect(lambda chk, f=freq, m=mode: self._recall_memory(f, m))
            mem_layout.addWidget(btn, i // 4, i % 4)

        layout.addWidget(mem_box)

        # Initial port scan
        self._refresh_ports()

    # ─── Signal Wiring ────────────────────────────────────────────────────────

    def _wire_signals(self):
        self.cat.connected.connect(self._on_connected)
        self.cat.frequency_changed.connect(self._on_freq_changed)
        self.cat.mode_changed.connect(self._on_mode_changed)
        self.cat.ptt_changed.connect(self._on_ptt_changed)
        self.cat.smeter_updated.connect(self._on_smeter)

    # ─── Radio Model ──────────────────────────────────────────────────────────

    def _on_radio_changed(self):
        key = self.radio_combo.currentData()
        self.cat.set_radio_model(key)
        self._rebuild_power_combo()
        self._update_radio_info()

    def _rebuild_power_combo(self):
        self.pwr_combo.clear()
        for p in self.cat.power_steps:
            self.pwr_combo.addItem(p)

    def _update_radio_info(self):
        info = self.cat.radio_info
        self.radio_info_label.setText(
            f"📡  {info['name']}  —  Max power: {info['max_power']}W  —  {info['notes']}"
        )

    # ─── Port Management ──────────────────────────────────────────────────────

    def _refresh_ports(self):
        self.port_combo.clear()
        ports = CAT817.list_ports()
        if ports:
            self.port_combo.addItems(ports)
        else:
            self.port_combo.addItem("(No ports found)")

    def _toggle_connect(self, checked: bool):
        if checked:
            port = self.port_combo.currentText()
            baud = self.baud_combo.currentData()
            success = self.cat.connect(port, baud)
            if not success:
                self.btn_connect.setChecked(False)
        else:
            self.cat.disconnect()

    # ─── Frequency Control ────────────────────────────────────────────────────

    def _set_freq_from_entry(self):
        text = self.freq_entry.text().strip().replace(",", ".")
        try:
            mhz = float(text)
            hz  = int(mhz * 1e6)
            if 100000 <= hz <= 500000000:
                self.cat.set_frequency(hz)
        except ValueError:
            pass

    def _go_to_band(self, freq_hz: int):
        self.cat.set_frequency(freq_hz)

    def _go_ft8(self):
        band = self.ft8_band_combo.currentText()
        freq = FT8_FREQS.get(band)
        if freq:
            self.cat.set_frequency(freq)
            self.cat.set_mode("USB")

    def _step_up(self):
        step = self._get_step_hz()
        self.cat.set_frequency(self.cat.frequency + step)

    def _step_down(self):
        step = self._get_step_hz()
        self.cat.set_frequency(max(100000, self.cat.frequency - step))

    def _get_step_hz(self) -> int:
        steps_hz = [10, 100, 500, 1000, 5000, 10000, 25000, 100000, 500000, 1000000]
        idx = self.step_combo.currentIndex()
        return steps_hz[idx] if idx < len(steps_hz) else 1000

    # ─── Mode Control ─────────────────────────────────────────────────────────

    def _set_mode(self, mode: str):
        self.cat.set_mode(mode)

    def _recall_memory(self, freq: int, mode: str):
        self.cat.set_frequency(freq)
        self.cat.set_mode(mode)

    # ─── PTT ──────────────────────────────────────────────────────────────────

    def _toggle_ptt(self, checked: bool):
        self.cat.set_ptt(checked)

    # ─── CAT Callbacks ────────────────────────────────────────────────────────

    @pyqtSlot(bool)
    def _on_connected(self, connected: bool):
        if connected:
            self.conn_status.setText("⬤ Connected")
            self.conn_status.setStyleSheet("color: #3fb950; font-weight: bold;")
            self.btn_connect.setText("■ DISCONNECT")
            self.btn_connect.setChecked(True)
        else:
            self.conn_status.setText("⬤ Disconnected")
            self.conn_status.setStyleSheet("color: #666; font-weight: bold;")
            self.btn_connect.setText("▶ CONNECT")
            self.btn_connect.setChecked(False)
            self.btn_ptt.setChecked(False)

    @pyqtSlot(int)
    def _on_freq_changed(self, freq_hz: int):
        self.freq_entry.setText(f"{freq_hz / 1e6:.6f}")

    @pyqtSlot(str)
    def _on_mode_changed(self, mode: str):
        for name, btn in self.mode_buttons.items():
            btn.setChecked(name == mode)

    @pyqtSlot(bool)
    def _on_ptt_changed(self, tx: bool):
        self.btn_ptt.setChecked(tx)
        if tx:
            self.btn_ptt.setText("■ TX\nACTIVE")
        else:
            self.btn_ptt.setText("PTT\nTRANSMIT")

    @pyqtSlot(int)
    def _on_smeter(self, value: int):
        self.smeter_bar.setValue(value)
        if value <= 9:
            self.smeter_label.setText(f"S{value}")
        else:
            over = (value - 9) * 6  # Rough dB over S9
            self.smeter_label.setText(f"S9+{over:02d}")
