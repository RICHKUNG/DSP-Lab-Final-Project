"""Audio I/O module with ring buffer for microphone input."""

import queue
import threading
from collections import deque

import numpy as np
import pyaudio
from scipy.signal import resample_poly

from . import config


def find_suitable_device(sample_rate=16000, verbose=False):
    """Find an input device that supports the given sample rate.

    Returns:
        (int, int): (Device index, working sample rate) or None if not found
    """
    pa = pyaudio.PyAudio()
    last_error = None

    def _try_open(index: int, rate: int) -> bool:
        """Attempt to open device at rate; return success bool."""
        nonlocal last_error
        if verbose:
            print(f"  - Trying device {index} at {rate} Hz...")

        try:
            # Quick capability check
            pa.is_format_supported(
                rate,
                input_device=index,
                input_channels=1,
                input_format=pyaudio.paInt16,
            )
        except Exception as e:  # ValueError or OSError from PortAudio
            last_error = str(e)
            if verbose:
                print(f"    Format check failed: {last_error}")
            return False

        try:
            test_stream = pa.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=rate,
                input=True,
                input_device_index=index,
                frames_per_buffer=512,
                start=False,  # do not start to keep this lightweight
            )
            test_stream.close()
            if verbose:
                print(f"    OK at {rate} Hz")
            return True
        except Exception as e:
            last_error = str(e)
            if verbose:
                print(f"    Open failed: {last_error}")
            return False

    try:
        # Try default input device first
        try:
            default_info = pa.get_default_input_device_info()
            default_index = default_info["index"]
            default_rate = int(default_info.get("defaultSampleRate", sample_rate))

            if verbose:
                print(f"Testing default device {default_index} ({default_info.get('name', 'Unknown')})")

            rates_to_try = [sample_rate]
            if default_rate != sample_rate:
                rates_to_try.append(default_rate)
            # Add common rates to fallback list
            for r in [16000, 44100, 48000, 32000, 8000, 88200, 96000]:
                if r not in rates_to_try:
                    rates_to_try.append(r)

            for rate in rates_to_try:
                if _try_open(default_index, int(rate)):
                    return default_index, int(rate)
        except Exception as e:
            last_error = str(e)
            if verbose:
                print(f"Default device failed: {last_error}")

        # Search all input devices
        for i in range(pa.get_device_count()):
            try:
                info = pa.get_device_info_by_index(i)
            except Exception as e:
                last_error = str(e)
                if verbose:
                    print(f"Could not read device {i}: {last_error}")
                continue

            if info.get("maxInputChannels", 0) <= 0:
                continue

            if verbose:
                print(f"\nTesting device {i}: {info.get('name', 'Unknown')}")

            default_rate = int(info.get("defaultSampleRate", sample_rate))
            rates = [sample_rate, default_rate]
            for r in [16000, 44100, 48000, 32000, 8000]:
                if r not in rates:
                    rates.append(r)

            for rate in rates:
                if _try_open(i, rate):
                    return i, int(rate)

        if verbose and last_error:
            print(f"No working device found. Last error: {last_error}")
        return None
    finally:
        pa.terminate()


class RingBuffer:
    """Thread-safe ring buffer for audio samples."""

    def __init__(self, max_duration_ms: int = 500):
        max_samples = int(config.SAMPLE_RATE * max_duration_ms / 1000)
        self._buffer = deque(maxlen=max_samples)
        self._lock = threading.Lock()

    def append(self, samples: np.ndarray):
        with self._lock:
            for s in samples:
                self._buffer.append(s)

    def get_all(self) -> np.ndarray:
        with self._lock:
            return np.array(list(self._buffer), dtype=np.int16)

    def get_last_ms(self, ms: int) -> np.ndarray:
        n_samples = int(config.SAMPLE_RATE * ms / 1000)
        with self._lock:
            data = list(self._buffer)
            return np.array(data[-n_samples:] if len(data) >= n_samples else data, dtype=np.int16)

    def clear(self):
        with self._lock:
            self._buffer.clear()


class AudioStream:
    """Non-blocking audio stream from microphone."""

    def __init__(self, device_index=None, input_rate=None, target_rate=None):
        self._pa = pyaudio.PyAudio()
        self._stream = None
        self._ring_buffer = RingBuffer()
        self._output_queue = queue.Queue()
        self._running = False
        self._background_rms = None
        self._device_index = device_index

        self._target_rate = target_rate or config.SAMPLE_RATE
        self._input_rate = input_rate or self._target_rate
        self._needs_resample = self._input_rate != self._target_rate
        # Maintain roughly the same window duration when resampling
        if self._needs_resample:
            self._frames_per_buffer = max(
                1, int(round(config.CHUNK_SIZE * self._input_rate / self._target_rate))
            )
        else:
            self._frames_per_buffer = config.CHUNK_SIZE

    def _resample_to_target(self, samples: np.ndarray) -> np.ndarray:
        """Resample from input rate to target rate."""
        if not self._needs_resample:
            return samples
        resampled = resample_poly(samples.astype(np.float32), self._target_rate, self._input_rate)
        return np.asarray(resampled, dtype=np.int16)

    def _callback(self, in_data, frame_count, time_info, status):
        samples = np.frombuffer(in_data, dtype=np.int16)
        samples = self._resample_to_target(samples)
        self._ring_buffer.append(samples)
        self._output_queue.put(samples.copy())
        return (None, pyaudio.paContinue)

    def start(self):
        """Start audio stream."""
        kwargs = {
            'format': pyaudio.paInt16,
            'channels': config.CHANNELS,
            'rate': self._input_rate,
            'input': True,
            'frames_per_buffer': self._frames_per_buffer,
            'stream_callback': self._callback
        }

        # Add device index if specified
        if self._device_index is not None:
            kwargs['input_device_index'] = self._device_index

        self._stream = self._pa.open(**kwargs)
        self._running = True
        self._stream.start_stream()

    def stop(self):
        """Stop audio stream."""
        self._running = False
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
        self._pa.terminate()

    def get_chunk(self, timeout: float = 0.1) -> np.ndarray:
        """Get next audio chunk from queue."""
        try:
            return self._output_queue.get(timeout=timeout)
        except queue.Empty:
            return np.array([], dtype=np.int16)

    def get_pre_roll(self, ms: int) -> np.ndarray:
        """Get pre-roll samples from ring buffer."""
        return self._ring_buffer.get_last_ms(ms)

    def measure_background(self, duration_ms: int = 1500) -> float:
        """Measure background RMS for VAD calibration."""
        samples_needed = int(self._target_rate * duration_ms / 1000)
        collected = []

        while len(collected) < samples_needed:
            chunk = self.get_chunk(timeout=0.5)
            if len(chunk) > 0:
                collected.extend(chunk)

        audio = np.array(collected[:samples_needed], dtype=np.float32)
        self._background_rms = np.sqrt(np.mean(audio ** 2))
        return self._background_rms

    @property
    def background_rms(self) -> float:
        return self._background_rms if self._background_rms else 100.0


def load_audio_file(filepath: str) -> np.ndarray:
    """Load audio file and convert to 16kHz mono."""
    import librosa
    y, sr = librosa.load(filepath, sr=config.SAMPLE_RATE, mono=True)
    # Convert to int16
    y = (y * 32767).astype(np.int16)
    return y


def save_audio_file(filepath: str, audio: np.ndarray):
    """Save audio to file."""
    import soundfile as sf
    # Convert int16 to float
    if audio.dtype == np.int16:
        audio = audio.astype(np.float32) / 32767.0
    sf.write(filepath, audio, config.SAMPLE_RATE)
