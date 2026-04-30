"""
Spotter Panel
Combined POTA / DX Cluster / RBN spot display with one-click QSY
"""

import time
import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QPushButton, QComboBox, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QSplitter, QCheckBox, QSpinBox, QTextEdit,
    QTabWidget, QFrame, QDialog, QVBoxLayout as QVBox, QFormLayout,
    QDialogButtonBox, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSlot, QTimer, QSortFilterProxyModel
from PyQt6.QtGui import QColor, QFont, QBrush

from core.spotters import (
    Spot, POTASpotter, DXClusterSpotter, RBNSpotter, DX_CLUSTER_SERVERS
)
from core.cat817 import CAT817
from core.logger import ContactLogger, QSOContact


# ─── Colour scheme per network ────────────────────────────────────────────────
NETWORK_COLORS = {
    "POTA": {"bg": "#0d2b1a", "fg": "#3fb950", "badge_bg": "#1a4731", "badge_fg": "#56d364"},
    "DX":   {"bg": "#0d1b2b", "fg": "#58a6ff", "badge_bg": "#1a3a5c", "badge_fg": "#79c0ff"},
    "RBN":  {"bg": "#2b1a0d", "fg": "#e3b341", "badge_bg": "#5c3a1a", "badge_fg": "#f0c040"},
}

MODE_COLORS = {
    "FT8":  "#58a6ff",
    "FT4":  "#79c0ff",
    "CW":   "#f0c040",
    "USB":  "#3fb950",
    "LSB":  "#3fb950",
    "JS8":  "#bc8cff",
    "WSPR": "#e3b341",
    "DIG":  "#d2a8ff",
    "AM":   "#ffa657",
    "FM":   "#ffa657",
}

MAX_SPOTS = 500   # Keep table manageable


