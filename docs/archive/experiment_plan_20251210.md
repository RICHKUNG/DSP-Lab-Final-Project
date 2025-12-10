# Noise Robustness & Accuracy Optimization Experiment Plan

**Date**: 2025-12-10
**Objective**: Optimize for noise robustness and accuracy (speed is secondary)
**Current Baseline**: 80.0% overall, Clean 86.7% → 10dB 60.0% (26.7% drop)

## Problem Analysis

1. **Noise Sensitivity**: 26.7% accuracy drop from clean to 10dB noise
2. **Current DTW_RADIUS = 2**: Optimized for speed, may sacrifice robustness
3. **Single threshold for all conditions**: May need adaptive strategy

## Experiment Design

### Experiment 1: DTW_RADIUS Optimization
**Hypothesis**: Larger radius allows more flexible alignment, improving noise robustness

| Config | DTW_RADIUS | Expected Impact |
|--------|------------|-----------------|
| E1-A (Current) | 2 | Baseline (fast) |
| E1-B | 3 | Moderate flexibility |
| E1-C | 5 | High flexibility (original) |
| E1-D | 7 | Maximum flexibility |

**Metrics to track**:
- Noise accuracy (10dB, 15dB, 20dB)
- Speed penalty
- Overall accuracy

---

### Experiment 2: MFCC Feature Enhancement
**Hypothesis**: More MFCC coefficients capture richer spectral information, improving discrimination

| Config | N_MFCC | HOP_LENGTH | Expected Impact |
|--------|--------|------------|-----------------|
| E2-A (Current) | 13 | 512 | Baseline |
| E2-B | 20 | 512 | More spectral detail |
| E2-C | 13 | 256 | Better temporal resolution |
| E2-D | 20 | 256 | Both improvements |

**Metrics to track**:
- Accuracy in all conditions
- Processing time increase

---

### Experiment 3: Threshold Adaptation
**Hypothesis**: Noise increases feature distances, requiring relaxed thresholds

| Config | THRESHOLD_MFCC_DTW | Notes |
|--------|-------------------|-------|
| E3-A (Current) | 140.0 | Baseline |
| E3-B | 160.0 | +14% (moderate) |
| E3-C | 180.0 | +28% (relaxed) |
| E3-D | 200.0 | +42% (very relaxed) |

**Metrics to track**:
- False positive rate (NONE → Command)
- Noise accuracy improvement

---

### Experiment 4: Advanced Strategy (if needed)
**Hypothesis**: Ensemble can be weighted differently in noisy conditions

Potential strategies:
- Use only MFCC+DTW in noise (other methods may degrade more)
- Implement noise-adaptive thresholds
- Add spectral subtraction preprocessing

---

## Success Criteria

**Primary Goals**:
1. **Noise Robustness**: 10dB accuracy > 70% (currently 60%)
2. **Overall Accuracy**: Maintain or improve 80%+
3. **Clean Accuracy**: Maintain 85%+

**Secondary Goal**:
- Processing time < 400ms acceptable (currently ~217ms)

## Execution Plan

1. Run baseline test with current config (already done)
2. Execute E1 (DTW_RADIUS): 4 tests
3. Analyze E1, select best radius
4. Execute E2 (MFCC params) with best radius: 4 tests
5. Analyze E2, select best feature config
6. Execute E3 (Thresholds) with best config: 4 tests
7. Final validation and documentation

## Expected Timeline

- E1: ~20 min (4 arena tests)
- E2: ~20 min (4 arena tests)
- E3: ~20 min (4 arena tests)
- Analysis & documentation: ~30 min
- **Total**: ~90 minutes
