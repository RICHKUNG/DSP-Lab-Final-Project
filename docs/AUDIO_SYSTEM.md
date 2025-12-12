# Bio-Voice Commander: Audio System Documentation

This document provides a comprehensive overview of the audio system, including architecture, method comparisons, troubleshooting, and accuracy analysis.

---

## 1. System Overview

### Pipeline
1.  **Input**: PyAudio captures raw audio (16kHz, Mono, Int16).
2.  **Buffering**: `AudioStream` uses a bounded queue (max 8s) to prevent latency buildup.
3.  **VAD (Voice Activity Detection)**:
    -   Uses adaptive energy thresholding.
    -   Estimates background noise using EMA (Exponential Moving Average).
    -   Triggers recognition only on valid speech segments.
4.  **Preprocessing**: Optional Spectral Subtraction for noise reduction.
5.  **Feature Extraction**:
    -   **MFCC**: 13 coefficients + Delta/Delta-Delta (Time-series).
    -   **Mel**: 128-band Mel Spectrogram (Fixed size image-like).
    -   **LPC**: Linear Predictive Coding coefficients (Resampled).
6.  **Recognition (Ensemble)**:
    -   Methods vote on the result.
    -   Weights can be static or dynamic (SNR-based).
7.  **Event Bus**: Publishes `VOICE_COMMAND` events to the game.

---

## 2. Recognition Methods Comparison

| Method | Algorithm | Pros | Cons | Best For |
|--------|-----------|------|------|----------|
| **MFCC** | DTW (Radius=3) | Highest Clean Accuracy (100%), Fast (~169ms) | Sensitive to Noise | Quiet Rooms, Low Power |
| **Mel** | Cosine Dist | Noise Robust, Stable across Pitch/Speed | Lower Clean Accuracy | High Noise, Variable Speakers |
| **LPC** | Euclidean | Detects channel anomalies | Fails in high noise (10dB) | Verification |
| **Ensemble** | Weighted Vote | Best of all worlds, High Robustness | Slower (~200ms) | General Use |

### Performance Data (10dB Noise)
- **MFCC Only**: 64% Accuracy
- **Ensemble**: 71% Accuracy
- **Adaptive Ensemble**: 93% Accuracy (with Spectral Subtraction)

---

## 3. Accuracy Analysis & Improvement

### Common Failure Modes
1.  **False Positives (Noise -> Command)**
    -   *Cause*: Sudden loud noises (claps, coughs).
    -   *Fix*: "Human Garbage" templates, Dynamic VAD calibration.
2.  **False Negatives (Command -> Ignored)**
    -   *Cause*: Thresholds too strict, VAD clipped start of word.
    -   *Fix*: Adaptive VAD, `VAD_PRE_ROLL` buffer.
3.  **Confusion (Start -> Pause)**
    -   *Cause*: Similar vowel structures, poor template quality.
    -   *Fix*: **Re-record templates**. This is often more effective than code changes.

### Optimizing Templates
-   Use `temp/find_bad_templates.py` to identify weak templates.
-   Record 8-10 samples per command.
-   Ensure recording environment matches deployment environment (e.g., distance to mic).

---

## 4. Troubleshooting Guide

### Error: `PyAudio -9999: Unanticipated host error`
**Root Cause**: Windows permission or driver issue.

**Solutions**:
1.  **Privacy Settings**: Settings > Privacy > Microphone. Enable "Allow desktop apps".
2.  **Exclusive Mode**: Sound Control Panel > Recording > Properties > Advanced. **Uncheck** "Allow applications to take exclusive control".
3.  **Device Sample Rate**: Ensure microphone supports 16000Hz.
4.  **Drivers**: Update audio drivers.

### Issue: "System stops hearing me after a while"
**Fixed in v2.0**: This was caused by an unbounded audio queue. Update to the latest version which includes the bounded queue fix.

### Issue: Low Sensitivity
-   Check if the background is noisy. The Adaptive VAD might have raised the threshold.
-   Speak closer to the microphone.
-   Run `python tests/test_calibration_mode.py` to re-calibrate.

---

## 5. Configuration Guide

**Recommended Settings (`src/config.py`)**:

**For Quiet/Office (Default)**:
```python
VOICE_METHOD = 'mfcc_dtw'
DTW_RADIUS = 3
THRESHOLD = 140.0
```

**For Noisy/Public Demo**:
```python
VOICE_METHOD = 'adaptive_ensemble'
DTW_RADIUS = 3
# Ensure initial calibration is done in the noisy environment!
```

**For Microcontrollers**:
```python
VOICE_METHOD = 'mfcc_dtw' # Lowest CPU usage
```
