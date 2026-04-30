"""
WSJT-X Engine Manager
Launches WSJT-X as a hidden background process, manages its config file,
and communicates via UDP. The user never sees the WSJT-X window.
"""

import os
import sys
import json
import time
import socket
import struct
import subprocess
import threading
import configparser
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal, QTimer


# ─── Default WSJT-X install locations on Windows ─────────────────────────────
WSJTX_SEARCH_PATHS = [
    r"C:\WSJT\wsjtx\bin\wsjtx.exe",
    r"C:\Program Files\WSJT-X\bin\wsjtx.exe",
    r"C:\Program Files (x86)\WSJT-X\bin\wsjtx.exe",
    str(Path.home() / "AppData" / "Local" / "WSJT-X" / "bin" / "wsjtx.exe"),
]

# WSJT-X config file location
WSJTX_CONFIG_DIR  = Path.home() / "AppData" / "Local" / "WSJT-X"
WSJTX_CONFIG_FILE = WSJTX_CONFIG_DIR / "WSJTX.ini"

# UDP
WSJTX_MAGIC  = 0xADBCCBDA
WSJTX_SCHEMA = 2
WSJTX_PORT   = 2237

# Message types
MSG_HEARTBEAT  = 0
MSG_STATUS     = 1
MSG_DECODE     = 2
MSG_CLEAR      = 3
MSG_REPLY      = 4
MSG_LOG_QSO    = 5
MSG_CLOSE      = 6
MSG_HALT_TX    = 8
MSG_FREE_TEXT  = 9
MSG_CONFIGURE  = 15


class WSJTXConfig:
    """
    Reads and writes the WSJT-X INI config file.
    Allows Yaesu FT-8XX Suite by K3LH to pre-configure WSJT-X before launching it.
    """

    DEFAULTS = {
        "Configuration": {
            "MyCall":        "NOCALL",
            "MyGrid":        "AA00",
            "PTTMethod":     "2",        # CAT
            "Mode":          "FT8",
            "SaveAll":       "false",
            "SaveDecodes":   "true",
            "TxFirst":       "false",
            "HoldTxFreq":    "false",
            "SplitMode":     "0",
            "SchemaVersion": "2",
        },
        "Rig": {
            "Rig":           "2",        # Hamlib
            "CATPort":       "COM1",
            "BaudRate":      "9600",
            "DataBits":      "3",        # 8 bits
            "StopBits":      "2",        # 2 stop bits
            "Handshake":     "0",        # None
            "PTTPort":       "CAT",
            "TXDelay":       "0",
        },
        "Audio": {
            "SoundInName":   "",
            "SoundOutName":  "",
        },
        "Network": {
            "UDPServer":     "127.0.0.1",
            "UDPServerPort": "2237",
            "AcceptUDPRequests": "true",
        },
    }

    def __init__(self, path: Path = WSJTX_CONFIG_FILE):
        self._path = path
        self._cfg  = configparser.ConfigParser(strict=False)
        self._cfg.optionxform = str   # Preserve case
        if path.exists():
            self._cfg.read(str(path), encoding="utf-8")

    def set(self, section: str, key: str, value: str):
        if not self._cfg.has_section(section):
            self._cfg.add_section(section)
        self._cfg.set(section, key, str(value))

    def get(self, section: str, key: str, fallback: str = "") -> str:
        return self._cfg.get(section, key, fallback=fallback)

    def apply_settings(self, settings: dict):
        """
        Apply a flat settings dict from FT817Settings to the INI.
        settings keys: callsign, grid, cat_port, baud, audio_in, audio_out,
                       mode, my_call, my_grid, udp_port
        """
        s = settings

        # Ensure sections exist
        for section in ["Configuration", "Rig", "Audio", "Network", "Frequencies"]:
            if not self._cfg.has_section(section):
                self._cfg.add_section(section)

        # Identity
        if s.get("callsign"):
            self.set("Configuration", "MyCall", s["callsign"])
        if s.get("grid"):
            self.set("Configuration", "MyGrid", s["grid"])

        # CAT / Rig
        if s.get("cat_port"):
            # Strip "COM" prefix for some fields, keep full for others
            port = s["cat_port"]
            self.set("Rig", "CATPort", port)
            self.set("Rig", "PTTPort", "CAT")
        if s.get("baud"):
            self.set("Rig", "BaudRate", str(s["baud"]))

        # Rig = Hamlib + correct rig ID for selected radio
        from core.cat817 import RADIO_MODELS
        model_key = s.get("radio_model", "FT-817")
        hamlib_id = RADIO_MODELS.get(model_key, RADIO_MODELS["FT-817"])["hamlib_id"]
        self.set("Rig", "Rig", str(hamlib_id))
        self.set("Rig", "DataBits",  "3")  # 8
        self.set("Rig", "StopBits",  "2")  # 2
        self.set("Rig", "Handshake", "0")  # None
        self.set("Rig", "PTTMethod", "2")  # CAT

        # Audio
        if s.get("audio_in"):
            self.set("Audio", "SoundInName",  s["audio_in"])
        if s.get("audio_out"):
            self.set("Audio", "SoundOutName", s["audio_out"])

        # Network — ensure UDP is enabled
        self.set("Network", "UDPServer",          "127.0.0.1")
        self.set("Network", "UDPServerPort",      str(s.get("udp_port", 2237)))
        self.set("Network", "AcceptUDPRequests",  "true")

        # Mode
        if s.get("mode"):
            self.set("Configuration", "Mode", s["mode"])

    def save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            self._cfg.write(f)

    def load_current(self) -> dict:
        """Return current settings as flat dict for populating UI."""
        return {
            "callsign":  self.get("Configuration", "MyCall"),
            "grid":      self.get("Configuration", "MyGrid"),
            "cat_port":  self.get("Rig", "CATPort"),
            "baud":      self.get("Rig", "BaudRate", "9600"),
            "audio_in":  self.get("Audio", "SoundInName"),
            "audio_out": self.get("Audio", "SoundOutName"),
            "mode":      self.get("Configuration", "Mode", "FT8"),
            "udp_port":  self.get("Network", "UDPServerPort", "2237"),
        }


