"""
Yaesu CAT Control Core
Supports: FT-817/817ND/818, FT-857/857D, FT-897/897D
All three share the same 5-byte CAT protocol at the same baud rates.
Reference: Yaesu CAT Operation Manuals (FT-817, FT-857, FT-897)
"""

import serial
import serial.tools.list_ports
import threading
import time
import struct
from enum import IntEnum
from PyQt6.QtCore import QObject, pyqtSignal, QTimer


# ─── Supported Radio Models ───────────────────────────────────────────────────

RADIO_MODELS = {
    "FT-817":  {
        "name":       "FT-817 / 817ND",
        "max_power":  5,
        "power_steps":["5W", "2.5W", "1W", "500mW", "250mW", "100mW", "50mW", "10mW"],
        "has_vhf_uhf": True,
        "cat_menu":   14,       # Menu number for CAT baud rate
        "hamlib_id":  1688,
        "notes":      "CAT port: front panel 3.5mm DATA jack via Digirig or CT-62",
    },
    "FT-818":  {
        "name":       "FT-818 / 818ND",
        "max_power":  6,
        "power_steps":["6W", "2.5W", "1W", "500mW", "250mW", "100mW", "50mW", "10mW"],
        "has_vhf_uhf": True,
        "cat_menu":   14,
        "hamlib_id":  1688,
        "notes":      "CAT port: front panel 3.5mm DATA jack via Digirig or CT-62",
    },
    "FT-857":  {
        "name":       "FT-857 / 857D",
        "max_power":  100,
        "power_steps":["100W", "50W", "20W", "10W", "5W"],
        "has_vhf_uhf": True,
        "cat_menu":   59,       # Menu CAT RATE on FT-857
        "hamlib_id":  1621,
        "notes":      "CAT port: rear panel 6-pin mini-DIN ACC jack",
    },
    "FT-897":  {
        "name":       "FT-897 / 897D",
        "max_power":  100,
        "power_steps":["100W", "50W", "20W", "10W", "5W"],
        "has_vhf_uhf": True,
        "cat_menu":   59,
        "hamlib_id":  1625,
        "notes":      "CAT port: rear panel DB-9 RS-232 or 6-pin mini-DIN",
    },
}

# Default to FT-817 for backward compatibility
DEFAULT_RADIO = "FT-817"


# ─── Mode Bytes (identical across all three radios) ───────────────────────────

class FT817Mode(IntEnum):
    LSB  = 0x00
    USB  = 0x01
    CW   = 0x02
    CWR  = 0x03
    AM   = 0x04
    FM   = 0x08
    DIG  = 0x0A
    PKT  = 0x0C
    FMN  = 0x88


MODE_NAMES = {
    FT817Mode.LSB:  "LSB",
    FT817Mode.USB:  "USB",
    FT817Mode.CW:   "CW",
    FT817Mode.CWR:  "CW-R",
    FT817Mode.AM:   "AM",
    FT817Mode.FM:   "FM",
    FT817Mode.DIG:  "DIG",
    FT817Mode.PKT:  "PKT",
    FT817Mode.FMN:  "FM-N",
}

MODE_BYTES = {v: k for k, v in MODE_NAMES.items()}

# ─── CAT Command Bytes ────────────────────────────────────────────────────────

CMD_SET_FREQ      = 0x01
CMD_SET_MODE      = 0x07
CMD_GET_FREQ      = 0x03
CMD_PTT_ON        = 0x08
CMD_PTT_OFF       = 0x88
CMD_GET_STATUS    = 0xE7
CMD_LOCK_ON       = 0x00
CMD_LOCK_OFF      = 0x80
CMD_STEP_UP       = 0x0C
CMD_STEP_DOWN     = 0x8C
CMD_RPT_SHIFT     = 0x09
CMD_GET_RX_STATUS = 0xE7
CMD_GET_TX_STATUS = 0xF7
CMD_GET_SMETER    = 0xE7
CMD_READ_CONFIG   = 0xA7   # Returns 9 bytes — byte 6 contains supply voltage

