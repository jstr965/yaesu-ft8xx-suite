"""
Contact Logger
QSO logging with ADIF import/export support.
"""

import json
import os
import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional
from PyQt6.QtCore import QObject, pyqtSignal


@dataclass
class QSOContact:
    """A single QSO log entry."""
    callsign:   str = ""
    frequency:  int = 0        # Hz
    mode:       str = ""
    band:       str = ""
    rst_sent:   str = "59"
    rst_rcvd:   str = "59"
    name:       str = ""
    qth:        str = ""
    grid:       str = ""
    notes:      str = ""
    date_on:    str = ""       # YYYYMMDD
    time_on:    str = ""       # HHMMSS UTC
    date_off:   str = ""
    time_off:   str = ""
    tx_pwr:     str = "5"      # Watts
    op:         str = ""       # Operator callsign
    contest_id: str = ""
    dxcc:       str = ""
    state:      str = ""
    county:     str = ""
    country:    str = ""
    iota:       str = ""
    sota_ref:   str = ""
    propagation:str = ""
    qsl_sent:   str = "N"
    qsl_rcvd:   str = "N"
    uid:        str = ""       # Unique ID for table reference

    def __post_init__(self):
        if not self.uid:
            self.uid = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S%f")


class ContactLogger(QObject):
    """
    Manages QSO log entries.
    Stores in JSON, exports to ADIF.
    """

    contact_added   = pyqtSignal(object)   # QSOContact
    contact_updated = pyqtSignal(object)
    contact_deleted = pyqtSignal(str)      # uid
    log_loaded      = pyqtSignal(int)      # count

    def __init__(self, log_path: str = "qso_log.json", parent=None):
        super().__init__(parent)
        self._log_path = log_path
        self._contacts: list[QSOContact] = []
        self._load()

    # ─── Persistence ──────────────────────────────────────────────────────────

    def _load(self):
        """Load contacts from JSON file."""
        if not os.path.exists(self._log_path):
            return
        try:
            with open(self._log_path, "r") as f:
                data = json.load(f)
            self._contacts = [QSOContact(**d) for d in data]
            self.log_loaded.emit(len(self._contacts))
        except Exception as e:
            print(f"Log load error: {e}")

    def _save(self):
        """Save contacts to JSON file."""
        try:
            with open(self._log_path, "w") as f:
                json.dump([asdict(c) for c in self._contacts], f, indent=2)
        except Exception as e:
            print(f"Log save error: {e}")

    # ─── CRUD ────────────────────────────────────────────────────────────────

    def add_contact(self, contact: QSOContact):
        """Add a new QSO to the log."""
        if not contact.date_on:
            now = datetime.datetime.utcnow()
            contact.date_on = now.strftime("%Y%m%d")
            contact.time_on = now.strftime("%H%M%S")
        self._contacts.append(contact)
        self._save()
        self.contact_added.emit(contact)

    def update_contact(self, uid: str, **kwargs):
        """Update fields of an existing contact."""
        for c in self._contacts:
            if c.uid == uid:
                for k, v in kwargs.items():
                    if hasattr(c, k):
                        setattr(c, k, v)
                self._save()
                self.contact_updated.emit(c)
                return

    def delete_contact(self, uid: str):
        """Remove a contact by uid."""
        self._contacts = [c for c in self._contacts if c.uid != uid]
        self._save()
        self.contact_deleted.emit(uid)

    def get_all(self) -> list[QSOContact]:
        return list(reversed(self._contacts))  # Newest first

    def get_by_callsign(self, callsign: str) -> list[QSOContact]:
        cs = callsign.upper().strip()
        return [c for c in self._contacts if c.callsign.upper() == cs]

    def count(self) -> int:
        return len(self._contacts)

    # ─── ADIF Export ─────────────────────────────────────────────────────────

    def export_adif(self, path: str) -> bool:
        """Export log to ADIF format."""
        try:
            lines = []
            lines.append("ADIF Export from Yaesu FT-8XX Suite by K3LH")
            lines.append(f"<ADIF_VER:5>3.1.0")
            lines.append(f"<PROGRAMID:12>Yaesu FT-8XX Suite by K3LH")
            lines.append(f"<PROGRAMVERSION:5>1.0.0")
            lines.append("<EOH>")
            lines.append("")

            for c in self._contacts:
                record = []

                def adif_field(tag, value):
                    if value:
                        record.append(f"<{tag}:{len(str(value))}>{value}")

                adif_field("CALL",    c.callsign)
                adif_field("QSO_DATE", c.date_on)
                adif_field("TIME_ON",  c.time_on)
                adif_field("QSO_DATE_OFF", c.date_off or c.date_on)
                adif_field("TIME_OFF", c.time_off or c.time_on)
                adif_field("FREQ",  f"{c.frequency / 1e6:.6f}" if c.frequency else "")
                adif_field("BAND",   c.band)
                adif_field("MODE",   c.mode)
                adif_field("RST_SENT", c.rst_sent)
                adif_field("RST_RCVD", c.rst_rcvd)
                adif_field("NAME",   c.name)
                adif_field("QTH",    c.qth)
                adif_field("GRIDSQUARE", c.grid)
                adif_field("NOTES",  c.notes)
                adif_field("TX_PWR", c.tx_pwr)
                adif_field("OPERATOR", c.op)
                adif_field("DXCC",   c.dxcc)
                adif_field("STATE",  c.state)
                adif_field("COUNTRY", c.country)
                adif_field("IOTA",   c.iota)
                adif_field("SOTA_REF", c.sota_ref)
                adif_field("PROP_MODE", c.propagation)
                adif_field("QSL_SENT", c.qsl_sent)
                adif_field("QSL_RCVD", c.qsl_rcvd)

                record.append("<EOR>")
                lines.append(" ".join(record))
                lines.append("")

            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            return True

        except Exception as e:
            print(f"ADIF export error: {e}")
            return False

    def import_adif(self, path: str) -> int:
        """Import contacts from ADIF file. Returns count imported."""
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            # Find header end
            eoh = content.upper().find("<EOH>")
            if eoh >= 0:
                content = content[eoh + 5:]

            import re
            records = content.split("<EOR>")
            count = 0

            for record in records:
                fields = {}
                for match in re.finditer(r"<(\w+):\d+>([^<]*)", record, re.IGNORECASE):
                    tag   = match.group(1).upper()
                    value = match.group(2).strip()
                    fields[tag] = value

                if "CALL" not in fields:
                    continue

                c = QSOContact(
                    callsign    = fields.get("CALL", ""),
                    date_on     = fields.get("QSO_DATE", ""),
                    time_on     = fields.get("TIME_ON", ""),
                    band        = fields.get("BAND", ""),
                    mode        = fields.get("MODE", ""),
                    rst_sent    = fields.get("RST_SENT", "59"),
                    rst_rcvd    = fields.get("RST_RCVD", "59"),
                    name        = fields.get("NAME", ""),
                    qth         = fields.get("QTH", ""),
                    grid        = fields.get("GRIDSQUARE", ""),
                    notes       = fields.get("NOTES", ""),
                    tx_pwr      = fields.get("TX_PWR", "5"),
                    country     = fields.get("COUNTRY", ""),
                    state       = fields.get("STATE", ""),
                    dxcc        = fields.get("DXCC", ""),
                )
                try:
                    freq_mhz = float(fields.get("FREQ", "0"))
                    c.frequency = int(freq_mhz * 1e6)
                except ValueError:
                    pass

                self.add_contact(c)
                count += 1

            return count

        except Exception as e:
            print(f"ADIF import error: {e}")
            return 0