class WSJTXEngine(QObject):
    """
    Manages the hidden WSJT-X process and all UDP communication.
    This is the single integration point — replaces WSJTXInterface.
    """

    # Process signals
    engine_started    = pyqtSignal()
    engine_stopped    = pyqtSignal()
    engine_error      = pyqtSignal(str)

    # Radio/decode signals
    decode_received   = pyqtSignal(object)    # WSJTXDecode dataclass
    status_received   = pyqtSignal(object)    # WSJTXStatus dataclass
    qso_logged        = pyqtSignal(dict)
    heartbeat         = pyqtSignal(str)       # version string
    connected         = pyqtSignal(bool)

    # Status
    status_message    = pyqtSignal(str)
    error_occurred    = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.config = WSJTXConfig()
        self._proc: subprocess.Popen | None = None
        self._sock: socket.socket | None    = None
        self._running   = False
        self._recv_thread: threading.Thread | None = None
        self._is_connected = False
        self._last_heartbeat = 0.0
        self._wsjtx_exe = ""

        # Settings applied to WSJT-X
        self._settings: dict = {}

        # Watchdog
        self._watchdog = QTimer()
        self._watchdog.timeout.connect(self._check_heartbeat)
        self._watchdog.setInterval(8000)

        # Import decode types here to avoid circular
        from core.wsjtx_interface import WSJTXDecode, WSJTXStatus
        self._DecodeClass = WSJTXDecode
        self._StatusClass = WSJTXStatus

    # ─── Engine Lifecycle ─────────────────────────────────────────────────────

    def find_wsjtx(self) -> str | None:
        """Search common install paths for wsjtx.exe."""
        for path in WSJTX_SEARCH_PATHS:
            if os.path.exists(path):
                return path
        return None

    def start(self, exe_path: str, settings: dict) -> bool:
        """
        Configure and launch WSJT-X hidden, then open UDP listener.
        """
        if not os.path.exists(exe_path):
            self.engine_error.emit(f"WSJT-X not found at:\n{exe_path}")
            return False

        self._wsjtx_exe = exe_path
        self._settings  = settings

        # Write config before launching
        self.config.apply_settings(settings)
        self.config.save()
        self.status_message.emit("WSJT-X config written")

        # Start UDP listener first
        if not self._start_udp(int(settings.get("udp_port", WSJTX_PORT))):
            return False

        # Launch WSJT-X hidden
        try:
            CREATE_NO_WINDOW = 0x08000000   # Windows flag
            self._proc = subprocess.Popen(
                [exe_path, "--config", "FT817Suite"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW,
            )
            self.status_message.emit(f"WSJT-X engine started (PID {self._proc.pid})")
            self._watchdog.start()
            self.engine_started.emit()
            return True

        except Exception as e:
            self.engine_error.emit(f"Failed to launch WSJT-X: {e}")
            self._stop_udp()
            return False

    def stop(self):
        """Stop WSJT-X process and UDP listener."""
        self._watchdog.stop()
        self._send_close()
        time.sleep(0.5)

        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
        self._proc = None
        self._stop_udp()
        self._is_connected = False
        self.connected.emit(False)
        self.engine_stopped.emit()
        self.status_message.emit("WSJT-X engine stopped")

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    # ─── UDP ──────────────────────────────────────────────────────────────────

    def _start_udp(self, port: int) -> bool:
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.bind(("127.0.0.1", port))
            self._sock.settimeout(1.0)
            self._running = True
            self._recv_thread = threading.Thread(
                target=self._recv_loop, daemon=True)
            self._recv_thread.start()
            self.status_message.emit(f"UDP listener on port {port}")
            return True
        except Exception as e:
            self.engine_error.emit(f"UDP bind failed: {e}")
            return False

    def _stop_udp(self):
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
        self._sock = None

    def _recv_loop(self):
        while self._running:
            try:
                data, addr = self._sock.recvfrom(65536)
                self._parse(data)
            except socket.timeout:
                continue
            except Exception:
                break

    # ─── Packet Parser ────────────────────────────────────────────────────────

    def _parse(self, data: bytes):
        if len(data) < 12:
            return
        try:
            magic, schema, msg_type = struct.unpack_from(">III", data, 0)
            if magic != WSJTX_MAGIC:
                return

            # Read client ID
            id_len = struct.unpack_from(">I", data, 12)[0]
            offset = 16
            if id_len != 0xFFFFFFFF:
                offset += id_len

            if msg_type == MSG_HEARTBEAT:
                self._parse_heartbeat(data, offset)
            elif msg_type == MSG_STATUS:
                self._parse_status(data, offset)
            elif msg_type == MSG_DECODE:
                self._parse_decode(data, offset)
            elif msg_type == MSG_LOG_QSO:
                self._parse_log_qso(data, offset)

        except Exception:
            pass

    def _read_str(self, data: bytes, offset: int) -> tuple[str, int]:
        if offset + 4 > len(data):
            return "", offset
        length = struct.unpack_from(">I", data, offset)[0]
        offset += 4
        if length == 0xFFFFFFFF or length == 0:
            return "", offset
        if offset + length > len(data):
            return "", offset
        text = data[offset:offset + length].decode("utf-8", errors="replace")
        return text, offset + length

    def _read_bool(self, data: bytes, offset: int) -> tuple[bool, int]:
        if offset >= len(data):
            return False, offset
        return bool(data[offset]), offset + 1

    def _read_u32(self, data: bytes, offset: int) -> tuple[int, int]:
        if offset + 4 > len(data):
            return 0, offset
        return struct.unpack_from(">I", data, offset)[0], offset + 4

    def _read_i32(self, data: bytes, offset: int) -> tuple[int, int]:
        if offset + 4 > len(data):
            return 0, offset
        return struct.unpack_from(">i", data, offset)[0], offset + 4

    def _read_u64(self, data: bytes, offset: int) -> tuple[int, int]:
        if offset + 8 > len(data):
            return 0, offset
        return struct.unpack_from(">Q", data, offset)[0], offset + 8

    def _read_f64(self, data: bytes, offset: int) -> tuple[float, int]:
        if offset + 8 > len(data):
            return 0.0, offset
        return struct.unpack_from(">d", data, offset)[0], offset + 8

    def _parse_heartbeat(self, data: bytes, offset: int):
        version, offset = self._read_str(data, offset)
        self._last_heartbeat = time.monotonic()
        if not self._is_connected:
            self._is_connected = True
            self.connected.emit(True)
        self.heartbeat.emit(version)

    def _parse_status(self, data: bytes, offset: int):
        s = self._StatusClass()
        s.frequency, offset   = self._read_u64(data, offset)
        s.mode, offset        = self._read_str(data, offset)
        s.dx_call, offset     = self._read_str(data, offset)
        s.report, offset      = self._read_str(data, offset)
        s.tx_mode, offset     = self._read_str(data, offset)
        s.tx_enabled, offset  = self._read_bool(data, offset)
        s.transmitting, offset= self._read_bool(data, offset)
        s.decoding, offset    = self._read_bool(data, offset)
        s.rx_df, offset       = self._read_u32(data, offset)
        s.tx_df, offset       = self._read_u32(data, offset)
        s.de_call, offset     = self._read_str(data, offset)
        s.de_grid, offset     = self._read_str(data, offset)
        s.dx_grid, offset     = self._read_str(data, offset)
        s.tx_watchdog, offset = self._read_bool(data, offset)
        s.sub_mode, offset    = self._read_str(data, offset)
        s.fast_mode, offset   = self._read_bool(data, offset)
        self.status_received.emit(s)

    def _parse_decode(self, data: bytes, offset: int):
        d = self._DecodeClass()
        d.new, offset         = self._read_bool(data, offset)
        d.time, offset        = self._read_u32(data, offset)
        d.snr, offset         = self._read_i32(data, offset)
        d.delta_time, offset  = self._read_f64(data, offset)
        d.delta_freq, offset  = self._read_u32(data, offset)
        d.mode, offset        = self._read_str(data, offset)
        d.message, offset     = self._read_str(data, offset)
        d.low_conf, offset    = self._read_bool(data, offset)
        self.decode_received.emit(d)

    def _parse_log_qso(self, data: bytes, offset: int):
        qso = {}
        _, offset        = self._read_str(data, offset)   # date_off
        _, offset        = self._read_str(data, offset)   # time_off
        call, offset     = self._read_str(data, offset)
        grid, offset     = self._read_str(data, offset)
        freq, offset     = self._read_u64(data, offset)
        mode, offset     = self._read_str(data, offset)
        rst_s, offset    = self._read_str(data, offset)
        rst_r, offset    = self._read_str(data, offset)
        pwr, offset      = self._read_str(data, offset)
        comments, offset = self._read_str(data, offset)
        name, offset     = self._read_str(data, offset)

        qso.update({
            "callsign": call, "grid": grid, "frequency": freq,
            "mode": mode, "rst_sent": rst_s, "rst_rcvd": rst_r,
            "tx_pwr": pwr, "notes": comments, "name": name,
        })
        self.qso_logged.emit(qso)

    # ─── Watchdog ─────────────────────────────────────────────────────────────

    def _check_heartbeat(self):
        # Check if process died
        if self._proc and self._proc.poll() is not None:
            self.status_message.emit("WSJT-X process exited")
            self._is_connected = False
            self.connected.emit(False)
            self.engine_stopped.emit()
            self._watchdog.stop()
            return
        # Check UDP heartbeat
        if self._is_connected and time.monotonic() - self._last_heartbeat > 15:
            self._is_connected = False
            self.connected.emit(False)
            self.status_message.emit("WSJT-X heartbeat lost")

    # ─── Commands → WSJT-X ───────────────────────────────────────────────────

    def _build_header(self, msg_type: int) -> bytes:
        client_id = b"FT817Suite"
        return struct.pack(">IIII", WSJTX_MAGIC, WSJTX_SCHEMA,
                           msg_type, len(client_id)) + client_id

    def _send(self, pkt: bytes):
        if self._sock:
            try:
                self._sock.sendto(pkt, ("127.0.0.1", WSJTX_PORT))
            except Exception:
                pass

    def _send_close(self):
        self._send(self._build_header(MSG_CLOSE))

    def halt_tx(self, auto_only: bool = False):
        pkt = self._build_header(MSG_HALT_TX)
        pkt += struct.pack(">B", int(auto_only))
        self._send(pkt)

    def set_free_text(self, text: str, send: bool = False):
        enc = text.encode("utf-8")
        pkt = self._build_header(MSG_FREE_TEXT)
        pkt += struct.pack(">I", len(enc)) + enc
        pkt += struct.pack(">B", int(send))
        self._send(pkt)

    def configure(self, mode: str = "", freq_tolerance: int = 50,
                  tr_period: int = 15, rx_df: int = 1500, dx_call: str = "",
                  dx_grid: str = "", generate_messages: bool = False):
        """Send MSG_CONFIGURE to change WSJT-X operating parameters."""
        pkt = self._build_header(MSG_CONFIGURE)
        def enc_str(s):
            b = s.encode("utf-8")
            return struct.pack(">I", len(b)) + b
        pkt += enc_str(mode)
        pkt += struct.pack(">I", freq_tolerance)
        pkt += struct.pack(">I", tr_period)
        pkt += struct.pack(">I", rx_df)
        pkt += enc_str(dx_call)
        pkt += enc_str(dx_grid)
        pkt += struct.pack(">B", int(generate_messages))
        self._send(pkt)
