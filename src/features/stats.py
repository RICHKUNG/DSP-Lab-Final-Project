"""Segmental statistics feature extraction."""

import numpy as np
from .mfcc import extract_mfcc
from .. import config


def extract_stats_features(audio: np.ndarray, n_segments: int = None) -> np.ndarray:
    """
    Extract segmental statistics features.

    Divides MFCC sequence into segments and computes mean/std for each.

    Args:
        audio: Audio samples
        n_segments: Number of segments (default from config)

    Returns:
        Fixed-length feature vector
    """
    if n_segments is None:
        n_segments = config.STATS_SEGMENTS

    # Extract base MFCC (without delta for simplicity)
    mfcc = extract_mfcc(audio, include_delta=False)  # (n_frames, n_mfcc)

    n_frames = mfcc.shape[0]
    n_features = mfcc.shape[1]

    if n_frames < n_segments:
        # Pad with zeros if too short
        pad_frames = n_segments - n_frames
        mfcc = np.vstack([mfcc, np.zeros((pad_frames, n_features))])
        n_frames = n_segments

    # Split into segments
    segment_size = n_frames // n_segments
    features = []

    for i in range(n_segments):
        start = i * segment_size
        end = start + segment_size if i < n_segments - 1 else n_frames
        segment = mfcc[start:end]

        # Compute statistics
        seg_mean = np.mean(segment, axis=0)
        seg_std = np.std(segment, axis=0)

        features.extend(seg_mean)
        features.extend(seg_std)

    return np.array(features, dtype=np.float32)
