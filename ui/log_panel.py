"""
QSO Log Panel
Contact logging with full ADIF field support
"""

import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QPushButton, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QSplitter, QFormLayout, QComboBox, QTextEdit,
    QDialog, QDialogButtonBox, QFrame, QMessageBox, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSlot, QTimer
from PyQt6.QtGui import QFont

from core.logger import ContactLogger, QSOContact
from core.cat817 import CAT817


class ContactDialog(QDialog):
    """Dialog to add/edit a QSO."""
    def __init__(self, contact: QSOContact | None = None, cat: CAT817 | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Log QSO")
        self.setMinimumWidth(500)
        self._contact = contact or QSOContact()
        self._cat = cat
        self._build_ui()
        self._populate()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()
        form.setSpacing(8)

        self.call_edit    = QLineEdit(); self.call_edit.setPlaceholderText("K1ABC")
        self.freq_edit    = QLineEdit(); self.freq_edit.setPlaceholderText("14.074000")
        self.mode_combo   = QComboBox()
        self.mode_combo.addItems(["USB", "LSB", "CW", "CW-R", "AM", "FM", "FT8", "FT4",
                                   "JS8", "WSPR", "JT65", "JT9", "Q65", "MSK144", "PKT", "DIG"])
        self.band_edit    = QLineEdit(); self.band_edit.setPlaceholderText("20m")
        self.rst_sent     = QLineEdit("59"); self.rst_sent.setMaximumWidth(80)
        self.rst_rcvd     = QLineEdit("59"); self.rst_rcvd.setMaximumWidth(80)
        self.name_edit    = QLineEdit()
        self.qth_edit     = QLineEdit()
        self.grid_edit    = QLineEdit(); self.grid_edit.setMaximumWidth(100)
        self.date_edit    = QLineEdit()
        self.time_edit    = QLineEdit()
        self.pwr_edit     = QLineEdit("5"); self.pwr_edit.setMaximumWidth(80)
        self.notes_edit   = QTextEdit(); self.notes_edit.setMaximumHeight(80)

        form.addRow("Callsign *", self.call_edit)
        form.addRow("Frequency (MHz)", self.freq_edit)
        form.addRow("Mode", self.mode_combo)
        form.addRow("Band", self.band_edit)

        rst_row = QHBoxLayout()
        rst_row.addWidget(self.rst_sent)
        rst_row.addWidget(QLabel("Rcvd:"))
        rst_row.addWidget(self.rst_rcvd)
        form.addRow("RST Sent:", rst_row)

        form.addRow("Name", self.name_edit)
        form.addRow("QTH", self.qth_edit)
        form.addRow("Grid", self.grid_edit)
        form.addRow("Date (UTC)", self.date_edit)
        form.addRow("Time (UTC)", self.time_edit)
        form.addRow("TX Power (W)", self.pwr_edit)
        form.addRow("Notes", self.notes_edit)

        layout.addLayout(form)

        # Auto-fill from radio
        if self._cat:
            btn_fill = QPushButton("⬆ Auto-fill from Radio")
            btn_fill.clicked.connect(self._autofill)
            layout.addWidget(btn_fill)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate(self):
        c = self._contact
        self.call_edit.setText(c.callsign)
        if c.frequency:
            self.freq_edit.setText(f"{c.frequency / 1e6:.6f}")
        idx = self.mode_combo.findText(c.mode)
        if idx >= 0:
            self.mode_combo.setCurrentIndex(idx)
        self.band_edit.setText(c.band)
        self.rst_sent.setText(c.rst_sent)
        self.rst_rcvd.setText(c.rst_rcvd)
        self.name_edit.setText(c.name)
        self.qth_edit.setText(c.qth)
        self.grid_edit.setText(c.grid)
        self.pwr_edit.setText(c.tx_pwr)
        self.notes_edit.setPlainText(c.notes)

        now = datetime.datetime.utcnow()
        self.date_edit.setText(c.date_on or now.strftime("%Y%m%d"))
        self.time_edit.setText(c.time_on or now.strftime("%H%M%S"))

    def _autofill(self):
        if self._cat and self._cat.is_connected:
            freq = self._cat.frequency
            self.freq_edit.setText(f"{freq / 1e6:.6f}")
            self.band_edit.setText(CAT817.get_band(freq))
            idx = self.mode_combo.findText(self._cat.mode)
            if idx >= 0:
                self.mode_combo.setCurrentIndex(idx)

    def get_contact(self) -> QSOContact:
        c = self._contact
        c.callsign = self.call_edit.text().strip().upper()
        try:
            c.frequency = int(float(self.freq_edit.text()) * 1e6)
        except ValueError:
            pass
        c.mode     = self.mode_combo.currentText()
        c.band     = self.band_edit.text().strip()
        c.rst_sent = self.rst_sent.text().strip()
        c.rst_rcvd = self.rst_rcvd.text().strip()
        c.name     = self.name_edit.text().strip()
        c.qth      = self.qth_edit.text().strip()
        c.grid     = self.grid_edit.text().strip().upper()
        c.tx_pwr   = self.pwr_edit.text().strip()
        c.notes    = self.notes_edit.toPlainText().strip()
        c.date_on  = self.date_edit.text().strip()
        c.time_on  = self.time_edit.text().strip()
        return c


class LogPanel(QWidget):
    COLS = ["Date", "Time", "Call", "Band", "Mode", "Freq MHz",
            "RST S", "RST R", "Name", "Grid", "Notes"]

    def __init__(self, logger: ContactLogger, cat: CAT817, parent=None):
        super().__init__(parent)
        self.logger = logger
        self.cat    = cat
        self._build_ui()
        self._wire_signals()
        self._reload_table()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # ── Toolbar ───────────────────────────────────────────────────────────
        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)

        self.btn_add = QPushButton("➕ Log QSO")
        self.btn_add.setObjectName("btn_connect")
        self.btn_add.clicked.connect(self._add_qso)
        toolbar.addWidget(self.btn_add)

        self.btn_edit = QPushButton("✏ Edit")
        self.btn_edit.clicked.connect(self._edit_selected)
        toolbar.addWidget(self.btn_edit)

        self.btn_delete = QPushButton("🗑 Delete")
        self.btn_delete.clicked.connect(self._delete_selected)
        toolbar.addWidget(self.btn_delete)

        toolbar.addStretch()

        # Search
        toolbar.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Callsign, band, mode…")
        self.search_edit.setMinimumWidth(120)
        self.search_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.search_edit.textChanged.connect(self._filter_table)
        toolbar.addWidget(self.search_edit)

        # Stats
        self.stats_label = QLabel("QSOs: 0")
        self.stats_label.setStyleSheet("font-weight: bold; color: #8b949e;")
        toolbar.addWidget(self.stats_label)

        layout.addLayout(toolbar)

        # ── Table ─────────────────────────────────────────────────────────────
        self.table = QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)
        self.table.doubleClicked.connect(self._edit_selected)

        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(10, QHeaderView.ResizeMode.Stretch)
        hh.setStretchLastSection(True)
        self.table.setFont(QFont("Consolas", 10))
        self.table.horizontalHeader().setMinimumSectionSize(40)
        layout.addWidget(self.table, 1)

        # ── Stats bar ─────────────────────────────────────────────────────────
        stats_box = QGroupBox("STATISTICS")
        stats_layout = QHBoxLayout(stats_box)
        stats_layout.setSpacing(0)
        self.stat_total = QLabel("Total: 0")
        self.stat_bands = QLabel("Bands: 0")
        self.stat_modes = QLabel("Modes: 0")
        self.stat_dxcc  = QLabel("DXCC: 0")
        for lbl in [self.stat_total, self.stat_bands, self.stat_modes, self.stat_dxcc]:
            lbl.setStyleSheet("font-family: Consolas; font-size: 11px; font-weight: bold; padding: 0 10px;")
            lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
            stats_layout.addWidget(lbl)
        stats_layout.addStretch()
        layout.addWidget(stats_box)

    # ─── Signal Wiring ────────────────────────────────────────────────────────

    def _wire_signals(self):
        self.logger.contact_added.connect(lambda c: self._reload_table())
        self.logger.contact_updated.connect(lambda c: self._reload_table())
        self.logger.contact_deleted.connect(lambda uid: self._reload_table())

    # ─── Table Management ─────────────────────────────────────────────────────

    def _reload_table(self):
        contacts = self.logger.get_all()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)

        for c in contacts:
            row = self.table.rowCount()
            self.table.insertRow(row)

            # Format date/time nicely
            date_str = f"{c.date_on[:4]}-{c.date_on[4:6]}-{c.date_on[6:]}" if len(c.date_on) == 8 else c.date_on
            time_str = f"{c.time_on[:2]}:{c.time_on[2:4]}:{c.time_on[4:]}" if len(c.time_on) == 6 else c.time_on
            freq_str = f"{c.frequency/1e6:.3f}" if c.frequency else ""

            values = [date_str, time_str, c.callsign, c.band, c.mode, freq_str,
                      c.rst_sent, c.rst_rcvd, c.name, c.grid, c.notes]

            for col, val in enumerate(values):
                item = QTableWidgetItem(str(val))
                if col == 2:  # Callsign — bold
                    item.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
                self.table.setItem(row, col, item)

            # Store uid in first column
            if self.table.item(row, 0):
                self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, c.uid)

        self.table.setSortingEnabled(True)
        self._update_stats(contacts)

    def _filter_table(self, text: str):
        text = text.lower()
        for row in range(self.table.rowCount()):
            match = False
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item and text in item.text().lower():
                    match = True
                    break
            self.table.setRowHidden(row, not match)

    def _update_stats(self, contacts: list[QSOContact]):
        total  = len(contacts)
        bands  = len(set(c.band for c in contacts if c.band))
        modes  = len(set(c.mode for c in contacts if c.mode))
        dxcc   = len(set(c.dxcc for c in contacts if c.dxcc))

        self.stat_total.setText(f"Total: {total}")
        self.stat_bands.setText(f"Bands: {bands}")
        self.stat_modes.setText(f"Modes: {modes}")
        self.stat_dxcc.setText(f"DXCC: {dxcc}")
        self.stats_label.setText(f"QSOs: {total}")

    # ─── Actions ──────────────────────────────────────────────────────────────

    def _add_qso(self):
        # Pre-fill with current radio state
        pre = QSOContact(
            frequency = self.cat.frequency,
            mode      = self.cat.mode,
            band      = CAT817.get_band(self.cat.frequency),
        )
        dlg = ContactDialog(pre, self.cat, self)
        if dlg.exec():
            contact = dlg.get_contact()
            if contact.callsign:
                self.logger.add_contact(contact)

    def _edit_selected(self):
        sel = self.table.selectedItems()
        if not sel:
            return
        row = self.table.currentRow()
        uid_item = self.table.item(row, 0)
        if not uid_item:
            return
        uid = uid_item.data(Qt.ItemDataRole.UserRole)
        contact = next((c for c in self.logger._contacts if c.uid == uid), None)
        if not contact:
            return
        dlg = ContactDialog(contact, self.cat, self)
        if dlg.exec():
            updated = dlg.get_contact()
            self.logger.update_contact(uid, **{
                k: v for k, v in updated.__dict__.items() if k != "uid"
            })

    def _delete_selected(self):
        sel = self.table.selectedItems()
        if not sel:
            return
        row = self.table.currentRow()
        uid_item = self.table.item(row, 0)
        if not uid_item:
            return
        uid = uid_item.data(Qt.ItemDataRole.UserRole)
        call_item = self.table.item(row, 2)
        call = call_item.text() if call_item else "?"

        reply = QMessageBox.question(
            self, "Delete QSO",
            f"Delete QSO with {call}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.logger.delete_contact(uid)