class ParkInfoDialog(QDialog):
    """Shows POTA park details."""
    def __init__(self, spot: Spot, park_data: dict | None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"POTA Park Info — {spot.pota_ref}")
        self.setMinimumWidth(420)
        layout = QVBox(self)

        if park_data:
            form = QFormLayout()
            fields = [
                ("Reference",   park_data.get("reference", spot.pota_ref)),
                ("Park Name",   park_data.get("name", spot.park_name)),
                ("Location",    park_data.get("locationName", "")),
                ("State/Prov",  park_data.get("locationDesc", spot.park_state)),
                ("Country",     park_data.get("entityName", "")),
                ("Type",        park_data.get("parktypeDesc", "")),
                ("Active QSOs", str(spot.activator_qso_count)),
                ("Activator",   spot.callsign),
                ("Frequency",   f"{spot.frequency:.3f} MHz"),
                ("Mode",        spot.mode),
                ("Spotter",     spot.spotter),
                ("Comment",     spot.comment),
            ]
            for label, value in fields:
                if value:
                    lbl = QLabel(str(value))
                    lbl.setFont(QFont("Consolas", 10))
                    lbl.setWordWrap(True)
                    form.addRow(f"<b>{label}:</b>", lbl)
            layout.addLayout(form)
        else:
            layout.addWidget(QLabel(
                f"<b>{spot.callsign}</b> activating <b>{spot.pota_ref}</b><br>"
                f"{spot.park_name}<br>{spot.park_state}<br><br>"
                f"Freq: {spot.frequency:.3f} MHz  Mode: {spot.mode}<br>"
                f"QSOs: {spot.activator_qso_count}  Spotter: {spot.spotter}"
            ))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class SpotTable(QTableWidget):
    """The main combined spot table."""

    COLS = ["Age", "Net", "Callsign", "Freq MHz", "Mode", "Info", "Spotter", "Comment"]

    spot_clicked = None   # set by SpotterPanel

    def __init__(self, parent=None):
        super().__init__(0, len(self.COLS), parent)
        self.setHorizontalHeaderLabels(self.COLS)
        self.setAlternatingRowColors(False)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.setSortingEnabled(False)
        self.setWordWrap(False)
        self.setShowGrid(True)
        self.setFont(QFont("Consolas", 10))

        hh = self.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # Age
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Net
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Call
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Freq
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Mode
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # Info
        hh.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)  # Spotter
        hh.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)           # Comment

        self.setRowHeight(0, 24)
        self.verticalHeader().setDefaultSectionSize(24)

        # Store spot objects by row
        self._spots: list[Spot] = []

    def add_spot(self, spot: Spot):
        """Add spot at top, deduplicate by callsign+network."""
        # Remove existing spot from same callsign+network (update)
        for i, s in enumerate(self._spots):
            if s.callsign == spot.callsign and s.network == spot.network:
                self.removeRow(i)
                self._spots.pop(i)
                break

        # Insert at top
        self.insertRow(0)
        self._spots.insert(0, spot)

        c = NETWORK_COLORS.get(spot.network, NETWORK_COLORS["DX"])
        bg = QColor(c["bg"])
        fg = QColor(c["fg"])

        # Info column — POTA ref or SNR
        if spot.network == "POTA":
            info = f"{spot.pota_ref}  {spot.activator_qso_count}Q"
        elif spot.network == "RBN":
            info = f"{spot.snr}dB {spot.wpm}wpm" if spot.snr else ""
        else:
            info = spot.dx_country or ""

        mode_color = QColor(MODE_COLORS.get(spot.mode, c["fg"]))

        values = [
            spot.age_str,
            spot.network,
            spot.callsign,
            f"{spot.frequency:.3f}",
            spot.mode,
            info,
            spot.spotter,
            spot.comment,
        ]

        for col, val in enumerate(values):
            item = QTableWidgetItem(str(val))
            item.setBackground(QBrush(bg))

            if col == 2:   # Callsign — bold network colour
                item.setForeground(QBrush(fg))
                item.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            elif col == 4:  # Mode — mode colour
                item.setForeground(QBrush(mode_color))
                item.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            else:
                item.setForeground(QBrush(QColor("#c9d1d9")))

            self.setItem(0, col, item)

        # Trim to MAX_SPOTS
        while len(self._spots) > MAX_SPOTS:
            self.removeRow(self.rowCount() - 1)
            self._spots.pop()

    def get_spot_at_row(self, row: int) -> Spot | None:
        if 0 <= row < len(self._spots):
            return self._spots[row]
        return None

    def refresh_ages(self):
        """Update the Age column for all rows."""
        for row, spot in enumerate(self._spots):
            item = self.item(row, 0)
            if item:
                item.setText(spot.age_str)

    def filter_rows(self, network: str = "ALL", mode: str = "ALL",
                    band: str = "ALL", search: str = ""):
        """Show/hide rows by filter criteria."""
        for row, spot in enumerate(self._spots):
            visible = True
            if network != "ALL" and spot.network != network:
                visible = False
            if mode != "ALL" and spot.mode != mode:
                visible = False
            if band != "ALL":
                freq_hz = spot.freq_hz
                band_ranges = {
                    "160m": (1800000, 2000000), "80m":  (3500000, 4000000),
                    "60m":  (5330500, 5403500), "40m":  (7000000, 7300000),
                    "30m":  (10100000,10150000),"20m":  (14000000,14350000),
                    "17m":  (18068000,18168000),"15m":  (21000000,21450000),
                    "12m":  (24890000,24990000),"10m":  (28000000,29700000),
                    "6m":   (50000000,54000000),"2m":   (144000000,148000000),
                }
                lo, hi = band_ranges.get(band, (0, 999999999))
                if not (lo <= freq_hz <= hi):
                    visible = False
            if search:
                text = f"{spot.callsign} {spot.pota_ref} {spot.park_name} {spot.comment}".lower()
                if search.lower() not in text:
                    visible = False
            self.setRowHidden(row, not visible)


