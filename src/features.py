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
    Also includes Zero Crossing Rate (ZCR) stats.

    Args:
        audio: Audio samples
        n_segments: Number of segments (default from config)

    Returns:
        Fixed-length feature vector
    """
    if n_segments is None:
        n_segments = config.STATS_SEGMENTS

    # 1. Extract MFCCs with deltas
    mfcc = extract_mfcc(audio, include_delta=True)
    n_frames = mfcc.shape[0]
    n_mfcc_feats = mfcc.shape[1]

    # 2. Extract ZCR
    zcr = librosa.feature.zero_crossing_rate(
        y=audio, 
        frame_length=config.N_FFT, 
        hop_length=config.HOP_LENGTH
    ).T # (n_frames, 1)
    
    # Ensure lengths match (librosa padding might cause slight mismatch)
    min_len = min(len(mfcc), len(zcr))
    mfcc = mfcc[:min_len]
    zcr = zcr[:min_len]
    n_frames = min_len

    # Concatenate features
    combined_features = np.hstack([mfcc, zcr])
    n_total_feats = combined_features.shape[1]

    if n_frames < n_segments:
        pad_frames = n_segments - n_frames
        combined_features = np.vstack([combined_features, np.zeros((pad_frames, n_total_feats))])
        n_frames = n_segments

    segment_size = n_frames // n_segments
    features = []

    for i in range(n_segments):
        start = i * segment_size
        end = start + segment_size if i < n_segments - 1 else n_frames
        segment = combined_features[start:end]
        
        # Compute mean and std for this segment
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

def lpc_to_lpcc(a: np.ndarray, order: int, cep_order: int) -> np.ndarray:
    """
    Convert LPC coefficients to LPC Cepstral Coefficients (LPCC).
    
    Args:
        a: LPC coefficients [1, a1, a2, ...]
        order: LPC order
        cep_order: Output cepstral order
    """
    c = np.zeros(cep_order)
    # a array includes a0=1 at index 0
    
    for n in range(1, cep_order + 1):
        sum_term = 0.0
        # summation limit: min(n-1, order)
        # k goes from 1 to n-1
        # Formula: c[n] = -a[n] - (1/n) * sum(k=1..n-1) [ (n-k) * a[k] * c[n-k] ]
        
        for k in range(1, n):
            if k <= order:
                sum_term += (n - k) * a[k] * c[n - k - 1]
        
        current_a = a[n] if n <= order else 0.0
        c[n-1] = -current_a - (1.0 / n) * sum_term
    
    # Clip to prevent numerical explosion
    c = np.clip(c, -50.0, 50.0)
        
    return c


def extract_lpc_features(audio: np.ndarray, order: int = None) -> np.ndarray:
    """
    Extract LPC-based features from audio using librosa.lpc.

    Args:
        audio: Audio samples
        order: LPC order

    Returns:
        Feature sequence (n_frames, cep_order)
    """
    if order is None:
        order = config.LPC_ORDER

    if audio.dtype != np.float32:
        audio = audio.astype(np.float32)
        if np.max(np.abs(audio)) > 1.0:
            audio = audio / 32768.0

    # 1. Pre-emphasis
    audio = librosa.effects.preemphasis(audio)

    # 2. Frame parameters
    frame_length = int(config.LPC_FRAME_MS * config.SAMPLE_RATE / 1000)
    hop_length = int(config.LPC_HOP_MS * config.SAMPLE_RATE / 1000)

    # 3. Framing with Librosa (efficient stride tricks)
    # Output is (frame_length, n_frames)
    frames = librosa.util.frame(audio, frame_length=frame_length, hop_length=hop_length)
    
    # 4. Windowing
    window = np.hamming(frame_length)
    frames = frames * window[:, np.newaxis]
    
    # 5. Compute LPC and LPCC for each frame
    # librosa.lpc only accepts 1D input in older versions, 
    # but let's iterate. The number of frames is ~100-200, so a simple loop is fine
    # if the inner LPC calc is fast (which librosa.lpc is).
    
    n_frames = frames.shape[1]
    lpcc_frames = np.zeros((n_frames, order), dtype=np.float32)
    
    for i in range(n_frames):
        frame = frames[:, i]
        # librosa.lpc returns [1, a1, a2, ... ap]
        a = librosa.lpc(frame, order=order)
        lpcc_frames[i] = lpc_to_lpcc(a, order, order)

    return lpcc_frames


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
