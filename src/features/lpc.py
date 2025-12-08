"""LPC and Formant feature extraction."""

import numpy as np
from scipy.signal import lfilter
from .. import config


def _autocorr(x: np.ndarray, order: int) -> np.ndarray:
    """Compute autocorrelation coefficients."""
    n = len(x)
    r = np.zeros(order + 1)
    for i in range(order + 1):
        r[i] = np.sum(x[:n-i] * x[i:])
    return r


def _levinson_durbin(r: np.ndarray, order: int) -> np.ndarray:
    """Levinson-Durbin algorithm for LPC coefficients."""
    a = np.zeros(order + 1)
    e = np.zeros(order + 1)

    a[0] = 1.0
    e[0] = r[0]

    for i in range(1, order + 1):
        # Compute reflection coefficient
        acc = r[i]
        for j in range(1, i):
            acc += a[j] * r[i - j]

        if e[i-1] == 0:
            k = 0
        else:
            k = -acc / e[i-1]

        # Update coefficients
        a_new = a.copy()
        a_new[i] = k
        for j in range(1, i):
            a_new[j] = a[j] + k * a[i - j]

        a = a_new
        e[i] = (1 - k * k) * e[i-1]

    return a[1:]  # Return LPC coefficients (excluding a[0]=1)


def compute_lpc(frame: np.ndarray, order: int = None) -> np.ndarray:
    """
    Compute LPC coefficients for a single frame.

    Args:
        frame: Audio frame (windowed)
        order: LPC order (default from config)

    Returns:
        LPC coefficients array
    """
    if order is None:
        order = config.LPC_ORDER

    # Apply Hamming window
    windowed = frame * np.hamming(len(frame))

    # Compute autocorrelation
    r = _autocorr(windowed, order)

    # Handle zero energy
    if r[0] == 0:
        return np.zeros(order)

    # Normalize
    r = r / r[0]

    # Levinson-Durbin
    lpc = _levinson_durbin(r, order)

    return lpc


def extract_lpc_features(audio: np.ndarray, order: int = None) -> np.ndarray:
    """
    Extract LPC-based features from audio.

    Computes mean and std of LPC coefficients across all frames.

    Args:
        audio: Audio samples
        order: LPC order

    Returns:
        Feature vector (2 * order dimensions)
    """
    if order is None:
        order = config.LPC_ORDER

    # Ensure float32
    if audio.dtype != np.float32:
        audio = audio.astype(np.float32)
        if np.max(np.abs(audio)) > 1.0:
            audio = audio / 32768.0

    # Frame parameters
    frame_length = int(config.LPC_FRAME_MS * config.SAMPLE_RATE / 1000)
    hop_length = int(config.LPC_HOP_MS * config.SAMPLE_RATE / 1000)

    # Extract LPC for each frame
    lpc_frames = []
    for start in range(0, len(audio) - frame_length, hop_length):
        frame = audio[start:start + frame_length]
        lpc = compute_lpc(frame, order)
        lpc_frames.append(lpc)

    if len(lpc_frames) == 0:
        return np.zeros(2 * order, dtype=np.float32)

    lpc_frames = np.array(lpc_frames)

    # Compute statistics
    lpc_mean = np.mean(lpc_frames, axis=0)
    lpc_std = np.std(lpc_frames, axis=0)

    return np.concatenate([lpc_mean, lpc_std]).astype(np.float32)


def extract_formants(audio: np.ndarray, n_formants: int = 3, order: int = None) -> np.ndarray:
    """
    Extract formant frequencies from LPC analysis.

    Args:
        audio: Audio samples
        n_formants: Number of formants to extract
        order: LPC order

    Returns:
        Formant frequencies array (n_formants * 2 for mean/std)
    """
    if order is None:
        order = config.LPC_ORDER

    # Ensure float32
    if audio.dtype != np.float32:
        audio = audio.astype(np.float32)
        if np.max(np.abs(audio)) > 1.0:
            audio = audio / 32768.0

    # Frame parameters
    frame_length = int(config.LPC_FRAME_MS * config.SAMPLE_RATE / 1000)
    hop_length = int(config.LPC_HOP_MS * config.SAMPLE_RATE / 1000)

    all_formants = []

    for start in range(0, len(audio) - frame_length, hop_length):
        frame = audio[start:start + frame_length]
        lpc = compute_lpc(frame, order)

        # Find roots of LPC polynomial
        # A(z) = 1 + a1*z^-1 + a2*z^-2 + ...
        poly = np.concatenate([[1], lpc])
        roots = np.roots(poly)

        # Get formant frequencies from complex conjugate roots
        formants = []
        for root in roots:
            if np.imag(root) > 0:  # Only positive imaginary part
                freq = np.abs(np.arctan2(np.imag(root), np.real(root))) * config.SAMPLE_RATE / (2 * np.pi)
                if 90 < freq < 5000:  # Reasonable formant range
                    formants.append(freq)

        formants = sorted(formants)[:n_formants]

        # Pad if not enough formants
        while len(formants) < n_formants:
            formants.append(0)

        all_formants.append(formants)

    if len(all_formants) == 0:
        return np.zeros(2 * n_formants, dtype=np.float32)

    all_formants = np.array(all_formants)

    # Compute statistics (median is more robust for formants)
    formant_median = np.median(all_formants, axis=0)
    formant_std = np.std(all_formants, axis=0)

    return np.concatenate([formant_median, formant_std]).astype(np.float32)
