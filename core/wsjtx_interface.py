"""
WSJT-X Protocol Interface
Handles UDP communication with WSJT-X running as external process,
AND provides built-in mode information and frequency management.

WSJT-X communicates via UDP multicast on port 2237 (default).
Protocol: https://physics.princeton.edu/pulsar/K1JT/wsjtx-doc/wsjtx-main-2.6.1.html#PROTOCOL
"""

import socket
import struct
import threading
import time
import subprocess
import os
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from dataclasses import dataclass
from typing import Optional


# WSJT-X UDP Protocol Magic/Schema
WSJTX_MAGIC    = 0xADBCCBDA
WSJTX_SCHEMA   = 2
WSJTX_UDP_PORT = 2237
WSJTX_UDP_HOST = "127.0.0.1"

# Message Types
MSG_HEARTBEAT    = 0
MSG_STATUS       = 1
MSG_DECODE       = 2
MSG_CLEAR        = 3
MSG_REPLY        = 4
MSG_LOG_QSO      = 5
MSG_CLOSE        = 6
MSG_REPLAY       = 7
MSG_HALT_TX      = 8
MSG_FREE_TEXT    = 9
MSG_WSPR_DECODE  = 10
MSG_LOCATION     = 11
MSG_LOGGED_ADIF  = 12
MSG_HIGHLIGHT    = 13
MSG_SWITCH_CONFIG = 14
MSG_CONFIGURE    = 15


@dataclass
class WSJTXDecode:
    """A decoded signal from WSJT-X."""
    new:          bool  = False
    time:         int   = 0      # HHMMSS
    snr:          int   = 0      # dB
    delta_time:   float = 0.0    # seconds
    delta_freq:   int   = 0      # Hz
    mode:         str   = ""
    message:      str   = ""
    low_conf:     bool  = False
    off_air:      bool  = False


@dataclass
class WSJTXStatus:
    """Radio status as reported by WSJT-X."""
    frequency:    int   = 0
    mode:         str   = ""
    dx_call:      str   = ""
    report:       str   = ""
    tx_mode:      str   = ""
    tx_enabled:   bool  = False
    transmitting: bool  = False
    decoding:     bool  = False
    rx_df:        int   = 0
    tx_df:        int   = 0
    de_call:      str   = ""
    de_grid:      str   = ""
    dx_grid:      str   = ""
    tx_watchdog:  bool  = False
    sub_mode:     str   = ""
    fast_mode:    bool  = False
    special_op:   int   = 0
    freq_tolerance: int = 0
    tr_period:    int   = 0
    config_name:  str   = ""
    tx_message:   str   = ""


# ─── Digital Mode Info ────────────────────────────────────────────────────────

DIGITAL_MODES = {
    "FT8": {
        "period":     15,      # seconds per TX/RX cycle
        "bandwidth":  50,      # Hz
        "baud":       6.25,
        "t_tx":       12.64,   # seconds to transmit
        "description": "FT8 — 15s periods, -20dB sensitivity. Most popular digital mode.",
        "wsjt_mode":  "FT8",
        "mode_byte":  "USB",   # Radio mode
    },
    "FT4": {
        "period":     7.5,
        "bandwidth":  90,
        "baud":       20.8,
        "t_tx":       4.48,
        "description": "FT4 — 7.5s periods, contest-oriented. 5dB less sensitive than FT8.",
        "wsjt_mode":  "FT4",
        "mode_byte":  "USB",
    },
    "JS8": {
        "period":     15,
        "bandwidth":  50,
        "baud":       6.25,
        "t_tx":       None,
        "description": "JS8Call — free-text messaging over FT8-like waveform.",
        "wsjt_mode":  "JS8",
        "mode_byte":  "USB",
    },
    "WSPR": {
        "period":     120,
        "bandwidth":  6,
        "baud":       1.465,
        "t_tx":       110.6,
        "description": "WSPR — 2min periods, ultra-weak signal propagation beaconing.",
        "wsjt_mode":  "WSPR",
        "mode_byte":  "USB",
    },
    "JT65": {
        "period":     60,
        "bandwidth":  177.6,
        "baud":       2.69,
        "t_tx":       46.8,
        "description": "JT65 — 60s periods, HF/EME DX. Predecessor to FT8.",
        "wsjt_mode":  "JT65",
        "mode_byte":  "USB",
    },
    "JT9": {
        "period":     60,
        "bandwidth":  15.6,
        "baud":       1.736,
        "t_tx":       49.0,
        "description": "JT9 — narrow bandwidth version of JT65.",
        "wsjt_mode":  "JT9",
        "mode_byte":  "USB",
    },
    "Q65": {
        "period":     60,
        "bandwidth":  None,
        "baud":       None,
        "t_tx":       None,
        "description": "Q65 — weak signal mode for MS, EME, multi-path propagation.",
        "wsjt_mode":  "Q65",
        "mode_byte":  "USB",
    },
    "MSK144": {
        "period":     None,
        "bandwidth":  None,
        "baud":       None,
        "t_tx":       None,
        "description": "MSK144 — meteor scatter, very short bursts.",
        "wsjt_mode":  "MSK144",
        "mode_byte":  "USB",
    },
}