FREQ_STEPS = [10, 100, 500, 1000, 5000, 10000, 25000, 50000, 100000, 500000, 1000000]

# ─── Voltage decoding ─────────────────────────────────────────────────────────
# The 0xA7 response byte 6 encodes supply voltage as BCD tenths-of-a-volt.
# e.g. 0x98 = 9.8V (internal NiMH low), 0xC8 = 12.8V (external supply)
# Range: ~8.0V (dead batteries) to 16.0V (external DC).
# For the FT-857/897 the same register works but typical external voltage is 13.8V.

def decode_voltage(raw_byte: int) -> float:
    """Decode BCD voltage byte from 0xA7 response. Returns volts as float."""
    hi = (raw_byte >> 4) & 0x0F   # Tens of volts digit
    lo =  raw_byte & 0x0F          # Tenths of volts digit
    return hi + lo / 10.0


class CAT817(QObject):
    """
    Yaesu CAT Controller — FT-817, FT-818, FT-857, FT-897.
    All models share the identical 5-byte CAT protocol.
    Select the radio model at connect time.
    """

    # Signals
    connected         = pyqtSignal(bool)
    frequency_changed = pyqtSignal(int)
    mode_changed      = pyqtSignal(str)
    ptt_changed       = pyqtSignal(bool)
    smeter_updated    = pyqtSignal(int)
    voltage_updated   = pyqtSignal(float)   # Supply voltage in volts
    tx_power_updated  = pyqtSignal(int)
    error_occurred    = pyqtSignal(str)
    status_message    = pyqtSignal(str)
    radio_changed     = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ser: serial.Serial | None = None
        self._lock = threading.Lock()
        self._running = False
        self._poll_thread: threading.Thread | None = None

        # Cached state
        self.frequency: int = 14074000
        self.mode: str = "USB"
        self.ptt: bool = False
        self.smeter: int = 0
        self.voltage: float = 0.0
        self.tx_power: int = 0
        self._is_connected: bool = False
        self._poll_count: int = 0   # Used to throttle voltage reads

        # Radio model
        self._radio_model: str = DEFAULT_RADIO

        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._poll_radio)
        self._poll_timer.setInterval(250)

    # ─── Radio Model ──────────────────────────────────────────────────────────

    @property
    def radio_model(self) -> str:
        return self._radio_model

    @property
    def radio_info(self) -> dict:
        return RADIO_MODELS.get(self._radio_model, RADIO_MODELS[DEFAULT_RADIO])

    def set_radio_model(self, model: str):
        """Change the selected radio model."""
        if model in RADIO_MODELS:
            self._radio_model = model
            self.radio_changed.emit(model)
            self.status_message.emit(f"Radio model set to {RADIO_MODELS[model]['name']}")

    @property
    def max_power_watts(self) -> int:
        return self.radio_info["max_power"]

    @property
    def power_steps(self) -> list[str]:
        return self.radio_info["power_steps"]

    @property
    def hamlib_rig_id(self) -> int:
        return self.radio_info["hamlib_id"]

    # ─── Connection ───────────────────────────────────────────────────────────

    @staticmethod
    def list_ports() -> list[str]:
        return [p.device for p in serial.tools.list_ports.comports()]

    def connect(self, port: str, baud: int = 9600) -> bool:
        """Open serial connection to radio."""
        try:
            self._ser = serial.Serial(
                port=port,
                baudrate=baud,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_TWO,
                timeout=0.5,
                write_timeout=0.5,
                rtscts=False,
                dsrdtr=False,
            )

            # Force RTS/DTR low immediately — prevents accidental PTT on connect
            self._ser.rts = False
            self._ser.dtr = False
            time.sleep(0.3)

            self._ser.reset_input_buffer()
            self._ser.reset_output_buffer()

            # Explicit PTT-off as belt-and-suspenders
            self._send_ptt(False)
            time.sleep(0.1)

            self._is_connected = True
            self.connected.emit(True)
            info = self.radio_info
            self.status_message.emit(
                f"Connected to {info['name']} on {port} @ {baud} baud"
            )

            self._read_frequency()
            self._poll_timer.start()
            return True

        except serial.SerialException as e:
            self.error_occurred.emit(f"Connection failed: {e}")
            self._is_connected = False
            return False

    def disconnect(self):
        """Close serial connection."""
        self._poll_timer.stop()
        if self._ser and self._ser.is_open:
            try:
                self._send_ptt(False)
                time.sleep(0.1)
                self._ser.rts = False
                self._ser.dtr = False
                time.sleep(0.05)
                self._ser.close()
            except Exception:
                pass
        self._ser = None
        self._is_connected = False
        self.connected.emit(False)
        self.status_message.emit("Disconnected from radio")

    @property
    def is_connected(self) -> bool:
        return self._is_connected and self._ser is not None and self._ser.is_open

    # ─── CAT Command Engine ───────────────────────────────────────────────────

    def _send_command(self, p1=0x00, p2=0x00, p3=0x00, p4=0x00, cmd=0x00) -> bytes | None:
        if not self.is_connected:
            return None
        payload = bytes([p1, p2, p3, p4, cmd])
        try:
            with self._lock:
                self._ser.reset_input_buffer()
                self._ser.write(payload)
                time.sleep(0.05)
                if self._ser.in_waiting:
                    return self._ser.read(self._ser.in_waiting)
                return b""
        except serial.SerialException as e:
            self._is_connected = False
            self.connected.emit(False)
            self.error_occurred.emit(f"Serial error: {e}")
            return None

    # ─── Frequency ────────────────────────────────────────────────────────────

    def _bcd_encode_freq(self, freq_hz: int):
        freq_10hz = freq_hz // 10
        p1 = ((freq_10hz // 10000000) << 4) | ((freq_10hz // 1000000) % 10)
        p2 = (((freq_10hz // 100000) % 10) << 4) | ((freq_10hz // 10000) % 10)
        p3 = (((freq_10hz // 1000) % 10) << 4) | ((freq_10hz // 100) % 10)
        p4 = (((freq_10hz // 10) % 10) << 4) | (freq_10hz % 10)
        return p1, p2, p3, p4

    def _bcd_decode_freq(self, data: bytes) -> int:
        if len(data) < 5:
            return 0
        digits = ""
        for b in data[:4]:
            digits += f"{(b >> 4) & 0xF}{b & 0xF}"
        return int(digits) * 10

    def set_frequency(self, freq_hz: int):
        p1, p2, p3, p4 = self._bcd_encode_freq(freq_hz)
        self._send_command(p1, p2, p3, p4, CMD_SET_FREQ)
        self.frequency = freq_hz
        self.frequency_changed.emit(freq_hz)

    def _read_frequency(self):
        resp = self._send_command(0, 0, 0, 0, CMD_GET_FREQ)
        if resp and len(resp) >= 5:
            freq = self._bcd_decode_freq(resp)
            if freq > 0 and freq != self.frequency:
                self.frequency = freq
                self.frequency_changed.emit(freq)
                mode_byte = resp[4] & 0x0F   # Mask filter bit (0x80) for 857/897
                mode_name = MODE_NAMES.get(mode_byte, "USB")
                if mode_name != self.mode:
                    self.mode = mode_name
                    self.mode_changed.emit(mode_name)

    # ─── Mode ─────────────────────────────────────────────────────────────────

    def set_mode(self, mode_name: str):
        mode_byte = MODE_BYTES.get(mode_name)
        if mode_byte is None:
            return
        self._send_command(mode_byte, 0, 0, 0, CMD_SET_MODE)
        self.mode = mode_name
        self.mode_changed.emit(mode_name)

    # ─── PTT ──────────────────────────────────────────────────────────────────

    def _send_ptt(self, state: bool):
        cmd = CMD_PTT_ON if state else CMD_PTT_OFF
        self._send_command(0, 0, 0, 0, cmd)

    def set_ptt(self, state: bool):
        self._send_ptt(state)
        self.ptt = state
        self.ptt_changed.emit(state)

    # ─── Polling ──────────────────────────────────────────────────────────────

    def _poll_radio(self):
        if not self.is_connected:
            self._poll_timer.stop()
            return

        self._poll_count += 1

        # Frequency + mode — every poll (4x/sec)
        self._read_frequency()

        # S-meter — every poll
        resp = self._send_command(0, 0, 0, 0, CMD_GET_RX_STATUS)
        if resp and len(resp) >= 1:
            smeter = resp[0] & 0x0F
            self.smeter = smeter
            self.smeter_updated.emit(smeter)

        # Supply voltage — every 10 seconds (every 40 polls)
        # Voltage changes slowly so no need to hammer it
        if self._poll_count % 40 == 0:
            self._read_voltage()

    def _read_voltage(self):
        """Read supply voltage via 0xA7 Radio Configuration command."""
        resp = self._send_command(0, 0, 0, 0, CMD_READ_CONFIG)
        if resp and len(resp) >= 7:
            # Byte index 6 (0-based) contains the supply voltage BCD value
            raw = resp[6]
            volts = decode_voltage(raw)
            # Sanity check — valid range for these radios is 8.0V to 16.0V
            if 5.0 <= volts <= 16.0:
                self.voltage = volts
                self.voltage_updated.emit(volts)

    # ─── Band / Frequency Helpers ─────────────────────────────────────────────

    @staticmethod
    def get_band(freq_hz: int) -> str:
        bands = [
            (1800000,   2000000,   "160m"),
            (3500000,   4000000,   "80m"),
            (5330500,   5403500,   "60m"),
            (7000000,   7300000,   "40m"),
            (10100000,  10150000,  "30m"),
            (14000000,  14350000,  "20m"),
            (18068000,  18168000,  "17m"),
            (21000000,  21450000,  "15m"),
            (24890000,  24990000,  "12m"),
            (28000000,  29700000,  "10m"),
            (50000000,  54000000,  "6m"),
            (144000000, 148000000, "2m"),
            (430000000, 440000000, "70cm"),
        ]
        for lo, hi, name in bands:
            if lo <= freq_hz <= hi:
                return name
        return "OOB"

    @staticmethod
    def format_frequency(freq_hz: int) -> str:
        mhz = freq_hz // 1_000_000
        khz = (freq_hz % 1_000_000) // 1_000
        hz  = freq_hz % 1_000
        return f"{mhz:3d}.{khz:03d}.{hz:03d}"

    @staticmethod
    def get_digital_freq(band: str, mode: str = "FT8") -> int | None:
        table = {
            ("160m", "FT8"):   1840000,
            ("80m",  "FT8"):   3573000,
            ("60m",  "FT8"):   5357000,
            ("40m",  "FT8"):   7074000,
            ("30m",  "FT8"):  10136000,
            ("20m",  "FT8"):  14074000,
            ("17m",  "FT8"):  18100000,
            ("15m",  "FT8"):  21074000,
            ("12m",  "FT8"):  24915000,
            ("10m",  "FT8"):  28074000,
            ("6m",   "FT8"):  50313000,
            ("2m",   "FT8"): 144174000,
            ("40m",  "FT4"):   7047500,
            ("20m",  "FT4"):  14080000,
            ("20m",  "JS8"):  14078000,
            ("40m",  "WSPR"):  7038600,
            ("20m",  "WSPR"): 14095600,
            ("20m",  "JT65"): 14076000,
        }
        return table.get((band, mode))

