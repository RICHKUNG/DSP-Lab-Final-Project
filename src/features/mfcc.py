"""MFCC feature extraction."""

import numpy as np
import librosa
from .. import config


def extract_mfcc(audio: np.ndarray, include_delta: bool = True) -> np.ndarray:
    """
    Extract MFCC features from audio.

    Args:
        audio: Audio samples (float32, normalized)
        include_delta: Whether to include delta and delta-delta

    Returns:
        MFCC features array (n_frames, n_features)
    """
    # Ensure float32
    if audio.dtype != np.float32:
        audio = audio.astype(np.float32)
        if np.max(np.abs(audio)) > 1.0:
            audio = audio / 32768.0

    # Extract MFCCs
    mfcc = librosa.feature.mfcc(
        y=audio,
        sr=config.SAMPLE_RATE,
        n_mfcc=config.N_MFCC,
        n_fft=config.N_FFT,
        hop_length=config.HOP_LENGTH
    )

    if include_delta:
        # Compute deltas
        delta = librosa.feature.delta(mfcc)
        delta2 = librosa.feature.delta(mfcc, order=2)
        # Stack features
        features = np.vstack([mfcc, delta, delta2])
    else:
        features = mfcc

    # Transpose to (n_frames, n_features)
    features = features.T

    # Cepstral mean normalization (per-utterance)
    features = features - np.mean(features, axis=0)

    return features


def extract_mfcc_delta(audio: np.ndarray) -> np.ndarray:
    """Extract MFCC with delta and delta-delta."""
    return extract_mfcc(audio, include_delta=True)
