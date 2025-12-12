# Voice Recognition QA Test Report (VoiceController)

**Generated:** 2025-12-12 21:09:03
**Method:** mfcc_dtw

## Overall Summary

- **Total samples:** 8
- **Noise samples (ground truth):** 0
- **Valid command samples:** 8

## Results

- **Command Accuracy:** 87.5% (7/8)
- **Noise Rejection Accuracy:** 0.0% (0/0)
- **False Positives (NOISE detected as command):** 0
- **False Negatives (Command detected as NONE/NOISE):** 0
- **Misclassifications:** 1

## Confusion Matrix

| Actual \ Predicted | START | JUMP | FLIP | PAUSE | NONE | NOISE |
|--------------------|------:|------:|------:|------:|------:|------:|
| **START** | 3 | 0 | 0 | 0 | 0 | 0 |
| **JUMP** | 0 | 3 | 0 | 0 | 0 | 0 |
| **FLIP** | 1 | 0 | 1 | 0 | 0 | 0 |
| **PAUSE** | 0 | 0 | 0 | 0 | 0 | 0 |
| **NOISE** | 0 | 0 | 0 | 0 | 0 | 0 |

## Timing Statistics

- **Processing Latency (Avg):** 89.0ms
- **Processing Latency (Min):** 33.7ms
- **Processing Latency (Max):** 165.6ms

- **SNR (Avg):** 35.9dB
- **SNR (Min):** 10.9dB
- **SNR (Max):** 44.9dB

## Detailed Test Log

| # | Ground Truth | Predicted | Confidence | Latency (ms) | SNR (dB) | Result |
|--:|:-------------|:----------|----------:|-------------:|---------:|:------:|
| 1 | START | START | 0.68 | 74.9 | 43.1 | ✓ |
| 2 | JUMP | JUMP | 0.69 | 165.6 | 43.4 | ✓ |
| 3 | FLIP | START | 0.69 | 65.5 | 44.9 | ✗ |
| 4 | FLIP | FLIP | 0.69 | 163.8 | 43.0 | ✓ |
| 5 | START | START | 0.75 | 67.7 | 44.5 | ✓ |
| 6 | START | START | 0.61 | 36.6 | 13.5 | ✓ |
| 7 | JUMP | JUMP | 0.01 | 33.7 | 10.9 | ✓ |
| 8 | JUMP | JUMP | 0.67 | 104.4 | 43.8 | ✓ |

---
*✓ = Correct, ✗ = Incorrect*
*NOISE samples: NONE or NOISE prediction is considered correct*
