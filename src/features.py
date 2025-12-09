"""Feature extraction module - MFCC, Stats, Mel-template, LPC."""

import numpy as np
import librosa
from scipy.ndimage import zoom
from . import config


# =============================================================================
# MFCC Features
# =============================================================================

def extract_mfcc(audio: np.ndarray, include_delta: bool = True) -> np.ndarray:
    """
    Extract MFCC features from audio.

    Args:
        audio: Audio samples (float32, normalized)
        include_delta: Whether to include delta and delta-delta

    Returns:
        MFCC features array (n_frames, n_features)
    """
    if audio.dtype != np.float32:
        audio = audio.astype(np.float32)
        if np.max(np.abs(audio)) > 1.0:
            audio = audio / 32768.0

    mfcc = librosa.feature.mfcc(
        y=audio,
        sr=config.SAMPLE_RATE,
        n_mfcc=config.N_MFCC,
        n_fft=config.N_FFT,
        hop_length=config.HOP_LENGTH
    )

    if include_delta:
        delta = librosa.feature.delta(mfcc)
        delta2 = librosa.feature.delta(mfcc, order=2)
        features = np.vstack([mfcc, delta, delta2])
    else:
        features = mfcc

    features = features.T
    features = features - np.mean(features, axis=0)
    return features


def extract_mfcc_delta(audio: np.ndarray) -> np.ndarray:
    """Extract MFCC with delta and delta-delta."""
    return extract_mfcc(audio, include_delta=True)


# =============================================================================
# Segmental Statistics Features
# =============================================================================

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

    mfcc = extract_mfcc(audio, include_delta=False)
    n_frames = mfcc.shape[0]
    n_features = mfcc.shape[1]

    if n_frames < n_segments:
        pad_frames = n_segments - n_frames
        mfcc = np.vstack([mfcc, np.zeros((pad_frames, n_features))])
        n_frames = n_segments

    segment_size = n_frames // n_segments
    features = []

    for i in range(n_segments):
        start = i * segment_size
        end = start + segment_size if i < n_segments - 1 else n_frames
        segment = mfcc[start:end]
        seg_mean = np.mean(segment, axis=0)
        seg_std = np.std(segment, axis=0)
        features.extend(seg_mean)
        features.extend(seg_std)

    return np.array(features, dtype=np.float32)


# =============================================================================
# Mel-spectrogram Template Features
# =============================================================================

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

    if audio.dtype != np.float32:
        audio = audio.astype(np.float32)
        if np.max(np.abs(audio)) > 1.0:
            audio = audio / 32768.0

    mel = librosa.feature.melspectrogram(
        y=audio,
        sr=config.SAMPLE_RATE,
        n_mels=config.N_MELS,
        n_fft=config.N_FFT,
        hop_length=config.HOP_LENGTH,
        fmin=config.FMIN,
        fmax=config.FMAX
    )

    mel = np.log1p(mel)

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


# =============================================================================
# LPC and Formant Features
# =============================================================================

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
        acc = r[i]
        for j in range(1, i):
            acc += a[j] * r[i - j]

        if e[i-1] == 0:
            k = 0
        else:
            k = -acc / e[i-1]

        a_new = a.copy()
        a_new[i] = k
        for j in range(1, i):
            a_new[j] = a[j] + k * a[i - j]

        a = a_new
        e[i] = (1 - k * k) * e[i-1]

    return a[1:]


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

    windowed = frame * np.hamming(len(frame))
    r = _autocorr(windowed, order)

    if r[0] == 0:
        return np.zeros(order)

    r = r / r[0]
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

    if audio.dtype != np.float32:
        audio = audio.astype(np.float32)
        if np.max(np.abs(audio)) > 1.0:
            audio = audio / 32768.0

    frame_length = int(config.LPC_FRAME_MS * config.SAMPLE_RATE / 1000)
    hop_length = int(config.LPC_HOP_MS * config.SAMPLE_RATE / 1000)

    lpc_frames = []
    for start in range(0, len(audio) - frame_length, hop_length):
        frame = audio[start:start + frame_length]
        lpc = compute_lpc(frame, order)
        lpc_frames.append(lpc)

    if len(lpc_frames) == 0:
        return np.zeros(2 * order, dtype=np.float32)

    lpc_frames = np.array(lpc_frames)
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

    if audio.dtype != np.float32:
        audio = audio.astype(np.float32)
        if np.max(np.abs(audio)) > 1.0:
            audio = audio / 32768.0

    frame_length = int(config.LPC_FRAME_MS * config.SAMPLE_RATE / 1000)
    hop_length = int(config.LPC_HOP_MS * config.SAMPLE_RATE / 1000)

    all_formants = []

    for start in range(0, len(audio) - frame_length, hop_length):
        frame = audio[start:start + frame_length]
        lpc = compute_lpc(frame, order)

        poly = np.concatenate([[1], lpc])
        roots = np.roots(poly)

        formants = []
        for root in roots:
            if np.imag(root) > 0:
                freq = np.abs(np.arctan2(np.imag(root), np.real(root))) * config.SAMPLE_RATE / (2 * np.pi)
                if 90 < freq < 5000:
                    formants.append(freq)

        formants = sorted(formants)[:n_formants]

        while len(formants) < n_formants:
            formants.append(0)

        all_formants.append(formants)

    if len(all_formants) == 0:
        return np.zeros(2 * n_formants, dtype=np.float32)

    all_formants = np.array(all_formants)
    formant_median = np.median(all_formants, axis=0)
    formant_std = np.std(all_formants, axis=0)

    return np.concatenate([formant_median, formant_std]).astype(np.float32)
