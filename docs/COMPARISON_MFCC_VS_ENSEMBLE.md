# Performance Comparison: MFCC vs Ensemble

**Date**: 2025-12-10
**Experimenter**: Claude (AI Research Assistant)
**Objective**: Quantify the trade-offs between "Lightweight" (MFCC Only) and "Robust" (Ensemble) modes.

---

## Executive Summary

| Feature | MFCC Only (Lightweight) | Ensemble (Robust) | Verdict |
| :--- | :--- | :--- | :--- |
| **Speed (Avg Latency)** | **~169 ms** | **~200 ms** | MFCC is **~15-20% faster** |
| **Clean Accuracy** | 100% | 100% | Tie |
| **Noise Accuracy (10dB)** | 64% | **71%** | **Ensemble is +7% better** |
| **Compute Cost** | Low (MFCC + DTW) | High (MFCC + Mel + LPC + Voting) | MFCC wins for low-power |

**Conclusion**: 
- Use **MFCC Only** for low-power devices or quiet environments (Office/Home).
- Use **Ensemble** for noisy environments (Outdoors/Industrial) or where reliability is critical.

---

## 1. Speed Analysis (Latency)

Measured average processing time per command (including feature extraction + matching):

| Condition | MFCC Only | Ensemble | Difference |
| :--- | :--- | :--- | :--- |
| **Clean Audio** | 169ms | 197ms | +28ms |
| **Noisy (10dB)** | 168ms | 201ms | +33ms |
| **Fast Speech (1.3x)** | 150ms | 176ms | +26ms |
| **Slow Speech (0.7x)** | 217ms | 266ms | +49ms |

*Note: Ensemble adds constant overhead due to Mel Spectrogram and LPC feature extraction.*

---

## 2. Accuracy Analysis

### Noise Robustness (Critical Differentiator)

| SNR Level | MFCC Only | Ensemble | Notes |
| :--- | :--- | :--- | :--- |
| **100dB (Clean)** | **100%** | **100%** | Both perfect in quiet |
| **25dB** | 86% | 86% | Tie |
| **20dB** | 86% | 86% | Tie |
| **15dB** | 79% | 79% | Tie |
| **10dB (Noisy)** | 64% | **71%** | **Ensemble Prevents Failure** |

*Insight*: The Ensemble's use of **Mel Templates** (which use Cosine Distance) helps reject false positives and stabilize detection when MFCC features become distorted by noise.

### Pitch & Speed Robustness

- **Pitch**: Both methods handle pitch shifts (-2.5st to +2.5st) equally well (93-100%).
- **Speed**: Both methods degrade gracefully at extreme speeds, but Ensemble maintains slight edge in stability metrics (though raw accuracy is similar).

---

## 3. Recommendation Guide

### Scenario A: Embedded Device / Microcontroller (e.g., Raspberry Pi Zero)
*   **Recommended Mode**: `MFCC Only`
*   **Reason**: Saves ~30ms per inference, lower CPU usage. Accuracy is sufficient for typical use.

### Scenario B: Robot / Industrial Controller (e.g., PC / Jetson)
*   **Recommended Mode**: `Ensemble`
*   **Reason**: The 30ms latency cost is negligible on powerful hardware. The **+7% accuracy in noise** prevents frustrating "missed command" errors in loud environments.

---

## 4. Technical Details

**MFCC Configuration**:
- 13 Coefficients
- DTW Radius: 3
- Spectral Subtraction: Enabled

**Ensemble Configuration**:
- Voting Weights: MFCC (4.0), Mel (2.5), LPC (1.0)
- Veto Logic: Mel template match required for high confidence.

---

*Data Source: `record/arena_mfcc_20251210_151537.json` and `record/arena_ensemble_20251210_151642.json`*
