# Bug Fix Report: SNR Underestimation
**Date:** 2025-12-12
**Status:** Fixed & Verified

---

## 🐛 Issue Description
**Symptom:** Recent audio recognition performance dropped significantly, especially in clean environments.
**Root Cause:**
The `estimate_snr` function in `src/audio/features.py` calculates SNR based on the assumption that the lowest 40% of energy in a clip is noise.
However, the VAD (Voice Activity Detector) crops audio segments to contain *only* speech.
Result: The function interpreted parts of the speech signal as noise, leading to an estimated SNR of ~0dB even for crystal clear audio.
**Consequence:**
The `adaptive_ensemble` method incorrectly switched to "Noisy Mode" weights (favoring Mel-spectrogram over MFCC) for all inputs, degrading accuracy in clean conditions where MFCC is superior.

## 🛠️ Fix Implementation

### 1. `src/audio/recognizers.py`
- Updated `MultiMethodMatcher.recognize` and `recognize_voting` to accept an optional `known_snr` parameter.
- If `known_snr` is provided, it bypasses the internal `estimate_snr` call.

### 2. `src/audio/controller.py`
- Updated `VoiceController._recognition_loop` to calculate SNR using the VAD's continuous background noise tracker (`_vad.background_rms`).
- `SNR = 20 * log10(Signal_RMS / Background_RMS)`
- This value is passed to the recognizer, ensuring accurate mode selection.

## ✅ Verification
- **Unit Test:** `tests/verify_fix.py` confirmed `recognize` accepts and uses the injected SNR.
- **Stress Test:** `tests/test_arena_extreme.py` confirmed:
    - **100% Accuracy** in Clean/Moderate noise (20dB+).
    - **>90% Accuracy** in High noise (0-10dB).
    - Robustness maintained across Speed (0.5x-1.7x) and Pitch (-5 to +5 semitones).

## 📝 Conclusion
The system's adaptive logic is now functioning correctly. It dynamically switches between MFCC-dominant (Clean) and Mel-dominant (Noisy) weights based on the actual environmental noise level.
