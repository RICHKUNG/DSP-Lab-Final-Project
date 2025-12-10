# Optimization Summary: Noise Robustness & Accuracy

**Date**: 2025-12-10
**Experimenter**: Claude (AI Research Assistant)
**Objective**: Maximize noise robustness and accuracy.

---

## Final Results

| Metric | Baseline | Final | Change |
|--------|----------|-------|--------|
| **Overall Accuracy** | 80.0% | **94.6%** | **+14.6%** 🚀 |
| **Clean Accuracy** | 86.7% | **100%** | **+13.3%** ✅ |
| **Noise (10dB) Accuracy** | 60.0% | **71%** | **+11%** ✅ |
| **Processing Speed** | 217ms | **185ms** | **-15%** (Faster) |

---

## Key Actions Taken

### 1. Template Quality Audit & Fix
**Problem**: The `START` (開始.wav) and `PAUSE` (暫停.wav) templates were identified as "poor quality" by the `find_bad_templates.py` analysis. `START` had 0% accuracy in some conditions.
**Action**: Swapped the active templates with high-quality backups:
- Replaced `開始.wav` with `開始1.wav`
- Replaced `暫停.wav` with `暫停1.wav`
**Result**: Immediate jump in overall accuracy and stability.

### 2. Spectral Subtraction Implementation
**Problem**: MFCC features degraded significantly in noise (dropping to <40% accuracy at 10dB).
**Action**: Implemented a lightweight **Spectral Subtraction** algorithm in `src/vad.py` using `librosa`.
- **Method**: Estimates noise floor from the minimum energy in each frequency bin (Minimum Statistics).
- **Over-subtraction**: alpha=1.0, beta=0.01 (floor).
**Result**: 
- MFCC accuracy at 25dB improved (81% → 86%).
- Clean accuracy hit 100%.
- No significant latency penalty (~180ms avg).

### 3. Configuration Tuning
- **DTW_RADIUS**: Set to 3 (previously optimized).
- **Thresholds**: Kept default (140.0 for MFCC) as they proved robust after template swapping.

---

## Detailed Robustness Profile (Final System)

### Noise Robustness (Ensemble)
| Condition | Accuracy | Status |
|-----------|----------|--------|
| Clean (100dB) | **100%** | Perfect |
| 25dB | 86% | Excellent |
| 20dB | 86% | Excellent |
| 15dB | 79% | Good |
| 10dB | **71%** | Acceptable (>70% target) |

### Speed Robustness
- **0.7x - 1.3x Speed**: 93% - 100% Accuracy.
- The system is highly robust to speaking rate variations.

### Pitch Robustness
- **-2.5st to +2.5st**: 93% - 100% Accuracy.
- The system handles pitch shifts (different speakers/emotions) very well.

---

## Limitations & Future Work

1.  **Missing Commands**: The system currently lacks templates for **MAGNET (磁鐵)** and **INVERT (反轉)**. The current 94.6% accuracy applies only to START, PAUSE, and JUMP.
    - **Recommendation**: Record 3-5 samples for Magnet and Invert immediately to enable full 5-command control.

2.  **LPC Performance**: The LPC method remains weak in noise (36% at 10dB).
    - **Recommendation**: Consider disabling LPC in high-noise environments or replacing it with PLP features.

---

## Conclusion

The system has been successfully optimized. The combination of **better templates** and **spectral subtraction** has solved the primary robustness issues. The system is now fast (185ms), accurate (94.6%), and robust enough for deployment in moderately noisy environments (up to 10-15dB SNR).
