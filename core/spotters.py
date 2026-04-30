"""
Spotter Network Backends
- POTA: REST API (api.pota.app)
- DX Cluster: Telnet (configurable server)
- RBN: Reverse Beacon Network telnet (telnet.reversebeacon.net)
"""

import socket
import threading
import time
import re
import json
from dataclasses import dataclass, field
from typing import Optional
from urllib.request import urlopen, Request
from urllib.error import URLError
import urllib.parse

from PyQt6.QtCore import QObject, pyqtSignal, QTimer


# ─── Spot Data Model ──────────────────────────────────────────────────────────

@dataclass
class Spot:
    """Universal spot record across all networks."""
    network:     str   = ""       # "POTA", "DX", "RBN"
    callsign:    str   = ""       # Activator / DX station
    spotter:     str   = ""       # Who spotted them
    frequency:   float = 0.0      # MHz
    mode:        str   = ""       # USB, CW, FT8, etc.
    comment:     str   = ""       # Free text comment
    timestamp:   float = 0.0      # Unix time

    # POTA-specific
    pota_ref:    str   = ""       # e.g. "K-0001"
    park_name:   str   = ""
    park_state:  str   = ""
    park_country:str   = ""
    activator_qso_count: int = 0  # QSOs made this activation

    # DX/RBN-specific
    dx_country:  str   = ""
    snr:         int   = 0        # RBN signal/noise ratio
    wpm:         int   = 0        # RBN CW speed

    @property
    def freq_hz(self) -> int:
        return int(self.frequency * 1e6)

    @property
    def age_seconds(self) -> float:
        return time.time() - self.timestamp if self.timestamp else 0

    @property
    def age_str(self) -> str:
        s = int(self.age_seconds)
        if s < 60:
            return f"{s}s"
        elif s < 3600:
            return f"{s//60}m"
        else:
            return f"{s//3600}h"


# ─── POTA Spotter ─────────────────────────────────────────────────────────────

class POTASpotter(QObject):
    """
    Polls the POTA API for active spots.
    Endpoint: https://api.pota.app/spot/activator
    """

    spots_updated   = pyqtSignal(list)   # list[Spot]
    error_occurred  = pyqtSignal(str)
    status_message  = pyqtSignal(str)

    SPOT_URL     = "https://api.pota.app/spot/activator"
    PARK_URL     = "https://api.pota.app/park/{ref}"
    POLL_INTERVAL = 60_000   # ms — POTA asks for no more than 1/min

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QTimer()
        self._timer.timeout.connect(self._fetch)
        self._running = False
        self._last_spots: list[Spot] = []
        self._park_cache: dict[str, dict] = {}

    def start(self):
        self._running = True
        self._fetch()
        self._timer.start(self.POLL_INTERVAL)
        self.status_message.emit("POTA spotter started")

    def stop(self):
        self._running = False
        self._timer.stop()

    def _fetch(self):
        thread = threading.Thread(target=self._fetch_thread, daemon=True)
        thread.start()

    def _fetch_thread(self):
        try:
            req = Request(
                self.SPOT_URL,
                headers={"User-Agent": "FT817Suite/1.0"}
            )
            with urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())

            spots = []
            for item in data:
                try:
                    spot = Spot(
                        network   = "POTA",
                        callsign  = item.get("activator", ""),
                        spotter   = item.get("spotter", ""),
                        frequency = float(item.get("frequency", 0)),
                        mode      = self._normalize_mode(item.get("mode", "")),
                        comment   = item.get("comments", ""),
                        timestamp = time.time(),  # API doesn't give exact time
                        pota_ref  = item.get("reference", ""),
                        park_name = item.get("name", ""),
                        park_state= item.get("locationDesc", ""),
                        activator_qso_count = int(item.get("count", 0)),
                    )
                    spots.append(spot)
                except Exception:
                    continue

            self._last_spots = spots
            self.spots_updated.emit(spots)
            self.status_message.emit(f"POTA: {len(spots)} active spots")

        except URLError as e:
            self.error_occurred.emit(f"POTA fetch error: {e}")
        except Exception as e:
            self.error_occurred.emit(f"POTA error: {e}")

    def fetch_park_info(self, ref: str, callback) -> None:
        """Fetch park details for a POTA reference (async)."""
        if ref in self._park_cache:
            callback(self._park_cache[ref])
            return
        def _thread():
            try:
                url = self.PARK_URL.format(ref=urllib.parse.quote(ref))
                req = Request(url, headers={"User-Agent": "FT817Suite/1.0"})
                with urlopen(req, timeout=8) as resp:
                    data = json.loads(resp.read().decode())
                self._park_cache[ref] = data
                callback(data)
            except Exception as e:
                callback(None)
        threading.Thread(target=_thread, daemon=True).start()

    @staticmethod
    def _normalize_mode(mode: str) -> str:
        mode = mode.upper().strip()
        mapping = {
            "SSB": "USB", "LSB": "LSB", "USB": "USB",
            "CW": "CW", "FT8": "FT8", "FT4": "FT4",
            "AM": "AM", "FM": "FM", "DATA": "DIG",
            "PSK": "DIG", "RTTY": "DIG", "JS8": "JS8",
        }
        for k, v in mapping.items():
            if k in mode:
                return v
        return mode or "USB"


