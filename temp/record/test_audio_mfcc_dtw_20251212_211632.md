# Voice Recognition QA Test Report (VoiceController)

**Generated:** 2025-12-12 21:16:32
**Method:** mfcc_dtw

## Overall Summary

- **Total samples:** 40
- **Noise samples (ground truth):** 6
- **Valid command samples:** 34

## Results

- **Command Accuracy:** 85.3% (29/34)
- **Noise Rejection Accuracy:** 0.0% (0/6)
- **False Positives (NOISE detected as command):** 6
- **False Negatives (Command detected as NONE/NOISE):** 0
- **Misclassifications:** 5

## Confusion Matrix

| Actual \ Predicted | START | JUMP | FLIP | PAUSE | NONE | NOISE |
|--------------------|------:|------:|------:|------:|------:|------:|
| **START** | 8 | 0 | 0 | 0 | 0 | 0 |
| **JUMP** | 0 | 7 | 0 | 0 | 0 | 0 |
| **FLIP** | 1 | 0 | 8 | 0 | 0 | 0 |
| **PAUSE** | 2 | 2 | 0 | 6 | 0 | 0 |
| **NOISE** | 2 | 4 | 0 | 0 | 0 | 0 |

## Timing Statistics

- **Processing Latency (Avg):** 203.3ms
- **Processing Latency (Min):** 42.7ms
- **Processing Latency (Max):** 501.1ms

- **SNR (Avg):** 39.3dB
- **SNR (Min):** 4.5dB
- **SNR (Max):** 46.5dB

## Detailed Test Log

| # | Ground Truth | Predicted | Confidence | Latency (ms) | SNR (dB) | Result |
|--:|:-------------|:----------|----------:|-------------:|---------:|:------:|
| 1 | START | START | 0.68 | 84.1 | 43.7 | ✓ |
| 2 | NOISE | JUMP | 0.32 | 42.7 | 6.6 | ✗ |
| 3 | JUMP | JUMP | 0.70 | 106.1 | 43.4 | ✓ |
| 4 | PAUSE | PAUSE | 0.73 | 258.0 | 41.9 | ✓ |
| 5 | FLIP | FLIP | 0.66 | 104.8 | 45.2 | ✓ |
| 6 | START | START | 0.74 | 131.2 | 45.0 | ✓ |
| 7 | JUMP | JUMP | 0.70 | 113.7 | 43.9 | ✓ |
| 8 | FLIP | FLIP | 0.71 | 102.9 | 45.8 | ✓ |
| 9 | PAUSE | JUMP | 0.69 | 258.7 | 42.1 | ✗ |
| 10 | START | START | 0.80 | 104.9 | 44.4 | ✓ |
| 11 | NOISE | START | 0.60 | 67.5 | 9.3 | ✗ |
| 12 | JUMP | JUMP | 0.71 | 133.2 | 43.8 | ✓ |
| 13 | FLIP | FLIP | 0.69 | 110.3 | 46.1 | ✓ |
| 14 | NOISE | JUMP | 0.51 | 57.3 | 4.5 | ✗ |
| 15 | PAUSE | PAUSE | 0.68 | 267.7 | 43.9 | ✓ |
| 16 | START | START | 0.69 | 284.9 | 43.2 | ✓ |
| 17 | JUMP | JUMP | 0.75 | 128.0 | 43.7 | ✓ |
| 18 | FLIP | FLIP | 0.71 | 148.7 | 44.9 | ✓ |
| 19 | PAUSE | PAUSE | 0.71 | 351.7 | 43.1 | ✓ |
| 20 | NOISE | JUMP | 0.12 | 65.7 | 13.3 | ✗ |
| 21 | START | START | 0.73 | 106.1 | 43.7 | ✓ |
| 22 | JUMP | JUMP | 0.73 | 329.6 | 44.0 | ✓ |
| 23 | FLIP | FLIP | 0.68 | 118.8 | 46.5 | ✓ |
| 24 | PAUSE | JUMP | 0.73 | 308.7 | 42.0 | ✗ |
| 25 | PAUSE | PAUSE | 0.75 | 378.9 | 42.4 | ✓ |
| 26 | START | START | 0.71 | 154.6 | 44.2 | ✓ |
| 27 | NOISE | START | 0.69 | 82.6 | 11.7 | ✗ |
| 28 | JUMP | JUMP | 0.74 | 131.3 | 43.7 | ✓ |
| 29 | FLIP | FLIP | 0.64 | 111.3 | 45.7 | ✓ |
| 30 | NOISE | JUMP | 0.74 | 101.5 | 27.2 | ✗ |
| 31 | PAUSE | PAUSE | 0.70 | 395.7 | 44.4 | ✓ |
| 32 | START | START | 0.67 | 378.7 | 43.2 | ✓ |
| 33 | JUMP | JUMP | 0.75 | 409.4 | 43.2 | ✓ |
| 34 | PAUSE | PAUSE | 0.77 | 325.3 | 44.3 | ✓ |
| 35 | FLIP | START | 0.70 | 152.9 | 46.5 | ✗ |
| 36 | FLIP | FLIP | 0.69 | 420.4 | 45.1 | ✓ |
| 37 | PAUSE | START | 0.66 | 501.1 | 43.0 | ✗ |
| 38 | PAUSE | START | 0.76 | 493.3 | 44.0 | ✗ |
| 39 | START | START | 0.78 | 171.7 | 43.7 | ✓ |
| 40 | FLIP | FLIP | 0.70 | 138.1 | 45.0 | ✓ |

---
*✓ = Correct, ✗ = Incorrect*
*NOISE samples: NONE or NOISE prediction is considered correct*
