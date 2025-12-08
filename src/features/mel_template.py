"""Mel-spectrogram template feature extraction."""

import numpy as np
import librosa
from scipy.ndimage import zoom
from .. import config


def extract_mel_template(audio: np.ndarray, fixed_frames: int = None) -> np.ndarray:
    """
    Extract mel-spectrogram and resize to fixed dimensions.

    Args:
        audio: Audio samples
        fixed_frames: Target number of frames (default from config)

    Returns:
        Mel-spectrogram template (n_mels, fixed_frames)
    """
    if fixed_frames is None:
        fixed_frames = config.TEMPLATE_FIXED_FRAMES

    # Ensure float32
    if audio.dtype != np.float32:
        audio = audio.astype(np.float32)
        if np.max(np.abs(audio)) > 1.0:
            audio = audio / 32768.0

    # Extract mel-spectrogram
    mel = librosa.feature.melspectrogram(
        y=audio,
        sr=config.SAMPLE_RATE,
        n_mels=config.N_MELS,
        n_fft=config.N_FFT,
        hop_length=config.HOP_LENGTH,
        fmin=config.FMIN,
        fmax=config.FMAX
    )

    # Log compression
    mel = np.log1p(mel)

    # Resize to fixed dimensions
    n_mels, n_frames = mel.shape
    if n_frames != fixed_frames:
        zoom_factor = (1.0, fixed_frames / n_frames)
        mel = zoom(mel, zoom_factor, order=1)

    return mel.astype(np.float32)


def mel_distance(mel1: np.ndarray, mel2: np.ndarray, metric: str = 'euclidean') -> float:
    """
    Compute distance between two mel templates.

    Args:
        mel1, mel2: Mel-spectrogram templates
        metric: 'euclidean' or 'cosine'

    Returns:
        Distance value
    """
    mel1_flat = mel1.flatten()
    mel2_flat = mel2.flatten()

    if metric == 'euclidean':
        return np.sqrt(np.sum((mel1_flat - mel2_flat) ** 2))
    elif metric == 'cosine':
        norm1 = np.linalg.norm(mel1_flat)
        norm2 = np.linalg.norm(mel2_flat)
        if norm1 == 0 or norm2 == 0:
            return 1.0
        return 1.0 - np.dot(mel1_flat, mel2_flat) / (norm1 * norm2)
    else:
        raise ValueError(f"Unknown metric: {metric}")