# ─── DX Cluster Telnet ────────────────────────────────────────────────────────

# Well-known DX cluster servers
DX_CLUSTER_SERVERS = [
    ("DXHeat (US)",          "dxheat.com",            7300),
    ("VE7CC (Vancouver)",    "dxc.ve7cc.net",         23),
    ("DX Summit (OH2AQ)",    "dxsummit.fi",           8000),
    ("GB7DXC (UK)",          "gb7dxc.net",            8000),
    ("WA9PIE (US)",          "wa9pie.net",            7300),
    ("K3LR (US)",            "k3lr.com",              7373),
    ("W3LPL (US)",           "w3lpl.net",             7373),
]

# DX spot line format:  DX de K1ABC:     14074.0  W2XYZ        FT8 -10dB         1234Z
DX_SPOT_RE = re.compile(
    r"DX de\s+(\S+?):\s+([\d.]+)\s+(\S+)\s+(.*?)\s+(\d{4}Z)?",
    re.IGNORECASE
)

# WWV/WCY lines — skip these
SKIP_RE = re.compile(r"^(WWV|WCY|To ALL)", re.IGNORECASE)


class DXClusterSpotter(QObject):
    """
    Connects to a DX Cluster via telnet and streams spots.
    """

    spot_received   = pyqtSignal(object)   # Spot
    connected       = pyqtSignal(bool)
    error_occurred  = pyqtSignal(str)
    status_message  = pyqtSignal(str)
    raw_line        = pyqtSignal(str)       # Raw telnet line for display

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sock: socket.socket | None = None
        self._running = False
        self._thread: threading.Thread | None = None
        self._host = ""
        self._port = 0
        self._callsign = ""

    def connect(self, host: str, port: int, callsign: str) -> bool:
        self._host     = host
        self._port     = port
        self._callsign = callsign.upper()
        self._running  = True
        self._thread   = threading.Thread(target=self._telnet_loop, daemon=True)
        self._thread.start()
        return True

    def disconnect(self):
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
        self._sock = None
        self.connected.emit(False)

    def send(self, text: str):
        if self._sock:
            try:
                self._sock.sendall((text + "\r\n").encode("utf-8", errors="replace"))
            except Exception:
                pass

    def _telnet_loop(self):
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(10)
            self._sock.connect((self._host, self._port))
            self._sock.settimeout(30)
            self.connected.emit(True)
            self.status_message.emit(f"DX Cluster connected: {self._host}:{self._port}")

            buf = ""
            login_sent = False

            while self._running:
                try:
                    chunk = self._sock.recv(4096).decode("utf-8", errors="replace")
                    if not chunk:
                        break
                    buf += chunk

                    # Process complete lines
                    while "\n" in buf:
                        line, buf = buf.split("\n", 1)
                        line = line.strip()
                        if not line:
                            continue

                        self.raw_line.emit(line)

                        # Auto-login when prompted
                        if not login_sent and ("login" in line.lower() or
                                               "call" in line.lower() or
                                               "enter" in line.lower()):
                            time.sleep(0.3)
                            self.send(self._callsign)
                            login_sent = True
                            continue

                        # Parse DX spot
                        spot = self._parse_dx_line(line)
                        if spot:
                            self.spot_received.emit(spot)

                except socket.timeout:
                    # Send keepalive
                    self.send("show/dx/1")
                    continue
                except Exception as e:
                    if self._running:
                        self.error_occurred.emit(f"DX Cluster recv error: {e}")
                    break

        except Exception as e:
            self.error_occurred.emit(f"DX Cluster connect error: {e}")
        finally:
            self.connected.emit(False)
            self.status_message.emit("DX Cluster disconnected")

    def _parse_dx_line(self, line: str) -> Optional[Spot]:
        if SKIP_RE.match(line):
            return None
        m = DX_SPOT_RE.search(line)
        if not m:
            return None
        try:
            spotter  = m.group(1).rstrip(":")
            freq_str = m.group(2)
            callsign = m.group(3)
            comment  = m.group(4).strip()
            freq     = float(freq_str)
            mode     = self._guess_mode(freq, comment)

            return Spot(
                network   = "DX",
                callsign  = callsign,
                spotter   = spotter,
                frequency = freq,
                mode      = mode,
                comment   = comment,
                timestamp = time.time(),
            )
        except Exception:
            return None

    @staticmethod
    def _guess_mode(freq_mhz: float, comment: str) -> str:
        """Guess mode from frequency and comment text."""
        comment_up = comment.upper()
        if "FT8"  in comment_up: return "FT8"
        if "FT4"  in comment_up: return "FT4"
        if "JS8"  in comment_up: return "JS8"
        if "WSPR" in comment_up: return "WSPR"
        if "RTTY" in comment_up: return "DIG"
        if "PSK"  in comment_up: return "DIG"
        if "CW"   in comment_up: return "CW"
        if "SSB"  in comment_up: return "USB"
        if "AM"   in comment_up: return "AM"
        if "FM"   in comment_up: return "FM"

        # Frequency-based guesses
        freq_hz = int(freq_mhz * 1e6)
        FT8_FREQS = [1840000, 3573000, 5357000, 7074000, 10136000,
                     14074000, 18100000, 21074000, 24915000, 28074000, 50313000]
        for ft8 in FT8_FREQS:
            if abs(freq_hz - ft8) < 2000:
                return "FT8"

        CW_SEGMENTS = [(1800000,1840000),(3500000,3600000),(7000000,7040000),
                       (14000000,14070000),(21000000,21070000),(28000000,28070000)]
        for lo, hi in CW_SEGMENTS:
            if lo <= freq_hz <= hi:
                return "CW"

        return "USB"


