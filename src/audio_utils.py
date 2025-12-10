import numpy as np

def estimate_snr(audio: np.ndarray, sample_rate: int = 16000,
                 frame_length_ms: int = 20) -> float:
    """
    Estimate the Signal-to-Noise Ratio (SNR) of an audio signal.

    Method:
    1. Calculate Short-Time Energy.
    2. Use a percentile threshold to separate "noise" (silence/background) from "signal" (speech).
    3. SNR = 10 * log10(Signal Energy / Noise Energy).

    Args:
        audio: Audio samples (int16 or float32).
        sample_rate: Sampling rate in Hz.
        frame_length_ms: Frame length in milliseconds for energy calculation.

    Returns:
        Estimated SNR in dB. Returns 100.0 if practically clean.
    """
    if len(audio) == 0:
        return 0.0

    # Convert to float32 if int16
    if audio.dtype == np.int16:
        audio = audio.astype(np.float32) / 32768.0
    else:
        audio = audio.astype(np.float32)

    # Frame parameters
    frame_length = int(sample_rate * frame_length_ms / 1000)
    hop_length = frame_length // 2

    if len(audio) < frame_length:
        return 0.0

    # Compute Short-Time Energy
    # Simple squared sum windowing
    energy = []
    for i in range(0, len(audio) - frame_length, hop_length):
        frame = audio[i:i+frame_length]
        energy.append(np.sum(frame ** 2))

    energy = np.array(energy)
    
    if len(energy) == 0:
        return 0.0

    # Determine threshold to separate noise from signal
    # Assumption: The bottom 40% of energy frames are noise/background
    # This works reasonable well for command words which have clear silence gaps
    threshold = np.percentile(energy, 40)

    # Separate energies
    noise_frames = energy[energy <= threshold]
    signal_frames = energy[energy > threshold]

    # Calculate mean energy
    noise_energy = np.mean(noise_frames) if len(noise_frames) > 0 else 1e-9
    signal_energy = np.mean(signal_frames) if len(signal_frames) > 0 else 0.0

    # Avoid division by zero
    if noise_energy < 1e-9:
        return 100.0 # Effectively infinite SNR

    if signal_energy <= noise_energy:
        return 0.0 # Signal is buried in noise

    # SNR formula
    snr_db = 10 * np.log10(signal_energy / noise_energy)
    
    return float(snr_db)
