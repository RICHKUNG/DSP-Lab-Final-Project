"""Dynamic Time Warping implementation."""

import numpy as np
from fastdtw import fastdtw
from scipy.spatial.distance import euclidean


def dtw_distance(seq1: np.ndarray, seq2: np.ndarray, radius: int = 5) -> float:
    """
    Compute DTW distance between two sequences.

    Args:
        seq1: First sequence (n_frames1, n_features)
        seq2: Second sequence (n_frames2, n_features)
        radius: Sakoe-Chiba band radius

    Returns:
        DTW distance
    """
    if len(seq1) == 0 or len(seq2) == 0:
        return float('inf')

    distance, _ = fastdtw(seq1, seq2, radius=radius, dist=euclidean)
    return distance


def dtw_distance_normalized(seq1: np.ndarray, seq2: np.ndarray, radius: int = 5) -> float:
    """
    Compute length-normalized DTW distance.

    Args:
        seq1, seq2: Feature sequences
        radius: Sakoe-Chiba band radius

    Returns:
        Normalized DTW distance
    """
    dist = dtw_distance(seq1, seq2, radius)
    path_length = len(seq1) + len(seq2)
    return dist / path_length if path_length > 0 else float('inf')