class WSJTXInterface(QObject):
    """
    Manages UDP connection to WSJT-X.
    Can also launch WSJT-X as a subprocess.
    """

    decode_received  = pyqtSignal(object)    # WSJTXDecode
    status_received  = pyqtSignal(object)    # WSJTXStatus
    qso_logged       = pyqtSignal(dict)      # QSO data dict
    heartbeat        = pyqtSignal(str)       # WSJT-X version
    connected        = pyqtSignal(bool)
    error_occurred   = pyqtSignal(str)
    status_message   = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sock: socket.socket | None = None
        self._running = False
        self._thread: threading.Thread | None = None
        self._wsjtx_proc: subprocess.Popen | None = None
        self._last_heartbeat = 0.0

        self.current_status = WSJTXStatus()
        self._is_connected = False

        self._watchdog = QTimer()
        self._watchdog.timeout.connect(self._check_connection)
        self._watchdog.setInterval(5000)

    # ─── Connection ───────────────────────────────────────────────────────────

    def start_listening(self, port: int = WSJTX_UDP_PORT):
        """Start UDP listener for WSJT-X messages."""
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.bind(("", port))
            self._sock.settimeout(1.0)

            self._running = True
            self._thread = threading.Thread(target=self._recv_loop, daemon=True)
            self._thread.start()
            self._watchdog.start()
            self.status_message.emit(f"Listening for WSJT-X on UDP port {port}")
            return True

        except Exception as e:
            self.error_occurred.emit(f"UDP error: {e}")
            return False

    def stop_listening(self):
        """Stop UDP listener."""
        self._running = False
        self._watchdog.stop()
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
        self._sock = None
        self._is_connected = False
        self.connected.emit(False)

    # ─── Receive Loop ─────────────────────────────────────────────────────────

    def _recv_loop(self):
        """Background thread: receive and parse WSJT-X UDP datagrams."""
        while self._running:
            try:
                data, addr = self._sock.recvfrom(65536)
                self._parse_message(data)
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    self.error_occurred.emit(f"Receive error: {e}")
                break

    def _parse_message(self, data: bytes):
        """Parse a WSJT-X UDP message."""
        try:
            if len(data) < 8:
                return
            magic, schema, msg_type, client_id_len = struct.unpack_from(">IIIB", data, 0)

            if magic != WSJTX_MAGIC:
                return

            offset = 13 + client_id_len  # Skip magic(4) + schema(4) + type(4) + id

            if msg_type == MSG_HEARTBEAT:
                self._handle_heartbeat(data, offset)
            elif msg_type == MSG_STATUS:
                self._handle_status(data, offset)
            elif msg_type == MSG_DECODE:
                self._handle_decode(data, offset)
            elif msg_type == MSG_LOG_QSO:
                self._handle_log_qso(data, offset)
            elif msg_type == MSG_LOGGED_ADIF:
                self._handle_logged_adif(data, offset)

        except Exception:
            pass  # Malformed packet

    def _read_utf8(self, data: bytes, offset: int) -> tuple[str, int]:
        """Read a length-prefixed UTF-8 string from buffer."""
        if offset + 4 > len(data):
            return "", offset
        length = struct.unpack_from(">I", data, offset)[0]
        offset += 4
        if length == 0xFFFFFFFF:
            return "", offset
        if offset + length > len(data):
            return "", offset
        text = data[offset:offset + length].decode("utf-8", errors="replace")
        return text, offset + length

    def _handle_heartbeat(self, data: bytes, offset: int):
        """Handle WSJT-X heartbeat."""
        version, offset = self._read_utf8(data, offset)
        self._last_heartbeat = time.monotonic()
        if not self._is_connected:
            self._is_connected = True
            self.connected.emit(True)
        self.heartbeat.emit(version)

    def _handle_status(self, data: bytes, offset: int):
        """Handle WSJT-X status update."""
        try:
            s = WSJTXStatus()
            if offset + 8 <= len(data):
                s.frequency = struct.unpack_from(">Q", data, offset)[0]
                offset += 8
            s.mode, offset         = self._read_utf8(data, offset)
            s.dx_call, offset      = self._read_utf8(data, offset)
            s.report, offset       = self._read_utf8(data, offset)
            s.tx_mode, offset      = self._read_utf8(data, offset)

            if offset + 1 <= len(data):
                s.tx_enabled = bool(data[offset]); offset += 1
            if offset + 1 <= len(data):
                s.transmitting = bool(data[offset]); offset += 1
            if offset + 1 <= len(data):
                s.decoding = bool(data[offset]); offset += 1
            if offset + 4 <= len(data):
                s.rx_df = struct.unpack_from(">I", data, offset)[0]; offset += 4
            if offset + 4 <= len(data):
                s.tx_df = struct.unpack_from(">I", data, offset)[0]; offset += 4

            s.de_call, offset = self._read_utf8(data, offset)
            s.de_grid, offset = self._read_utf8(data, offset)
            s.dx_grid, offset = self._read_utf8(data, offset)

            if offset + 1 <= len(data):
                s.tx_watchdog = bool(data[offset]); offset += 1

            s.sub_mode, offset = self._read_utf8(data, offset)

            if offset + 1 <= len(data):
                s.fast_mode = bool(data[offset]); offset += 1
            if offset + 4 <= len(data):
                s.special_op = struct.unpack_from(">I", data, offset)[0]; offset += 4

            s.config_name, offset = self._read_utf8(data, offset)
            s.tx_message, offset  = self._read_utf8(data, offset)

            self.current_status = s
            self.status_received.emit(s)

        except Exception:
            pass

    def _handle_decode(self, data: bytes, offset: int):
        """Handle a decoded signal."""
        try:
            d = WSJTXDecode()
            if offset + 1 <= len(data):
                d.new = bool(data[offset]); offset += 1
            if offset + 4 <= len(data):
                d.time = struct.unpack_from(">I", data, offset)[0]; offset += 4
            if offset + 4 <= len(data):
                d.snr = struct.unpack_from(">i", data, offset)[0]; offset += 4
            if offset + 8 <= len(data):
                d.delta_time = struct.unpack_from(">d", data, offset)[0]; offset += 8
            if offset + 4 <= len(data):
                d.delta_freq = struct.unpack_from(">I", data, offset)[0]; offset += 4
            d.mode, offset    = self._read_utf8(data, offset)
            d.message, offset = self._read_utf8(data, offset)
            if offset + 1 <= len(data):
                d.low_conf = bool(data[offset]); offset += 1
            if offset + 1 <= len(data):
                d.off_air = bool(data[offset]); offset += 1

            self.decode_received.emit(d)

        except Exception:
            pass

    def _handle_log_qso(self, data: bytes, offset: int):
        """Handle WSJT-X QSO log entry."""
        try:
            qso = {}
            date_off, offset  = self._read_utf8(data, offset)
            time_off, offset  = self._read_utf8(data, offset)
            dx_call, offset   = self._read_utf8(data, offset)
            dx_grid, offset   = self._read_utf8(data, offset)

            if offset + 8 <= len(data):
                freq = struct.unpack_from(">Q", data, offset)[0]; offset += 8
                qso["frequency"] = freq

            mode, offset     = self._read_utf8(data, offset)
            rst_sent, offset = self._read_utf8(data, offset)
            rst_rcvd, offset = self._read_utf8(data, offset)
            tx_pwr, offset   = self._read_utf8(data, offset)
            comments, offset = self._read_utf8(data, offset)
            name, offset     = self._read_utf8(data, offset)

            qso.update({
                "callsign": dx_call,
                "grid":     dx_grid,
                "mode":     mode,
                "rst_sent": rst_sent,
                "rst_rcvd": rst_rcvd,
                "tx_pwr":   tx_pwr,
                "notes":    comments,
                "name":     name,
            })
            self.qso_logged.emit(qso)

        except Exception:
            pass

    def _handle_logged_adif(self, data: bytes, offset: int):
        """WSJT-X logged an ADIF record."""
        adif, _ = self._read_utf8(data, offset)
        self.status_message.emit(f"WSJT-X logged: {adif[:80]}")

    def _check_connection(self):
        """Watchdog: detect WSJT-X disconnect."""
        if self._is_connected and time.monotonic() - self._last_heartbeat > 10:
            self._is_connected = False
            self.connected.emit(False)
            self.status_message.emit("WSJT-X heartbeat lost")

    # ─── Commands to WSJT-X ──────────────────────────────────────────────────

    def send_halt_tx(self, auto_only: bool = False):
        """Tell WSJT-X to stop transmitting."""
        if not self._sock:
            return
        # Build Halt Tx packet
        client_id = b"FT817Suite"
        pkt = struct.pack(">IIIB", WSJTX_MAGIC, WSJTX_SCHEMA, MSG_HALT_TX, len(client_id))
        pkt += client_id
        pkt += struct.pack(">B", int(auto_only))
        try:
            self._sock.sendto(pkt, (WSJTX_UDP_HOST, WSJTX_UDP_PORT))
        except Exception:
            pass

    def send_free_text(self, text: str, send: bool = False):
        """Set WSJT-X free text field."""
        if not self._sock:
            return
        client_id = b"FT817Suite"
        text_enc = text.encode("utf-8")
        pkt = struct.pack(">IIIB", WSJTX_MAGIC, WSJTX_SCHEMA, MSG_FREE_TEXT, len(client_id))
        pkt += client_id
        pkt += struct.pack(">I", len(text_enc)) + text_enc
        pkt += struct.pack(">B", int(send))
        try:
            self._sock.sendto(pkt, (WSJTX_UDP_HOST, WSJTX_UDP_PORT))
        except Exception:
            pass

    # ─── WSJT-X Launch ───────────────────────────────────────────────────────

    def launch_wsjtx(self, exe_path: str = "wsjtx") -> bool:
        """Launch WSJT-X as a subprocess."""
        try:
            self._wsjtx_proc = subprocess.Popen(
                [exe_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.status_message.emit("WSJT-X launched")
            return True
        except FileNotFoundError:
            self.error_occurred.emit(f"WSJT-X not found at: {exe_path}")
            return False
        except Exception as e:
            self.error_occurred.emit(f"Launch error: {e}")
            return False

    def close_wsjtx(self):
        """Send close message to WSJT-X."""
        if not self._sock:
            return
        client_id = b"FT817Suite"
        pkt = struct.pack(">IIIB", WSJTX_MAGIC, WSJTX_SCHEMA, MSG_CLOSE, len(client_id))
        pkt += client_id
        try:
            self._sock.sendto(pkt, (WSJTX_UDP_HOST, WSJTX_UDP_PORT))
        except Exception:
            pass

    @property
    def is_connected(self) -> bool:
        return self._is_connected
