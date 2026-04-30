"""
Main Application Window
Yaesu FT-8XX Suite by K3LH — tabbed radio control interface
"""

import datetime
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QStatusBar, QLabel, QToolBar, QSizePolicy, QSplitter, QMessageBox,
    QFileDialog, QMenuBar, QMenu, QFrame
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QFont, QKeySequence, QAction

from ui.theme import theme_manager, THEMES
from ui.cat_panel import CATPanel
from ui.audio_panel import AudioPanel
from ui.digital_modes_panel import DigitalModesPanel
from ui.log_panel import LogPanel
from ui.waterfall_widget import WaterfallWidget
from ui.spotter_panel import SpotterPanel
from ui.help_window import HelpWindow
from core.cat817 import CAT817
from core.audio_engine import AudioEngine
from core.logger import ContactLogger, QSOContact


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # ─── Core Objects ────────────────────────────────────────────────────
        self.cat     = CAT817(self)
        self.audio   = AudioEngine(self)
        self.logger  = ContactLogger("qso_log.json", self)

        # ─── Window Setup ────────────────────────────────────────────────────
        self.setWindowTitle("Yaesu FT-8XX Suite by K3LH  v2.1.0  ◈  Amateur Radio Control")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)

        # Apply initial theme
        theme_manager.apply_theme()
        theme_manager.theme_changed.connect(self._on_theme_changed)

        # ─── Menu Bar ────────────────────────────────────────────────────────
        self._build_menu()

        # ─── Tool Bar ────────────────────────────────────────────────────────
        self._build_toolbar()

        # ─── Central Widget ───────────────────────────────────────────────────
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 4, 8, 4)
        main_layout.setSpacing(6)

        # ─── Top: Radio Status Bar ────────────────────────────────────────────
        self._build_radio_header(main_layout)

        # ─── Splitter: Left=Waterfall, Right=Tabs ─────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        main_layout.addWidget(splitter, 1)

        # Waterfall (left pane)
        left_pane = QWidget()
        left_pane.setMinimumWidth(180)
        left_layout = QVBoxLayout(left_pane)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        wf_label = QLabel("◈ SPECTRUM / WATERFALL")
        wf_label.setStyleSheet("font-size: 10px; font-weight: bold; letter-spacing: 2px; padding: 2px 4px;")
        left_layout.addWidget(wf_label)

        self.waterfall = WaterfallWidget()
        self.waterfall.setMinimumHeight(150)
        left_layout.addWidget(self.waterfall, 1)
        splitter.addWidget(left_pane)

        # Tabs (right pane)
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs.setMinimumWidth(400)
        splitter.addWidget(self.tabs)

        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 5)
        splitter.setSizes([300, 900])

        # ─── Build Tabs ───────────────────────────────────────────────────────
        self.cat_panel      = CATPanel(self.cat)
        self.audio_panel    = AudioPanel(self.audio, self.cat)
        self.digital_panel  = DigitalModesPanel(self.cat, self.logger)
        self.log_panel      = LogPanel(self.logger, self.cat)
        self.spotter_panel  = SpotterPanel(self.cat, self.logger)

        self.tabs.addTab(self.cat_panel,     "📡  CAT Control")
        self.tabs.addTab(self.audio_panel,   "🔊  Audio")
        self.tabs.addTab(self.digital_panel, "📶  Digital Modes")
        self.tabs.addTab(self.spotter_panel, "🗺  Spotters")
        self.tabs.addTab(self.log_panel,     "📒  Log")

        # ─── Status Bar ───────────────────────────────────────────────────────
        self._build_statusbar()

        # ─── Cross-component wiring ───────────────────────────────────────────
        self._wire_signals()

        # ─── UTC Clock ────────────────────────────────────────────────────────
        self._utc_timer = QTimer()
        self._utc_timer.timeout.connect(self._update_utc)
        self._utc_timer.start(1000)

        # Connect waterfall to audio engine
        self.audio.fft_updated.connect(self.waterfall.update_fft)

    # ─── Menu Bar ─────────────────────────────────────────────────────────────

    def _build_menu(self):
        mb = self.menuBar()

        # File
        file_menu = mb.addMenu("&File")
        act_export = QAction("Export Log (ADIF)…", self)
        act_export.setShortcut(QKeySequence("Ctrl+E"))
        act_export.triggered.connect(self._export_adif)
        file_menu.addAction(act_export)

        act_import = QAction("Import Log (ADIF)…", self)
        act_import.triggered.connect(self._import_adif)
        file_menu.addAction(act_import)

        file_menu.addSeparator()
        act_quit = QAction("Quit", self)
        act_quit.setShortcut(QKeySequence("Ctrl+Q"))
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        # View / Theme
        view_menu = mb.addMenu("&View")
        for name, info in THEMES.items():
            act = QAction(f"{info['icon']}  {info['name']} Mode", self)
            act.triggered.connect(lambda checked, n=name: theme_manager.set_theme(n))
            view_menu.addAction(act)

        # Radio
        radio_menu = mb.addMenu("&Radio")
        act_connect = QAction("Connect Radio…", self)
        act_connect.triggered.connect(lambda: self.tabs.setCurrentWidget(self.cat_panel))
        radio_menu.addAction(act_connect)

        # Help
        help_menu = mb.addMenu("&Help")

        act_guide = QAction("📖  How-To Guide", self)
        act_guide.setShortcut(QKeySequence("F1"))
        act_guide.setToolTip("Open the full user guide (F1)")
        act_guide.triggered.connect(self._show_help)
        help_menu.addAction(act_guide)

        help_menu.addSeparator()

        act_about = QAction("About Yaesu FT-8XX Suite by K3LH", self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)

    # ─── Toolbar ──────────────────────────────────────────────────────────────

    def _build_toolbar(self):
        tb = QToolBar("Main Toolbar")
        tb.setMovable(False)
        self.addToolBar(tb)

        # Theme buttons
        for name, info in THEMES.items():
            act = QAction(f"{info['icon']} {info['name']}", self)
            act.triggered.connect(lambda checked, n=name: theme_manager.set_theme(n))
            tb.addAction(act)

        tb.addSeparator()

        # Quick tab navigation
        for i, label in enumerate(["📡 CAT", "🔊 Audio", "📶 Digital", "🗺 Spotters", "📒 Log"]):
            act = QAction(label, self)
            act.triggered.connect(lambda checked, idx=i: self.tabs.setCurrentIndex(idx))
            tb.addAction(act)

    # ─── Radio Header (frequency display) ─────────────────────────────────────

    def _build_radio_header(self, layout):
        header = QWidget()
        header.setMinimumHeight(70)
        header.setMaximumHeight(100)
        h = QHBoxLayout(header)
        h.setContentsMargins(4, 4, 4, 4)
        h.setSpacing(16)

        # Big frequency display
        self.freq_label = QLabel("14.074.000")
        self.freq_label.setObjectName("freq_display")
        self.freq_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.freq_label.setMinimumWidth(200)
        self.freq_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        h.addWidget(self.freq_label)

        # Mode + Band column
        vinfo = QVBoxLayout()
        vinfo.setSpacing(2)
        self.mode_label = QLabel("USB")
        self.mode_label.setObjectName("mode_label")
        self.band_label = QLabel("20m")
        self.band_label.setObjectName("band_label")
        vinfo.addWidget(self.mode_label)
        vinfo.addWidget(self.band_label)
        h.addLayout(vinfo)

        # TX/RX indicator
        self.trx_label = QLabel("RX")
        self.trx_label.setObjectName("status_indicator")
        self.trx_label.setMinimumSize(50, 30)
        self.trx_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.trx_label.setProperty("class", "status_rx")
        h.addWidget(self.trx_label)

        h.addStretch()

        # ── Voltage display ───────────────────────────────────────────────────
        vvolt = QVBoxLayout()
        vvolt.setSpacing(0)
        volt_lbl = QLabel("SUPPLY")
        volt_lbl.setStyleSheet("font-size: 9px; color: #666; letter-spacing: 2px;")
        volt_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.voltage_label = QLabel("--.- V")
        self.voltage_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.voltage_label.setStyleSheet(
            "font-family: Consolas, monospace; font-size: 18px; "
            "font-weight: bold; color: #3fb950;"
        )
        self.voltage_label.setMinimumWidth(80)
        self.voltage_label.setToolTip("Supply voltage read from radio (updates every 10s)")
        vvolt.addWidget(volt_lbl)
        vvolt.addWidget(self.voltage_label)
        h.addLayout(vvolt)

        # Thin vertical separator
        from PyQt6.QtWidgets import QFrame as QF
        sep = QF()
        sep.setFrameShape(QF.Shape.VLine)
        sep.setStyleSheet("color: #30363d;")
        h.addWidget(sep)

        # UTC clock
        vutc = QVBoxLayout()
        vutc.setSpacing(0)
        utc_lbl = QLabel("UTC")
        utc_lbl.setStyleSheet("font-size: 9px; color: #666; letter-spacing: 2px;")
        self.utc_label = QLabel("00:00:00")
        self.utc_label.setStyleSheet("font-family: Consolas, monospace; font-size: 18px; font-weight: bold;")
        vutc.addWidget(utc_lbl)
        vutc.addWidget(self.utc_label)
        h.addLayout(vutc)

        # Connection status
        self.conn_label = QLabel("● OFFLINE")
        self.conn_label.setStyleSheet("color: #666; font-size: 11px; font-weight: bold;")
        h.addWidget(self.conn_label)

        layout.addWidget(header)

        # Separator line
        from PyQt6.QtWidgets import QFrame
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(line)

    # ─── Status Bar ───────────────────────────────────────────────────────────

    def _build_statusbar(self):
        sb = self.statusBar()

        self.sb_radio   = QLabel("Radio: Disconnected")
        self.sb_audio   = QLabel("Audio: Stopped")
        self.sb_wsjtx   = QLabel("WSJT-X: Offline")
        self.sb_qso_cnt = QLabel(f"QSOs: {self.logger.count()}")

        for w in [self.sb_radio, self.sb_audio, self.sb_wsjtx, self.sb_qso_cnt]:
            sb.addPermanentWidget(w)
            sep = QLabel("|")
            sep.setStyleSheet("color: #444;")
            sb.addPermanentWidget(sep)

    # ─── Signal Wiring ────────────────────────────────────────────────────────

    def _wire_signals(self):
        # CAT → UI
        self.cat.connected.connect(self._on_cat_connected)
        self.cat.frequency_changed.connect(self._on_frequency_changed)
        self.cat.mode_changed.connect(self._on_mode_changed)
        self.cat.ptt_changed.connect(self._on_ptt_changed)
        self.cat.voltage_updated.connect(self._on_voltage_updated)
        self.cat.status_message.connect(self.statusBar().showMessage)

        # Audio → UI
        self.audio.status_message.connect(lambda m: self.sb_audio.setText(f"Audio: {m[:40]}"))
        self.audio.vox_triggered.connect(self.cat.set_ptt)

        # Digital engine → status bar
        self.digital_panel.engine.connected.connect(
            lambda c: self.sb_wsjtx.setText("Engine: " + ("Running" if c else "Stopped")))
        self.digital_panel.engine.status_message.connect(self.statusBar().showMessage)

        # Logger → UI
        self.logger.contact_added.connect(lambda: self.sb_qso_cnt.setText(f"QSOs: {self.logger.count()}"))

    # ─── Slots ────────────────────────────────────────────────────────────────

    @pyqtSlot(bool)
    def _on_cat_connected(self, connected: bool):
        if connected:
            self.conn_label.setText("● ONLINE")
            self.conn_label.setStyleSheet("color: #3fb950; font-size: 11px; font-weight: bold;")
            self.sb_radio.setText("Radio: Connected")
        else:
            self.conn_label.setText("● OFFLINE")
            self.conn_label.setStyleSheet("color: #666; font-size: 11px; font-weight: bold;")
            self.sb_radio.setText("Radio: Disconnected")
            self.trx_label.setText("RX")
            # Clear voltage when disconnected
            self.voltage_label.setText("--.- V")
            self.voltage_label.setStyleSheet(
                "font-family: Consolas, monospace; font-size: 18px; "
                "font-weight: bold; color: #484f58;"
            )

    @pyqtSlot(float)
    def _on_voltage_updated(self, volts: float):
        self.voltage_label.setText(f"{volts:.1f} V")
        # Colour-code by voltage level
        # FT-817/818 internal: ~9.6V full, ~8.0V low
        # External 13.8V DC: normal operating
        if volts >= 13.0:
            color = "#3fb950"   # Green  — external supply / full charge
        elif volts >= 11.5:
            color = "#58a6ff"   # Blue   — good
        elif volts >= 10.0:
            color = "#d29922"   # Amber  — getting low
        elif volts >= 8.5:
            color = "#f85149"   # Red    — low battery
        else:
            color = "#ff0000"   # Bright red — critical
        self.voltage_label.setStyleSheet(
            f"font-family: Consolas, monospace; font-size: 18px; "
            f"font-weight: bold; color: {color};"
        )

    @pyqtSlot(int)
    def _on_frequency_changed(self, freq_hz: int):
        self.freq_label.setText(CAT817.format_frequency(freq_hz))
        band = CAT817.get_band(freq_hz)
        self.band_label.setText(band)

    @pyqtSlot(str)
    def _on_mode_changed(self, mode: str):
        self.mode_label.setText(mode)

    @pyqtSlot(bool)
    def _on_ptt_changed(self, tx: bool):
        if tx:
            self.trx_label.setText("TX")
            self.trx_label.setStyleSheet(
                "background:#da3633; color:#fff; font-weight:bold; border-radius:4px; padding:3px 10px;")
        else:
            self.trx_label.setText("RX")
            self.trx_label.setStyleSheet(
                "background:#238636; color:#3fb950; font-weight:bold; border-radius:4px; padding:3px 10px;")

    def _update_utc(self):
        self.utc_label.setText(datetime.datetime.utcnow().strftime("%H:%M:%S"))

    def _on_theme_changed(self, name: str):
        # Waterfall picks up theme automatically via repaint
        self.waterfall.update()

    # ─── Actions ──────────────────────────────────────────────────────────────

    def _export_adif(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export ADIF Log", "qso_log.adi", "ADIF Files (*.adi *.adif)"
        )
        if path:
            if self.logger.export_adif(path):
                self.statusBar().showMessage(f"Exported {self.logger.count()} QSOs to {path}")
            else:
                QMessageBox.warning(self, "Export Failed", "Could not write ADIF file.")

    def _import_adif(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import ADIF Log", "", "ADIF Files (*.adi *.adif);;All Files (*)"
        )
        if path:
            count = self.logger.import_adif(path)
            self.statusBar().showMessage(f"Imported {count} QSOs from {path}")

    def _show_help(self):
        dlg = HelpWindow(self)
        dlg.exec()

    def _show_about(self):
        QMessageBox.about(self, "About Yaesu FT-8XX Suite by K3LH",
            "<h2>Yaesu FT-8XX Suite by K3LH  v2.1.0</h2>"
            "<p>Yaesu FT-8XX Suite by K3LH</p>"
            "<p><b>Supported radios:</b><br>"
            "• Yaesu FT-817 / FT-817ND (5W)<br>"
            "• Yaesu FT-818 / FT-818ND (6W)<br>"
            "• Yaesu FT-857 / FT-857D (100W)<br>"
            "• Yaesu FT-897 / FT-897D (100W)</p>"
            "<p><b>Features:</b><br>"
            "• CAT control — frequency, mode, PTT, S-meter<br>"
            "• Digirig Mobile / USB audio interface support<br>"
            "• Integrated FT8, FT4, JS8, WSPR (hidden WSJT-X engine)<br>"
            "• POTA, DX Cluster, RBN spotting networks<br>"
            "• QSO logging with ADIF export<br>"
            "• Dark, Light and Night display themes</p>"
            "<p>Press <b>F1</b> or use <b>Help → How-To Guide</b> for full documentation.</p>"
        )

    def closeEvent(self, event):
        """Clean up on exit."""
        self.cat.disconnect()
        self.audio.stop()
        if self.digital_panel.engine.is_running():
            self.digital_panel.engine.stop()
        self.spotter_panel.pota.stop()
        self.spotter_panel.dx.disconnect()
        self.spotter_panel.rbn.disconnect()
        event.accept()


# Import here to avoid circular imports at top
from core.cat817 import CAT817
