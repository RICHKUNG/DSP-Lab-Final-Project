"""Feature extraction module - MFCC, Stats, Mel-template, LPC."""

import numpy as np
import librosa
from scipy.ndimage import zoom
from scipy.signal import lfilter
from scipy.fftpack import dct
from .. import config


# =============================================================================
# MFCC Features
# =============================================================================

def extract_mfcc(audio: np.ndarray, include_delta: bool = True, first_delta_only: bool = False) -> np.ndarray:
    """
    Extract MFCC features from audio.

    Args:
        audio: Audio samples (float32, normalized)
        include_delta: Whether to include delta and delta-delta
        first_delta_only: If True, returns ONLY the 1st order delta (13 dims). Overrides include_delta.

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

    if include_delta or first_delta_only:
        # librosa.delta requires the window width to be <= number of frames.
        # Short VAD segments can have very few frames, so clamp the width to
        # the largest odd value that fits to avoid "width ... cannot exceed data.shape" errors.
        n_frames = mfcc.shape[1]
        if n_frames == 0:
            return np.zeros((0, config.N_MFCC * 3 if not first_delta_only else config.N_MFCC), dtype=np.float32)
        
        delta_width = n_frames if n_frames % 2 == 1 else max(1, n_frames - 1)
        delta_width = min(9, delta_width)

        delta = librosa.feature.delta(mfcc, width=delta_width)
        
        if first_delta_only:
            features = delta
        else:
            delta2 = librosa.feature.delta(mfcc, order=2, width=delta_width)
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
# RASTA-PLP (Approximation) Features
# =============================================================================

def extract_rasta_plp(audio: np.ndarray, n_coeffs: int = 13) -> np.ndarray:
    """
    Extract RASTA-PLP features (Approximation).
    
    Implements RASTA filtering on Log Mel-Spectrogram followed by DCT.
    This provides noise robustness by filtering out slow-moving channel noise.

    Args:
        audio: Audio samples
        n_coeffs: Number of cepstral coefficients

    Returns:
        RASTA-PLP features (n_frames, n_coeffs)
    """
    if audio.dtype != np.float32:
        audio = audio.astype(np.float32)
        if np.max(np.abs(audio)) > 1.0:
            audio = audio / 32768.0

    # 1. Compute Log Mel-Spectrogram
    # We use power spectrum (power=2.0) as per PLP, but standard mel filterbank
    mel_spec = librosa.feature.melspectrogram(
        y=audio,
        sr=config.SAMPLE_RATE,
        n_mels=config.N_MELS,
        n_fft=config.N_FFT,
        hop_length=config.HOP_LENGTH,
        power=2.0
    )
    
    # Logarithm (with offset to avoid log(0))
    # PLP usually uses log(power + epsilon)
    log_mel = np.log(mel_spec + 1e-6)

    # 2. RASTA Filtering
    # Filter is applied along the time axis (axis=1) for each frequency band
    # H(z) = 0.1 * z^4 * (2 + z^-1 - z^-3 - 2z^-4) / (1 - 0.98z^-1)
    
    # Numerator: 0.2*z^0 + 0.1*z^-1 + 0*z^-2 - 0.1*z^-3 - 0.2*z^-4
    b = np.array([0.2, 0.1, 0.0, -0.1, -0.2])
    
    # Denominator: 1 - 0.98*z^-1
    a = np.array([1.0, -0.98])
    
    # Apply filter along time axis (columns)
    rasta_log_mel = lfilter(b, a, log_mel, axis=1)

    # 3. DCT (Discrete Cosine Transform) to get Cepstral Coefficients
    # Type 2 DCT, orthonormal
    # Axis=0 is frequency bands (n_mels), we want to decorrelate these
    cepstra = dct(rasta_log_mel, type=2, axis=0, norm='ortho')
    
    # Keep desired number of coefficients
    features = cepstra[:n_coeffs, :].T
    
    # 4. CMN (Cepstral Mean Normalization)
    features = features - np.mean(features, axis=0)
    
    return features


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
        
        # compute_lpc is not defined here, but librosa.lpc is used above.
        # Let's fix this minor bug while we are at it.
        # But wait, compute_lpc was likely an alias or imported.
        # In extract_lpc_features it uses librosa.lpc directly.
        # I will replace compute_lpc with librosa.lpc
        a = librosa.lpc(frame, order=order)

        poly = np.concatenate([[1], a]) # a already has 1 at start? 
        # librosa.lpc returns [1, a1, a2...], so poly is just a.
        # Wait, librosa.lpc returns the coefficients. 
        # If I use np.roots, I need the polynomial.
        roots = np.roots(a)

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


# =============================================================================
# Signal Quality Features
# =============================================================================

def estimate_snr(audio: np.ndarray, sample_rate: int = 16000,
                 frame_length_ms: int = 20) -> float:
    """
    估計音訊的訊噪比 (SNR)

    方法：
    1. 計算短時能量
    2. 使用百分位閾值區分噪音和訊號
    3. SNR = 10 * log10(訊號能量 / 噪音能量)

    Args:
        audio: 音訊樣本 (int16 或 float32)
        sample_rate: 採樣率
        frame_length_ms: 幀長度 (毫秒)

    Returns:
        估計的 SNR (dB)，乾淨訊號返回 100.0
    """
    if len(audio) == 0:
        return 0.0

    # 轉換為 float32
    if audio.dtype == np.int16:
        audio = audio.astype(np.float32) / 32768.0
    else:
        audio = audio.astype(np.float32)

    # 幀參數
    frame_length = int(sample_rate * frame_length_ms / 1000)
    hop_length = frame_length // 2

    if len(audio) < frame_length:
        return 0.0

    # 計算短時能量
    energy = []
    for i in range(0, len(audio) - frame_length, hop_length):
        frame = audio[i:i+frame_length]
        energy.append(np.sum(frame ** 2))

    energy = np.array(energy)

    if len(energy) == 0:
        return 0.0

    # 使用百分位區分噪音和訊號 (底部 40% 為噪音)
    threshold = np.percentile(energy, 40)

    noise_frames = energy[energy <= threshold]
    signal_frames = energy[energy > threshold]

    noise_energy = np.mean(noise_frames) if len(noise_frames) > 0 else 1e-9
    signal_energy = np.mean(signal_frames) if len(signal_frames) > 0 else 0.0

    if noise_energy < 1e-9:
        return 100.0

    if signal_energy <= noise_energy:
        return 0.0

    snr_db = 10 * np.log10(signal_energy / noise_energy)

    return float(snr_db)
