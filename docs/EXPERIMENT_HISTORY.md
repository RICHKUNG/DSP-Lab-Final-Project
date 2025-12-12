# Bio-Voice Commander: Experiment History & Optimization Log

This document chronicles the development, optimization, and experimental validation of the Bio-Voice Commander audio system.

---

## 📅 Summary of Major Milestones

| Date | Phase | Key Achievement | Result |
|------|-------|-----------------|--------|
| 2025-12-09 | **Latency Optimization** | FastLPC + DTW Radius Reduction | Latency: 700ms → 217ms |
| 2025-12-10 | **Noise Robustness** | DTW Radius=3 Tuning | Clean Acc: 93%, 20dB Acc: 79% |
| 2025-12-10 | **Adaptive Ensemble** | SNR-weighted voting | 10dB Acc: 93%, 0dB Acc: 86% |
| 2025-12-12 | **Bug Fixes** | Adaptive VAD & Bounded Queue | Fixed "stop recognizing" bug |

---

## 1. Latency Optimization (2025-12-09)
**Source:** `OPTIMIZATION_SUMMARY.md`, `exp_fast_*.md`

### Objective
Reduce processing latency from ~700ms to <250ms while maintaining accuracy.

### Phase 1: FastLPCMatcher
- **Problem**: LPC DTW matching was too slow (480ms).
- **Solution**: Implemented `FastLPCMatcher` which resizes features to a fixed length (30 frames) and uses Euclidean distance instead of DTW.
- **Result**: Latency dropped to **330ms** (2.1x speedup). Accuracy maintained at 100% for test set.

### Phase 2: DTW Radius Optimization
- **Problem**: MFCC DTW became the bottleneck (330ms, 88% of time).
- **Solution**: Reduced `DTW_RADIUS`.
- **Experiments**:
    - Radius 5 (Baseline): 330ms
    - Radius 3: 275ms
    - **Radius 2: 217ms** (Chosen)
- **Result**: Latency reduced to **217ms**. Accuracy dropped slightly (80.3% → 80.0%), considered acceptable.

---

## 2. Noise Robustness Optimization (2025-12-10)
**Source:** `EXPERIMENT_NOISE_ROBUSTNESS.md`

### Objective
Improve accuracy in noisy environments (10-25dB SNR).

### Experiments
1.  **DTW Radius Tuning**: Tested radii 2, 3, 5, 7.
    -   **Winner**: **Radius 3**.
    -   Results: Best accuracy (85.7%) and fastest speed (186ms).
    -   Note: Radius 2 was slightly too aggressive; Radius 3 offered the best balance.
2.  **Threshold Adaptation**: Tested raising thresholds.
    -   Result: Degraded performance at 20dB. Kept `THRESHOLD_MFCC_DTW = 140.0`.

### Outcome
- **Overall Accuracy**: 80.0% → **85.7%**
- **Clean Accuracy**: 86.7% → **93%**
- **Processing Time**: 217ms → **186ms** (Optimization)

---

## 3. Adaptive Ensemble & Extreme Robustness (2025-12-10)
**Source:** `FINAL_EXPERIMENT_REPORT.md`, `EXTREME_TEST_REPORT_AFTER_FIX.md`

### Architecture
Introduced **Adaptive Ensemble** strategy:
- **Preprocessing**: **Spectral Subtraction** to estimate and subtract noise floor.
- **Dynamic Weighting**: Weights shift based on real-time SNR.
    - High SNR (>30dB): Trust MFCC.
    - Low SNR (<15dB): Trust Mel-Template.

### Extreme Test Results
| Condition | Description | Accuracy |
|-----------|-------------|----------|
| **Clean** | Library (100dB) | **100%** |
| **Noisy** | City Traffic (10dB) | **93%** |
| **Extreme** | Signal = Noise (0dB) | **86%** |
| **Limit** | Noise > Signal (-5dB) | **71%** |
| **Speed** | 0.5x - 1.0x | **100%** |
| **Pitch** | ±5 semitones | **86-100%** |

### Key Insight
The combination of **Spectral Subtraction** (cleaning the signal) and **Adaptive Weights** (trusting the most robust feature) allows the system to function even when noise exceeds the signal level (-5dB).

---

## 4. Bug Fixes & Stability (2025-12-12)
**Source:** `BUG_FIX_REPORT_SNR.md`

### Issue: Decreasing Sensitivity
Users reported the system stopped recognizing commands over time.

### Root Causes & Fixes
1.  **Infinite Lag**:
    -   *Cause*: Unbounded audio queue grew indefinitely if processing was slower than real-time.
    -   *Fix*: Implemented **bounded queue (maxlen=500)** with drop-oldest strategy.
2.  **VAD Threshold Drift**:
    -   *Cause*: Static threshold didn't adapt to changing environments.
    -   *Fix*: Implemented **Adaptive VAD** with Exponential Moving Average (EMA) background noise estimation.
3.  **SNR Underestimation**:
    -   *Cause*: SNR was calculated only on the *speech segment*, which often contains silence, leading to low SNR estimates.
    -   *Fix*: Injected background RMS from VAD into the recognizer for accurate SNR calculation.

---

## 5. RASTA-PLP Feasibility Study (2025-12-10)
**Source:** `exp_log.md`

### Objective
Test if RASTA-PLP features improve robustness at 10dB SNR.

### Results
- 20dB: 93% (Excellent)
- 10dB: 57% (Failed to beat Adaptive Ensemble's 93%)

### Decision
Code retained but not enabled by default, as Adaptive Ensemble proved superior.

---

## 6. Ensemble Strategy Evolution
**Source:** `exp_log.md`

- **Soft Voting (Adaptive)**: Weighted average of distances. Good general performance.
- **Hard Voting (Voting)**: Rank-based voting.
    -   *Result*: Fixed specific edge cases (Pitch -2.5st) but performed similarly elsewhere.
    -   *Decision*: Adaptive Ensemble (Soft Voting) remains the default for its smoother response, but Voting is available as an option.

---

## 7. Legacy Experiments (Early Insights)
**Source:** `insight.md`

- **Static Thresholds**: Failed (too many false positives).
- **Static Noise Templates**: Failed (environment mismatch).
- **Dynamic Calibration**: **Success**. Recording background noise at startup is critical.
- **"Human Garbage" Class**: **Success**. Explicitly training on "uhh", "umm" helps rejection.

---

*End of History Log*
