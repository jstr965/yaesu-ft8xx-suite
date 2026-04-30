"""
Audio Engine
Handles computer soundcard as radio mic/speaker interface.
Supports: playback, recording, VOX, waterfall FFT data, level monitoring,
          and voice clip recording + playback-over-TX.
"""

import numpy as np
import threading
import queue
import time
import wave
import os
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

try:
    import sounddevice as sd
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False

try:
    import scipy.signal as signal
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


SAMPLE_RATE    = 48000   # Standard for digital modes
BLOCK_SIZE     = 1024    # Frames per audio callback
CHANNELS       = 1       # Mono for radio
FFT_SIZE       = 2048    # For waterfall
VOX_THRESHOLD  = 0.02    # Default VOX trigger level
VOX_HANGTIME   = 0.5     # Seconds to hold PTT after audio drops


class AudioEngine(QObject):
    """
    Audio I/O engine for radio use.
    Manages input (mic → radio TX) and output (radio RX → speaker).
    """

    level_updated       = pyqtSignal(float, float)   # input_level, output_level
    fft_updated         = pyqtSignal(object)          # numpy array of FFT magnitudes
    vox_triggered       = pyqtSignal(bool)            # True = VOX keyed
    error_occurred      = pyqtSignal(str)
    status_message      = pyqtSignal(str)
    devices_changed     = pyqtSignal()

    # Voice recorder signals
    recording_started   = pyqtSignal()
    recording_stopped   = pyqtSignal(float)           # duration in seconds
    playback_started    = pyqtSignal()
    playback_finished   = pyqtSignal()
    clip_saved          = pyqtSignal(str)             # file path
    clip_loaded         = pyqtSignal(str, float)      # file path, duration

    def __init__(self, parent=None):
        super().__init__(parent)

        self._input_device: int | None  = None
        self._output_device: int | None = None
        self._stream_in:  "sd.InputStream | None"  = None
        self._stream_out: "sd.OutputStream | None" = None
        self._running = False

        # Audio queues
        self._rx_queue: queue.Queue = queue.Queue(maxsize=100)
        self._tx_queue: queue.Queue = queue.Queue(maxsize=100)

        # Level tracking
        self._input_level  = 0.0
        self._output_level = 0.0
        self._input_gain   = 1.0
        self._output_gain  = 1.0

        # VOX
        self._vox_enabled  = False
        self._vox_threshold = VOX_THRESHOLD
        self._vox_active   = False
        self._vox_hang_timer = 0.0

        # FFT buffer
        self._fft_buffer = np.zeros(FFT_SIZE)
        self._fft_window = np.hanning(FFT_SIZE)

        # Monitor timer
        self._monitor_timer = QTimer()
        self._monitor_timer.timeout.connect(self._emit_levels)
        self._monitor_timer.setInterval(50)  # 20 FPS

        # Pass-through mode (audio loops from input to output)
        self._passthrough = False

        # ── Voice Recorder ────────────────────────────────────────────────────
        self._recording        = False          # True while capture is active
        self._rec_chunks: list[np.ndarray] = [] # accumulated audio blocks
        self._rec_lock         = threading.Lock()

        self._clip: np.ndarray | None = None    # last recorded / loaded clip
        self._clip_duration    = 0.0            # seconds

        self._playing_clip     = False          # True while TX playback is running
        self._play_thread: threading.Thread | None = None

    # ─── Device Enumeration ───────────────────────────────────────────────────

    @staticmethod
    def list_devices() -> list[dict]:
        """Return list of audio devices."""
        if not AUDIO_AVAILABLE:
            return []
        try:
            devs = sd.query_devices()
            result = []
            for i, d in enumerate(devs):
                result.append({
                    "index": i,
                    "name": d["name"],
                    "inputs": d["max_input_channels"],
                    "outputs": d["max_output_channels"],
                    "sample_rate": d["default_samplerate"],
                })
            return result
        except Exception:
            return []

    @staticmethod
    def list_input_devices() -> list[tuple[int, str]]:
        return [(d["index"], d["name"]) for d in AudioEngine.list_devices() if d["inputs"] > 0]

    @staticmethod
    def list_output_devices() -> list[tuple[int, str]]:
        return [(d["index"], d["name"]) for d in AudioEngine.list_devices() if d["outputs"] > 0]

    # ─── Stream Control ───────────────────────────────────────────────────────

    def start(self, input_device: int | None = None, output_device: int | None = None) -> bool:
        """Start audio streams."""
        if not AUDIO_AVAILABLE:
            self.error_occurred.emit("sounddevice not installed. Run: pip install sounddevice")
            return False

        self._input_device  = input_device
        self._output_device = output_device

        try:
            # Input stream (mic/radio RX audio)
            self._stream_in = sd.InputStream(
                device=self._input_device,
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                blocksize=BLOCK_SIZE,
                dtype='float32',
                callback=self._input_callback,
            )

            # Output stream (audio to speaker/radio TX)
            self._stream_out = sd.OutputStream(
                device=self._output_device,
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                blocksize=BLOCK_SIZE,
                dtype='float32',
                callback=self._output_callback,
            )

            self._stream_in.start()
            self._stream_out.start()
            self._running = True
            self._monitor_timer.start()
            self.status_message.emit(f"Audio started — IN: {input_device}, OUT: {output_device}")
            return True

        except Exception as e:
            self.error_occurred.emit(f"Audio error: {e}")
            return False

    def stop(self):
        """Stop all audio streams."""
        self._running = False
        self._monitor_timer.stop()
        for stream in [self._stream_in, self._stream_out]:
            if stream:
                try:
                    stream.stop()
                    stream.close()
                except Exception:
                    pass
        self._stream_in = None
        self._stream_out = None
        self.status_message.emit("Audio stopped")

    # ─── Audio Callbacks ──────────────────────────────────────────────────────

    def _input_callback(self, indata: np.ndarray, frames: int, time_info, status):
        """Called by sounddevice for each input block."""
        if status:
            pass  # Ignore overflow warnings in production

        audio = indata[:, 0].copy() * self._input_gain
        self._input_level = float(np.sqrt(np.mean(audio ** 2)))  # RMS

        # Update FFT buffer
        if len(audio) <= FFT_SIZE:
            self._fft_buffer = np.roll(self._fft_buffer, -len(audio))
            self._fft_buffer[-len(audio):] = audio

        # VOX detection
        if self._vox_enabled:
            self._process_vox(self._input_level)

        # Voice recorder capture
        if self._recording:
            with self._rec_lock:
                self._rec_chunks.append(audio.copy())

        # Pass-through
        if self._passthrough:
            try:
                self._rx_queue.put_nowait(audio)
            except queue.Full:
                pass

        # Digital modes TX queue
        if not self._tx_queue.empty():
            pass  # Handled in output callback

    def _output_callback(self, outdata: np.ndarray, frames: int, time_info, status):
        """Called by sounddevice for each output block."""
        try:
            audio = self._rx_queue.get_nowait()
            if len(audio) >= frames:
                outdata[:, 0] = audio[:frames] * self._output_gain
            else:
                outdata[:, 0] = np.pad(audio, (0, frames - len(audio)))
            self._output_level = float(np.sqrt(np.mean(outdata[:, 0] ** 2)))
        except queue.Empty:
            outdata.fill(0)
            self._output_level = 0.0

    # ─── VOX ──────────────────────────────────────────────────────────────────

    def _process_vox(self, level: float):
        """Simple VOX processor."""
        now = time.monotonic()
        if level > self._vox_threshold:
            self._vox_hang_timer = now + VOX_HANGTIME
            if not self._vox_active:
                self._vox_active = True
                self.vox_triggered.emit(True)
        elif self._vox_active and now > self._vox_hang_timer:
            self._vox_active = False
            self.vox_triggered.emit(False)

    # ─── FFT / Waterfall ──────────────────────────────────────────────────────

    def _compute_fft(self) -> np.ndarray:
        """Compute FFT magnitude spectrum."""
        windowed = self._fft_buffer * self._fft_window
        spectrum = np.fft.rfft(windowed)
        magnitude = 20 * np.log10(np.abs(spectrum) + 1e-10)
        return magnitude

    def _emit_levels(self):
        """Emit level and FFT data on timer tick."""
        self.level_updated.emit(self._input_level, self._output_level)
        if self._running:
            fft = self._compute_fft()
            self.fft_updated.emit(fft)

    # ─── Gain / Settings ──────────────────────────────────────────────────────

    def set_input_gain(self, gain: float):
        self._input_gain = max(0.0, min(4.0, gain))

    def set_output_gain(self, gain: float):
        self._output_gain = max(0.0, min(4.0, gain))

    def set_passthrough(self, enabled: bool):
        self._passthrough = enabled
        if not enabled:
            while not self._rx_queue.empty():
                try:
                    self._rx_queue.get_nowait()
                except queue.Empty:
                    break

    def set_vox(self, enabled: bool, threshold: float = VOX_THRESHOLD):
        self._vox_enabled  = enabled
        self._vox_threshold = threshold

    def play_audio(self, audio: np.ndarray):
        """Queue audio data for playback (float32, mono)."""
        chunk_size = BLOCK_SIZE
        for i in range(0, len(audio), chunk_size):
            chunk = audio[i:i + chunk_size]
            try:
                self._rx_queue.put(chunk, timeout=1.0)
            except queue.Full:
                break

    @property
    def is_running(self) -> bool:
        return self._running

    # ─── Voice Recorder ───────────────────────────────────────────────────────

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def is_playing_clip(self) -> bool:
        return self._playing_clip

    @property
    def clip_duration(self) -> float:
        """Duration of the loaded/recorded clip in seconds."""
        return self._clip_duration

    @property
    def has_clip(self) -> bool:
        return self._clip is not None and len(self._clip) > 0

    def start_recording(self) -> bool:
        """Begin capturing microphone audio into a clip buffer."""
        if not self._running:
            self.error_occurred.emit("Start audio engine before recording.")
            return False
        if self._recording:
            return False
        with self._rec_lock:
            self._rec_chunks = []
        self._recording = True
        self.recording_started.emit()
        self.status_message.emit("Voice recorder: RECORDING…")
        return True

    def stop_recording(self) -> float:
        """
        Stop capture, assemble the clip, return duration in seconds.
        Emits recording_stopped(duration).
        """
        if not self._recording:
            return 0.0
        self._recording = False
        with self._rec_lock:
            chunks = list(self._rec_chunks)
            self._rec_chunks = []

        if chunks:
            self._clip = np.concatenate(chunks).astype(np.float32)
            self._clip_duration = len(self._clip) / SAMPLE_RATE
        else:
            self._clip = np.zeros(0, dtype=np.float32)
            self._clip_duration = 0.0

        self.recording_stopped.emit(self._clip_duration)
        self.status_message.emit(
            f"Voice recorder: clip captured ({self._clip_duration:.1f}s)")
        return self._clip_duration

    def save_clip(self, path: str) -> bool:
        """Save the current clip to a WAV file."""
        if not self.has_clip:
            self.error_occurred.emit("No clip to save.")
            return False
        try:
            pcm = (self._clip * 32767).clip(-32768, 32767).astype(np.int16)
            with wave.open(path, 'w') as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(2)          # 16-bit
                wf.setframerate(SAMPLE_RATE)
                wf.writeframes(pcm.tobytes())
            self.clip_saved.emit(path)
            self.status_message.emit(f"Clip saved: {os.path.basename(path)}")
            return True
        except Exception as e:
            self.error_occurred.emit(f"Save failed: {e}")
            return False

    def load_clip(self, path: str) -> bool:
        """Load a WAV file as the current clip."""
        try:
            with wave.open(path, 'r') as wf:
                raw = wf.readframes(wf.getnframes())
                pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                # Mix to mono if stereo
                if wf.getnchannels() == 2:
                    pcm = pcm.reshape(-1, 2).mean(axis=1)
                # Resample if needed (simple decimation/repeat — good enough for voice)
                src_rate = wf.getframerate()
                if src_rate != SAMPLE_RATE:
                    ratio = SAMPLE_RATE / src_rate
                    new_len = int(len(pcm) * ratio)
                    pcm = np.interp(
                        np.linspace(0, len(pcm) - 1, new_len),
                        np.arange(len(pcm)),
                        pcm
                    ).astype(np.float32)
            self._clip = pcm
            self._clip_duration = len(pcm) / SAMPLE_RATE
            self.clip_loaded.emit(path, self._clip_duration)
            self.status_message.emit(
                f"Clip loaded: {os.path.basename(path)} ({self._clip_duration:.1f}s)")
            return True
        except Exception as e:
            self.error_occurred.emit(f"Load failed: {e}")
            return False

    def play_clip_over_tx(self, cat=None) -> bool:
        """
        Key PTT via `cat` (if provided), stream the clip to the radio audio
        output, then un-key PTT.  Runs in a background thread so the UI stays
        responsive.  Emits playback_started / playback_finished.

        Parameters
        ----------
        cat : CAT817 | None
            If supplied, PTT is keyed/un-keyed automatically around playback.
            Pass None to drive PTT manually or use VOX.
        """
        if not self.has_clip:
            self.error_occurred.emit("No clip recorded. Use the Record button first.")
            return False
        if self._playing_clip:
            self.error_occurred.emit("Playback already in progress.")
            return False
        if not self._running:
            self.error_occurred.emit("Start audio engine before transmitting.")
            return False

        self._playing_clip = True
        self.playback_started.emit()

        def _run():
            try:
                if cat is not None:
                    cat.set_ptt(True)
                    time.sleep(0.15)        # brief delay for radio to key up

                self.play_audio(self._clip * self._output_gain)

                # Wait until the queue drains (clip fully played)
                drain_timeout = self._clip_duration + 3.0
                deadline = time.monotonic() + drain_timeout
                while not self._rx_queue.empty() and time.monotonic() < deadline:
                    time.sleep(0.05)

                # Small tail to avoid clipping the last syllable
                time.sleep(0.15)

            finally:
                if cat is not None:
                    cat.set_ptt(False)
                self._playing_clip = False
                self.playback_finished.emit()
                self.status_message.emit("Voice TX complete.")

        self._play_thread = threading.Thread(target=_run, daemon=True)
        self._play_thread.start()
        return True

    def stop_clip_playback(self, cat=None):
        """Abort an in-progress TX playback immediately."""
        if not self._playing_clip:
            return
        # Flush the output queue so audio stops instantly
        while not self._rx_queue.empty():
            try:
                self._rx_queue.get_nowait()
            except queue.Empty:
                break
        if cat is not None:
            cat.set_ptt(False)
        # _playing_clip will be cleared by the thread's finally block