class SpotterPanel(QWidget):
    """
    Main spotter panel — combined POTA + DX Cluster + RBN.
    """

    # Signal to tell main window to QSY + pre-fill log
    qsy_requested = None   # wired up in main_window

    def __init__(self, cat: CAT817, logger: ContactLogger, parent=None):
        super().__init__(parent)
        self.cat    = cat
        self.logger = logger

        # Backend objects
        self.pota   = POTASpotter(self)
        self.dx     = DXClusterSpotter(self)
        self.rbn    = RBNSpotter(self)

        self._build_ui()
        self._wire_signals()

        # Age refresh timer
        self._age_timer = QTimer()
        self._age_timer.timeout.connect(self.spot_table.refresh_ages)
        self._age_timer.start(10_000)   # every 10s

    # ─── UI Build ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # ── Top control row ───────────────────────────────────────────────────
        top = QHBoxLayout()
        layout.addLayout(top)

        # POTA controls
        pota_box = QGroupBox("POTA")
        pota_layout = QHBoxLayout(pota_box)
        self.btn_pota = QPushButton("▶ Start")
        self.btn_pota.setCheckable(True)
        self.btn_pota.setObjectName("btn_connect")
        self.btn_pota.clicked.connect(self._toggle_pota)
        self.pota_status = QLabel("⬤ Offline")
        self.pota_status.setStyleSheet("color:#666; font-weight:bold;")
        pota_layout.addWidget(self.btn_pota)
        pota_layout.addWidget(self.pota_status)
        top.addWidget(pota_box)

        # DX Cluster controls
        dx_box = QGroupBox("DX Cluster")
        dx_layout = QHBoxLayout(dx_box)
        dx_layout.addWidget(QLabel("Server:"))
        self.dx_server_combo = QComboBox()
        for label, host, port in DX_CLUSTER_SERVERS:
            self.dx_server_combo.addItem(label, (host, port))
        self.dx_server_combo.setMinimumWidth(160)
        dx_layout.addWidget(self.dx_server_combo)

        dx_layout.addWidget(QLabel("Callsign:"))
        self.dx_callsign = QLineEdit()
        self.dx_callsign.setPlaceholderText("K1ABC")
        self.dx_callsign.setMaximumWidth(90)
        dx_layout.addWidget(self.dx_callsign)

        self.btn_dx = QPushButton("▶ Connect")
        self.btn_dx.setCheckable(True)
        self.btn_dx.clicked.connect(self._toggle_dx)
        self.dx_status = QLabel("⬤ Offline")
        self.dx_status.setStyleSheet("color:#666; font-weight:bold;")
        dx_layout.addWidget(self.btn_dx)
        dx_layout.addWidget(self.dx_status)
        top.addWidget(dx_box)

        # RBN controls
        rbn_box = QGroupBox("RBN")
        rbn_layout = QHBoxLayout(rbn_box)
        rbn_layout.addWidget(QLabel("Callsign:"))
        self.rbn_callsign = QLineEdit()
        self.rbn_callsign.setPlaceholderText("K1ABC")
        self.rbn_callsign.setMaximumWidth(90)
        rbn_layout.addWidget(self.rbn_callsign)
        self.btn_rbn = QPushButton("▶ Connect")
        self.btn_rbn.setCheckable(True)
        self.btn_rbn.clicked.connect(self._toggle_rbn)
        self.rbn_status = QLabel("⬤ Offline")
        self.rbn_status.setStyleSheet("color:#666; font-weight:bold;")
        rbn_layout.addWidget(self.btn_rbn)
        rbn_layout.addWidget(self.rbn_status)
        top.addWidget(rbn_box)

        # ── Filter bar ────────────────────────────────────────────────────────
        filter_bar = QHBoxLayout()
        layout.addLayout(filter_bar)

        filter_bar.addWidget(QLabel("Network:"))
        self.filter_network = QComboBox()
        self.filter_network.addItems(["ALL", "POTA", "DX", "RBN"])
        self.filter_network.currentTextChanged.connect(self._apply_filters)
        filter_bar.addWidget(self.filter_network)

        filter_bar.addWidget(QLabel("Band:"))
        self.filter_band = QComboBox()
        self.filter_band.addItems(["ALL","160m","80m","60m","40m","30m",
                                    "20m","17m","15m","12m","10m","6m","2m"])
        self.filter_band.currentTextChanged.connect(self._apply_filters)
        filter_bar.addWidget(self.filter_band)

        filter_bar.addWidget(QLabel("Mode:"))
        self.filter_mode = QComboBox()
        self.filter_mode.addItems(["ALL","FT8","FT4","CW","USB","LSB",
                                    "JS8","WSPR","DIG","AM","FM"])
        self.filter_mode.currentTextChanged.connect(self._apply_filters)
        filter_bar.addWidget(self.filter_mode)

        filter_bar.addWidget(QLabel("Search:"))
        self.filter_search = QLineEdit()
        self.filter_search.setPlaceholderText("callsign, park ref, comment…")
        self.filter_search.setMaximumWidth(200)
        self.filter_search.textChanged.connect(self._apply_filters)
        filter_bar.addWidget(self.filter_search)

        btn_clear_filter = QPushButton("✕ Clear")
        btn_clear_filter.clicked.connect(self._clear_filters)
        filter_bar.addWidget(btn_clear_filter)

        filter_bar.addStretch()

        self.spot_count_label = QLabel("0 spots")
        self.spot_count_label.setStyleSheet("color:#8b949e; font-weight:bold;")
        filter_bar.addWidget(self.spot_count_label)

        # ── Legend ────────────────────────────────────────────────────────────
        legend = QHBoxLayout()
        legend.addWidget(QLabel("Legend:"))
        for net, colors in NETWORK_COLORS.items():
            lbl = QLabel(f"  ■ {net}  ")
            lbl.setStyleSheet(
                f"background:{colors['badge_bg']}; color:{colors['badge_fg']};"
                f"font-weight:bold; border-radius:3px; padding:1px 6px; font-size:10px;"
            )
            legend.addWidget(lbl)
        legend.addStretch()
        layout.addLayout(legend)

        # ── Main splitter: table + detail/log ─────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        layout.addWidget(splitter, 1)

        # Spot table
        self.spot_table = SpotTable()
        self.spot_table.cellDoubleClicked.connect(self._on_double_click)
        self.spot_table.cellClicked.connect(self._on_click)
        splitter.addWidget(self.spot_table)

        # Bottom: detail panel + raw DX feed
        bottom = QWidget()
        bottom_layout = QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)

        # Spot detail / quick action panel
        detail_box = QGroupBox("SPOT DETAIL  —  Double-click a spot to QSY")
        detail_layout = QVBoxLayout(detail_box)

        self.detail_label = QLabel("Select a spot to see details and quick actions.")
        self.detail_label.setWordWrap(True)
        self.detail_label.setFont(QFont("Consolas", 10))
        detail_layout.addWidget(self.detail_label)

        action_row = QHBoxLayout()
        self.btn_qsy = QPushButton("📡 QSY Radio")
        self.btn_qsy.setToolTip("Tune radio to this spot's frequency and mode")
        self.btn_qsy.clicked.connect(self._qsy_selected)
        self.btn_qsy.setEnabled(False)

        self.btn_log = QPushButton("📒 Pre-fill Log")
        self.btn_log.setToolTip("Open log entry pre-filled with this callsign")
        self.btn_log.clicked.connect(self._prefill_log)
        self.btn_log.setEnabled(False)

        self.btn_info = QPushButton("ℹ Park Info")
        self.btn_info.setToolTip("Show POTA park details")
        self.btn_info.clicked.connect(self._show_park_info)
        self.btn_info.setEnabled(False)

        action_row.addWidget(self.btn_qsy)
        action_row.addWidget(self.btn_log)
        action_row.addWidget(self.btn_info)
        action_row.addStretch()
        detail_layout.addLayout(action_row)
        bottom_layout.addWidget(detail_box, 2)

        # Raw DX cluster feed
        raw_box = QGroupBox("DX CLUSTER RAW FEED")
        raw_layout = QVBoxLayout(raw_box)
        self.raw_feed = QTextEdit()
        self.raw_feed.setReadOnly(True)
        self.raw_feed.setFont(QFont("Consolas", 9))
        self.raw_feed.setMinimumHeight(60)
        raw_layout.addWidget(self.raw_feed)
        bottom_layout.addWidget(raw_box, 3)

        splitter.addWidget(bottom)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setChildrenCollapsible(False)

        self._selected_spot: Spot | None = None

    # ─── Signal Wiring ────────────────────────────────────────────────────────

    def _wire_signals(self):
        # POTA
        self.pota.spots_updated.connect(self._on_pota_spots)
        self.pota.status_message.connect(lambda m: self.pota_status.setText(m[:30]))
        self.pota.error_occurred.connect(lambda e: self.pota_status.setText(f"⚠ {e[:30]}"))

        # DX Cluster
        self.dx.spot_received.connect(self._on_single_spot)
        self.dx.connected.connect(self._on_dx_connected)
        self.dx.raw_line.connect(self._on_raw_line)
        self.dx.status_message.connect(lambda m: self.dx_status.setText(m[:30]))
        self.dx.error_occurred.connect(lambda e: self.dx_status.setText(f"⚠ {e[:30]}"))

        # RBN
        self.rbn.spot_received.connect(self._on_single_spot)
        self.rbn.connected.connect(self._on_rbn_connected)
        self.rbn.status_message.connect(lambda m: self.rbn_status.setText(m[:30]))
        self.rbn.error_occurred.connect(lambda e: self.rbn_status.setText(f"⚠ {e[:30]}"))

    # ─── Toggle Backends ──────────────────────────────────────────────────────

    def _toggle_pota(self, checked: bool):
        if checked:
            self.pota.start()
            self.btn_pota.setText("■ Stop")
            self.pota_status.setText("⬤ Polling…")
            self.pota_status.setStyleSheet("color:#3fb950; font-weight:bold;")
        else:
            self.pota.stop()
            self.btn_pota.setText("▶ Start")
            self.pota_status.setText("⬤ Offline")
            self.pota_status.setStyleSheet("color:#666; font-weight:bold;")

    def _toggle_dx(self, checked: bool):
        if checked:
            host, port = self.dx_server_combo.currentData()
            call = self.dx_callsign.text().strip() or "NOCALL"
            self.dx.connect(host, port, call)
            self.btn_dx.setText("■ Disconnect")
        else:
            self.dx.disconnect()
            self.btn_dx.setText("▶ Connect")
            self.dx_status.setText("⬤ Offline")
            self.dx_status.setStyleSheet("color:#666; font-weight:bold;")

    def _toggle_rbn(self, checked: bool):
        if checked:
            call = self.rbn_callsign.text().strip() or "NOCALL"
            self.rbn.connect(call)
            self.btn_rbn.setText("■ Disconnect")
        else:
            self.rbn.disconnect()
            self.btn_rbn.setText("▶ Connect")
            self.rbn_status.setText("⬤ Offline")
            self.rbn_status.setStyleSheet("color:#666; font-weight:bold;")

    # ─── Spot Handlers ────────────────────────────────────────────────────────

    @pyqtSlot(list)
    def _on_pota_spots(self, spots: list[Spot]):
        for spot in spots:
            self.spot_table.add_spot(spot)
        self._update_count()
        self._apply_filters()

    @pyqtSlot(object)
    def _on_single_spot(self, spot: Spot):
        self.spot_table.add_spot(spot)
        self._update_count()
        self._apply_filters()

    @pyqtSlot(bool)
    def _on_dx_connected(self, connected: bool):
        if connected:
            self.dx_status.setText("⬤ Live")
            self.dx_status.setStyleSheet("color:#58a6ff; font-weight:bold;")
        else:
            self.dx_status.setText("⬤ Offline")
            self.dx_status.setStyleSheet("color:#666; font-weight:bold;")
            self.btn_dx.setChecked(False)
            self.btn_dx.setText("▶ Connect")

    @pyqtSlot(bool)
    def _on_rbn_connected(self, connected: bool):
        if connected:
            self.rbn_status.setText("⬤ Live")
            self.rbn_status.setStyleSheet("color:#e3b341; font-weight:bold;")
        else:
            self.rbn_status.setText("⬤ Offline")
            self.rbn_status.setStyleSheet("color:#666; font-weight:bold;")
            self.btn_rbn.setChecked(False)
            self.btn_rbn.setText("▶ Connect")

    @pyqtSlot(str)
    def _on_raw_line(self, line: str):
        self.raw_feed.append(line)
        # Keep raw feed to ~200 lines
        doc = self.raw_feed.document()
        while doc.blockCount() > 200:
            cursor = self.raw_feed.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.select(cursor.SelectionType.LineUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()

    # ─── Table Interaction ────────────────────────────────────────────────────

    @pyqtSlot(int, int)
    def _on_click(self, row: int, col: int):
        spot = self.spot_table.get_spot_at_row(row)
        if not spot:
            return
        self._selected_spot = spot
        self._update_detail(spot)
        self.btn_qsy.setEnabled(True)
        self.btn_log.setEnabled(True)
        self.btn_info.setEnabled(spot.network == "POTA")

    @pyqtSlot(int, int)
    def _on_double_click(self, row: int, col: int):
        """Double-click = instant QSY."""
        self._on_click(row, col)
        self._qsy_selected()

    def _update_detail(self, spot: Spot):
        c = NETWORK_COLORS.get(spot.network, NETWORK_COLORS["DX"])
        fg = c["fg"]
        if spot.network == "POTA":
            text = (
                f"<span style='color:{fg}'><b>{spot.callsign}</b></span>"
                f"  activating  "
                f"<b>{spot.pota_ref}</b>  {spot.park_name}<br>"
                f"<b>Freq:</b> {spot.frequency:.3f} MHz  "
                f"<b>Mode:</b> {spot.mode}  "
                f"<b>QSOs:</b> {spot.activator_qso_count}  "
                f"<b>Spotter:</b> {spot.spotter}<br>"
                f"<b>Comment:</b> {spot.comment}"
            )
        elif spot.network == "RBN":
            text = (
                f"<span style='color:{fg}'><b>{spot.callsign}</b></span>"
                f"  spotted by RBN  {spot.spotter}<br>"
                f"<b>Freq:</b> {spot.frequency:.3f} MHz  "
                f"<b>Mode:</b> {spot.mode}  "
                f"<b>SNR:</b> {spot.snr}dB  "
                f"<b>Speed:</b> {spot.wpm}wpm<br>"
                f"<b>Comment:</b> {spot.comment}"
            )
        else:
            text = (
                f"<span style='color:{fg}'><b>{spot.callsign}</b></span>"
                f"  spotted by  {spot.spotter}<br>"
                f"<b>Freq:</b> {spot.frequency:.3f} MHz  "
                f"<b>Mode:</b> {spot.mode}<br>"
                f"<b>Comment:</b> {spot.comment}"
            )
        self.detail_label.setText(text)

    # ─── Actions ──────────────────────────────────────────────────────────────

    def _qsy_selected(self):
        spot = self._selected_spot
        if not spot or not spot.frequency:
            return
        freq_hz = spot.freq_hz
        self.cat.set_frequency(freq_hz)

        # Set mode on radio
        radio_mode = spot.mode
        # Map digital modes to radio DIG/USB
        if radio_mode in ("FT8", "FT4", "JS8", "WSPR", "RTTY", "PSK"):
            radio_mode = "USB"   # FT-817 uses USB for digital
        self.cat.set_mode(radio_mode)

    def _prefill_log(self):
        spot = self._selected_spot
        if not spot:
            return
        from core.logger import QSOContact
        from core.cat817 import CAT817
        contact = QSOContact(
            callsign  = spot.callsign,
            frequency = spot.freq_hz,
            mode      = spot.mode,
            band      = CAT817.get_band(spot.freq_hz),
            notes     = f"Via {spot.network} spot by {spot.spotter}. {spot.comment}".strip(),
        )
        if spot.network == "POTA":
            contact.notes = f"POTA {spot.pota_ref} {spot.park_name}. " + contact.notes
        # Emit to main window to open log dialog
        from ui.log_panel import ContactDialog
        from PyQt6.QtWidgets import QApplication
        main_win = QApplication.activeWindow()
        if main_win and hasattr(main_win, 'tabs') and hasattr(main_win, 'log_panel'):
            dlg = ContactDialog(contact, self.cat, main_win)
            if dlg.exec():
                filled = dlg.get_contact()
                if filled.callsign:
                    self.logger.add_contact(filled)
            main_win.tabs.setCurrentWidget(main_win.log_panel)

    def _show_park_info(self):
        spot = self._selected_spot
        if not spot or spot.network != "POTA":
            return
        def _show(park_data):
            dlg = ParkInfoDialog(spot, park_data, self)
            dlg.exec()
        self.pota.fetch_park_info(spot.pota_ref, _show)

    # ─── Filters ──────────────────────────────────────────────────────────────

    def _apply_filters(self):
        self.spot_table.filter_rows(
            network = self.filter_network.currentText(),
            mode    = self.filter_mode.currentText(),
            band    = self.filter_band.currentText(),
            search  = self.filter_search.text(),
        )

    def _clear_filters(self):
        self.filter_network.setCurrentIndex(0)
        self.filter_band.setCurrentIndex(0)
        self.filter_mode.setCurrentIndex(0)
        self.filter_search.clear()

    def _update_count(self):
        self.spot_count_label.setText(f"{self.spot_table.rowCount()} spots")

    def closeEvent(self, event):
        self.pota.stop()
        self.dx.disconnect()
        self.rbn.disconnect()
        super().closeEvent(event)
