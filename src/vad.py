"""Voice Activity Detection module."""

import numpy as np
from enum import Enum
from . import config


class VADState(Enum):
    SILENCE = 0
    RECORDING = 1
    PROCESSING = 2


class VAD:
    """Energy-based Voice Activity Detection with dynamic thresholding."""

    def __init__(self, background_rms: float = 100.0):
        self.state = VADState.SILENCE
        self.background_rms = background_rms
        self._speech_buffer = []
        self._silence_frames = 0
        self._speech_frames = 0

        # Calculate frame counts
        self._min_speech_frames = int(config.VAD_MIN_SPEECH_MS * config.SAMPLE_RATE / 1000 / config.CHUNK_SIZE)
        self._max_speech_frames = int(config.VAD_MAX_SPEECH_MS * config.SAMPLE_RATE / 1000 / config.CHUNK_SIZE)
        self._silence_frames_threshold = int(config.VAD_SILENCE_MS * config.SAMPLE_RATE / 1000 / config.CHUNK_SIZE)

    def set_background(self, rms: float):
        """Update background RMS."""
        self.background_rms = max(rms, 50.0)  # minimum floor

    def _get_threshold(self) -> float:
        """Get dynamic energy threshold."""
        low = self.background_rms * config.VAD_ENERGY_THRESHOLD_MULT_LOW
        high = self.background_rms * config.VAD_ENERGY_THRESHOLD_MULT_HIGH
        return (low + high) / 2

    def _compute_energy(self, samples: np.ndarray) -> float:
        """Compute RMS energy of samples."""
        if len(samples) == 0:
            return 0.0
        return np.sqrt(np.mean(samples.astype(np.float32) ** 2))

    def _compute_zcr(self, samples: np.ndarray) -> float:
        """Compute zero crossing rate."""
        if len(samples) < 2:
            return 0.0
        signs = np.sign(samples)
        signs[signs == 0] = 1
        crossings = np.sum(np.abs(np.diff(signs)) > 0)
        return crossings / len(samples)

    def process_chunk(self, chunk: np.ndarray) -> tuple:
        """
        Process audio chunk and return (state, speech_segment or None).

        Returns:
            (VADState, np.ndarray or None): Current state and completed speech segment if any
        """
        energy = self._compute_energy(chunk)
        threshold = self._get_threshold()
        is_speech = energy > threshold

        if self.state == VADState.SILENCE:
            if is_speech:
                self.state = VADState.RECORDING
                self._speech_buffer = [chunk.copy()]
                self._speech_frames = 1
                self._silence_frames = 0
            return (self.state, None)

        elif self.state == VADState.RECORDING:
            self._speech_buffer.append(chunk.copy())
            self._speech_frames += 1

            if is_speech:
                self._silence_frames = 0
            else:
                self._silence_frames += 1

            # Check for end of speech or max length
            if self._silence_frames >= self._silence_frames_threshold or \
               self._speech_frames >= self._max_speech_frames:

                # Check minimum length
                if self._speech_frames >= self._min_speech_frames:
                    self.state = VADState.PROCESSING
                    segment = np.concatenate(self._speech_buffer)
                    self._speech_buffer = []
                    return (self.state, segment)
                else:
                    # Too short, discard
                    self._speech_buffer = []
                    self.state = VADState.SILENCE

            return (self.state, None)

        elif self.state == VADState.PROCESSING:
            # Wait for external reset
            return (self.state, None)

        return (self.state, None)

    def reset(self):
        """Reset VAD to silence state."""
        self.state = VADState.SILENCE
        self._speech_buffer = []
        self._silence_frames = 0
        self._speech_frames = 0


def preprocess_audio(audio: np.ndarray) -> np.ndarray:
    """
    Preprocess audio for feature extraction.
    - Remove DC offset
    - Pre-emphasis
    - RMS normalization
    """
    # Convert to float
    audio = audio.astype(np.float32)

    # Remove DC offset
    audio = audio - np.mean(audio)

    # Pre-emphasis
    pre_emphasis = 0.97
    audio = np.append(audio[0], audio[1:] - pre_emphasis * audio[:-1])

    # RMS normalization
    rms = np.sqrt(np.mean(audio ** 2))
    if rms > 0:
        audio = audio / rms * 0.1  # normalize to ~0.1 RMS

    return audio