# ─── RBN (Reverse Beacon Network) ────────────────────────────────────────────

RBN_HOST = "telnet.reversebeacon.net"
RBN_PORT = 7000

# RBN spot format is same as DX cluster but with SNR/speed in comment
# e.g.: DX de DK9IP-#:   14025.0  K1ABC        CW 20 dB  22 WPM   CQ      1234Z
RBN_COMMENT_RE = re.compile(
    r"(\w+)\s+(\d+)\s*dB\s+(\d+)\s*WPM", re.IGNORECASE
)


class RBNSpotter(QObject):
    """
    Connects to the Reverse Beacon Network telnet feed.
    RBN spots CW/digital signals automatically via skimmer stations.
    """

    spot_received  = pyqtSignal(object)   # Spot
    connected      = pyqtSignal(bool)
    error_occurred = pyqtSignal(str)
    status_message = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dx = DXClusterSpotter()   # Reuse telnet logic
        self._dx.spot_received.connect(self._reprocess)
        self._dx.connected.connect(self.connected)
        self._dx.error_occurred.connect(self.error_occurred)
        self._dx.status_message.connect(self.status_message)
        self._callsign = ""

    def connect(self, callsign: str):
        self._callsign = callsign
        self._dx.connect(RBN_HOST, RBN_PORT, callsign)

    def disconnect(self):
        self._dx.disconnect()

    def _reprocess(self, spot: Spot):
        """Re-tag spot as RBN and extract SNR/WPM from comment."""
        spot.network = "RBN"
        m = RBN_COMMENT_RE.search(spot.comment)
        if m:
            spot.mode = m.group(1).upper()
            spot.snr  = int(m.group(2))
            spot.wpm  = int(m.group(3))
        self.spot_received.emit(spot)
