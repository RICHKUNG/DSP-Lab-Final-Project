"""Audio I/O module with ring buffer for microphone input using sounddevice."""

import queue
import threading
from collections import deque
from typing import Optional, Tuple

import numpy as np
import sounddevice as sd
from scipy.signal import resample_poly

from . import config


def find_suitable_device(sample_rate=16000, verbose=False, preferred_device_index: Optional[int] = None) -> Optional[Tuple[int, int]]:
    """Find an input device that supports the given sample rate using sounddevice.

    Args:
        sample_rate: Target sample rate for audio stream.
        verbose: Print detailed search process.
        preferred_device_index: If provided, this device will be tried first.

    Returns:
        (int, int): (Device index, working sample rate) or None if not found
    """
    if verbose:
        print(f"Scanning audio devices via sounddevice ({sd.__version__})...")
        print(f"Host API: {sd.get_portaudio_version()}")

    def _check_device(idx: int, rate: int) -> bool:
        try:
            sd.check_input_settings(
                device=idx,
                channels=1,
                dtype='int16',
                samplerate=rate
            )
            if verbose:
                print(f"    OK at {rate} Hz")
            return True
        except Exception as e:
            if verbose:
                print(f"    Failed at {rate} Hz: {e}")
            return False

    # Get all devices
    devices = sd.query_devices()
    
    # 1. Try preferred device if specified
    if preferred_device_index is not None:
        if 0 <= preferred_device_index < len(devices):
            d = devices[preferred_device_index]
            name = d.get('name', 'Unknown')
            max_in = d.get('max_input_channels', 0)
            
            if verbose:
                print(f"\nTesting PREFERRED device {preferred_device_index}: {name}")
            
            if max_in > 0:
                # Try preferred sample rate first, then standard ones
                def_rate = int(d.get('default_samplerate', sample_rate))
                rates_to_try = [sample_rate, def_rate, 48000, 44100, 32000, 16000]
                # Deduplicate preserving order
                rates_to_try = list(dict.fromkeys(rates_to_try))
                
                for r in rates_to_try:
                    if _check_device(preferred_device_index, r):
                        return preferred_device_index, r
            else:
                if verbose:
                    print("    Skipping: No input channels.")
        else:
            if verbose:
                print(f"\nPreferred device index {preferred_device_index} is out of range.")

    # 2. Try default input device
    # But first, prioritize WASAPI devices if available (better for Windows)
    if verbose:
        print("\nScanning for WASAPI devices (preferred)...")
    
    wasapi_candidates = []
    host_apis = sd.query_hostapis()
    wasapi_api_index = -1
    for i, api in enumerate(host_apis):
        if 'WASAPI' in api['name']:
            wasapi_api_index = i
            break
            
    if wasapi_api_index >= 0:
        for idx, d in enumerate(devices):
            if d['hostapi'] == wasapi_api_index and d['max_input_channels'] > 0:
                wasapi_candidates.append(idx)
                
        for idx in wasapi_candidates:
            d = devices[idx]
            if verbose:
                print(f"Testing WASAPI device {idx}: {d['name']}")
                
            rates_to_try = [sample_rate, 48000, 44100]
            # Prioritize default rate for WASAPI
            def_rate = int(d.get('default_samplerate', 0))
            if def_rate > 0:
                rates_to_try.insert(0, def_rate)
            rates_to_try = list(dict.fromkeys(rates_to_try))

            for r in rates_to_try:
                if _check_device(idx, r):
                    return idx, r

    # Fallback to default device if WASAPI failed
    default_in = sd.default.device[0]
    if default_in >= 0:
        if verbose:
            print(f"\nTesting DEFAULT device {default_in}: {devices[default_in]['name']}")
        
        rates_to_try = [sample_rate, int(devices[default_in]['default_samplerate'])]
        rates_to_try = list(dict.fromkeys(rates_to_try))
        
        for r in rates_to_try:
            if _check_device(default_in, r):
                return default_in, r

    # 3. Scan all other devices
    if verbose:
        print("\nScanning all other input devices...")
        
    for idx, d in enumerate(devices):
        # Skip already checked
        if idx == preferred_device_index or idx == default_in:
            continue
            
        if d['max_input_channels'] > 0:
            if verbose:
                print(f"Testing device {idx}: {d['name']} (API: {d.get('hostapi', '?')})")
            
            # Prioritize standard rates
            rates_to_try = [sample_rate, 48000, 44100, 16000]
            def_rate = int(d.get('default_samplerate', 0))
            if def_rate > 0:
                rates_to_try.insert(1, def_rate)
            
            rates_to_try = list(dict.fromkeys(rates_to_try))
            
            for r in rates_to_try:
                if _check_device(idx, r):
                    return idx, r

    return None


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
    """Non-blocking audio stream from microphone using sounddevice."""

    def __init__(self, device_index=None, input_rate=None, target_rate=None):
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

    def _callback(self, indata, frames, time, status):
        """Sounddevice callback."""
        if status:
            print(f"[Audio Warning] {status}")
            
        # indata is (frames, channels)
        # Select first channel if multiple
        if indata.shape[1] > 1:
            samples = indata[:, 0]
        else:
            samples = indata.flatten()
        
        # Resample if needed
        samples = self._resample_to_target(samples)
        
        self._ring_buffer.append(samples)
        self._output_queue.put(samples.copy())

    def start(self):
        """Start audio stream."""
        self._running = True
        
        # Check if device uses WASAPI
        extra_settings = None
        try:
            if self._device_index is not None:
                dev_info = sd.query_devices(self._device_index)
                host_api_idx = dev_info['hostapi']
                host_api_info = sd.query_hostapis(host_api_idx)
                if 'WASAPI' in host_api_info['name']:
                    # Explicitly request shared mode
                    extra_settings = sd.WasapiSettings(exclusive=False)
        except Exception:
            pass

        try:
            # Try with 1 channel first (standard)
            self._stream = sd.InputStream(
                samplerate=self._input_rate,
                blocksize=self._frames_per_buffer,
                device=self._device_index,
                channels=1,
                dtype='int16',
                callback=self._callback,
                extra_settings=extra_settings
            )
            self._stream.start()
        except Exception as e:
            print(f"Standard open failed ({e}), attempting fallbacks...")
            
            # Fallback 1: Native channels (for WASAPI strictness)
            try:
                if self._device_index is not None:
                    dev_info = sd.query_devices(self._device_index)
                    native_channels = dev_info['max_input_channels']
                    if native_channels > 1:
                        print(f"Trying with native {native_channels} channels...")
                        self._stream = sd.InputStream(
                            samplerate=self._input_rate,
                            blocksize=self._frames_per_buffer,
                            device=self._device_index,
                            channels=native_channels,
                            dtype='int16',
                            callback=self._callback,
                            extra_settings=extra_settings
                        )
                        self._stream.start()
                        return # Success
            except Exception as inner_e:
                print(f"Native channel fallback failed: {inner_e}")

            # Fallback 2: MME (The "Nuclear Option" for compatibility)
            # If we were forcing a specific device index, this might be tricky because indexes change per API.
            # But we can try to find the same device under MME.
            try:
                print("Attempting final fallback: MME driver...")
                # Find MME API index
                mme_idx = -1
                for i, api in enumerate(sd.query_hostapis()):
                    if 'MME' in api['name']:
                        mme_idx = i
                        break
                
                if mme_idx >= 0 and self._device_index is not None:
                     # Try to find the same device name under MME
                    current_name = sd.query_devices(self._device_index)['name']
                    mme_dev_idx = -1
                    for i, d in enumerate(sd.query_devices()):
                        if d['hostapi'] == mme_idx and d['name'] in current_name: # Partial match name
                             mme_dev_idx = i
                             break
                    
                    if mme_dev_idx >= 0:
                        print(f"Found MME equivalent device {mme_dev_idx}, trying...")
                        self._stream = sd.InputStream(
                            samplerate=self._input_rate,
                            blocksize=self._frames_per_buffer,
                            device=mme_dev_idx,
                            channels=1, # MME is usually fine with 1 channel
                            dtype='int16',
                            callback=self._callback
                        )
                        self._stream.start()
                        return # Success
            except Exception as mme_e:
                print(f"MME fallback failed: {mme_e}")

            
            # Re-raise original error if all fallbacks didn't work
            self._running = False
            raise e

    def stop(self):
        """Stop audio stream."""
        self._running = False
        if self._stream:
            self._stream.stop()
            self._stream.close()

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
        if len(audio) == 0:
            return 50.0 # Fallback
            
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