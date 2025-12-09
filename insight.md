# Bio-Voice Commander - Arena Test Insights Log

## Test Run 1: Initial Speed Arena
**Date:** 2025-12-09
**Test Suite:** Speed Only (0.7x - 1.3x)

### Executive Summary (Run 1)
Initial baseline test focusing on time-stretching robustness.

### Results (Run 1)
| Method       | 0.7x  | 0.8x  | 0.9x  | 1.0x  | 1.1x  | 1.2x  | 1.3x  |
|:-------------|:-----:|:-----:|:-----:|:-----:|:-----:|:-----:|:-----:|
| **mfcc_dtw** | 80%   | 80%   | 80%   | 80%   | 80%   | 80%   | 80%   |
| stats        | 53%   | 53%   | 53%   | 60%   | 53%   | 53%   | 53%   |
| mel          | 73%   | 73%   | 73%   | 73%   | 73%   | 73%   | 73%   |
| lpc          | 80%   | 80%   | 80%   | 80%   | 80%   | 80%   | 73%   |
| **ensemble** | **80%** | **80%** | **80%** | **80%** | **80%** | **80%** | **80%** |

---

## Test Run 2: Advanced Multi-Suite Arena
**Date:** 2025-12-09
**Test Suite:** Advanced Arena (Speed, Pitch, Noise, Volume)

### Executive Summary (Run 2)
An extensive "Leave-One-Out" cross-validation was performed on the command templates to evaluate the robustness of different recognition methods. The system was stressed with:
- **Speed:** 0.7x to 1.3x
- **Pitch:** -2.5 to +2.5 semitones
- **Noise:** 100dB (Clean) to 10dB SNR (Noisy)
- **Volume:** 0.3x to 3.0x

### Detailed Results (Run 2)

#### 1. Speed Robustness
*MFCC_DTW and Ensemble are perfectly stable across speed variations.*

| Method       | 0.7x  | 0.9x  | 1.0x  | 1.1x  | 1.3x  |
|:-------------|:-----:|:-----:|:-----:|:-----:|:-----:|
| **mfcc_dtw** | **80%** | **80%** | **80%** | **80%** | **80%** |
| stats        | 53%   | 53%   | 60%   | 53%   | 53%   |
| mel          | 73%   | 73%   | 73%   | 73%   | 73%   |
| lpc          | 80%   | 80%   | 80%   | 80%   | 73%   |
| **ensemble** | **80%** | **80%** | **80%** | **80%** | **80%** |

### 2. Pitch Robustness
*LPC struggles slightly with lower pitch (-2.5st). Ensemble benefits from diversity.*

| Method       | -2.5st| -1.0st| +0.0st| +1.0st| +2.5st|
|:-------------|:-----:|:-----:|:-----:|:-----:|:-----:|
| **mfcc_dtw** | 80%   | 87%   | 80%   | 80%   | 80%   |
| stats        | 53%   | 53%   | 60%   | 60%   | 53%   |
| mel          | 67%   | 73%   | 73%   | 73%   | 73%   |
| lpc          | 67%   | 67%   | 80%   | 80%   | 80%   |
| **ensemble** | **80%** | **87%** | **80%** | **80%** | **80%** |

### 3. Noise Robustness
*CRITICAL FINDING: LPC collapses in noise. Mel is the most stable individual method in high noise.*

| Method       | 100dB | 25dB  | 20dB  | 15dB  | 10dB  |
|:-------------|:-----:|:-----:|:-----:|:-----:|:-----:|
| mfcc_dtw     | 80%   | 73%   | 67%   | 60%   | 53%   |
| stats        | 60%   | 67%   | 53%   | 47%   | 33%   |
| **mel**      | 73%   | 73%   | 73%   | **73%** | **73%** |
| lpc          | 80%   | 47%   | 47%   | 27%   | 27%   |
| **ensemble** | **80%** | **87%** | **80%** | **73%** | **73%** |

### 4. Volume Robustness
*System is normalization-invariant.*

| Method       | 0.3x  | 0.6x  | 1.0x  | 1.5x  | 3.0x  |
|:-------------|:-----:|:-----:|:-----:|:-----:|:-----:|
| **mfcc_dtw** | 80%   | 80%   | 80%   | 80%   | 80%   |
| stats        | 60%   | 60%   | 60%   | 60%   | 60%   |
| mel          | 73%   | 73%   | 73%   | 73%   | 73%   |
| lpc          | 80%   | 80%   | 80%   | 80%   | 80%   |
| **ensemble** | **80%** | **80%** | **80%** | **80%** | **80%** |

## Key Insights & Recommendations

1.  **Ensemble Superiority:** The ensemble method (Weighted Voting) consistently outperformed or matched the best individual method in almost all scenarios. It achieved a robust **80% average accuracy**.

2.  **LPC vs. Noise:** LPC (Linear Predictive Coding) is highly sensitive to noise. Its accuracy dropped from 80% (Clean) to **27%** (10dB SNR).
    *   **Action:** Reduce LPC's voting weight dynamically if noise is detected, or generally lower its weight in the ensemble.

3.  **Mel Template Stability:** While `mel` rarely had the highest peak accuracy (73%), it was **completely unaffected by noise** down to 10dB SNR.
    *   **Action:** Increase `mel` weight in noisy conditions or use it as a "safety net" voter.

4.  **Stats Method Ineffectiveness:** The `stats` method (Zero Crossing Rate + RMS) consistently performed poorly (~53-60%) and behaved almost like a random guesser.
    *   **Action:** **DISABLE** the `stats` method to reduce computation and potential voting noise.

5.  **Data Quality:** Three base templates (`暫停.wav`, `跳.wav`, `開始.wav`) appear to be outliers compared to the numbered variations (`暫停1.wav`, etc.), consistently leading to misclassifications across all methods.

## Proposed Plan
1.  **Modify Ensemble Weights:**
    -   `stats`: 0.0 (Disable)
    -   `mfcc_dtw`: 4.0 (Keep high, best clean performance)
    -   `lpc`: 1.0 (Reduce from 1.5 due to noise fragility)
    -   `mel`: 2.5 (Increase from 2.0 for stability)
2.  **Clean Dataset:** Investigate or remove the outlier templates to push clean accuracy >90%.