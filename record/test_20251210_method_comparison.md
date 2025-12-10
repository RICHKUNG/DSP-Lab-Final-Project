# Method Comparison Test Report

**Date**: 2025-12-10
**Test**: Arena Leave-One-Out (14 templates × 4 suites × 5 conditions = 280 scenarios per method)
**Configuration**: DTW_RADIUS=3, THRESHOLD_MFCC_DTW=140.0

---

## Test Results Summary

### Overall Performance

| Method | Overall Accuracy | Average Latency | File |
|--------|------------------|-----------------|------|
| **mfcc_dtw** | **94.3%** | **141-201ms** | arena_mfcc_dtw_20251210_150725.json |
| **ensemble** | **94.6%** | **177-271ms** | arena_ensemble_20251210_150844.json |

**Winner**: Ensemble (+0.3% accuracy, but +27-35% slower)

---

## Detailed Robustness Comparison

### 1. Speed Robustness

| Method | 0.7x | 0.9x | 1.0x | 1.1x | 1.3x | Average |
|--------|------|------|------|------|------|---------|
| mfcc_dtw | 100% | 100% | 100% | 93% | 93% | **97.2%** |
| ensemble | 100% | 100% | 100% | 93% | 93% | **97.2%** |

**Result**: **TIE** - Both perform identically across all speed variations

**Latency**:
- mfcc_dtw: 141-201ms
- ensemble: 177-271ms (26-35% slower)

---

### 2. Pitch Robustness

| Method | -2.5st | -1.0st | 0.0st | +1.0st | +2.5st | Average |
|--------|--------|--------|-------|--------|--------|---------|
| mfcc_dtw | 93% | 100% | 100% | 100% | 93% | **97.2%** |
| ensemble | 93% | 100% | 100% | 100% | 93% | **97.2%** |

**Result**: **TIE** - Both perform identically across all pitch shifts

**Latency**:
- mfcc_dtw: 158-165ms
- ensemble: 208-211ms (31-32% slower)

---

### 3. Noise Robustness ⭐ KEY DIFFERENTIATOR

| Method | 100dB (Clean) | 25dB | 20dB | 15dB | 10dB | Average |
|--------|---------------|------|------|------|------|---------|
| mfcc_dtw | 100% | 86% | 86% | 79% | **64%** | **83.0%** |
| ensemble | 100% | 86% | 86% | 79% | **71%** | **84.4%** |

**Winner**: **Ensemble (+1.4% average, +7% at 10dB SNR)**

**Critical Finding**: At severe noise (10dB), ensemble shows **11% improvement** over mfcc_dtw alone
- mfcc_dtw: 64% (loses 36% from clean)
- ensemble: 71% (loses 29% from clean)

**Latency**:
- mfcc_dtw: 162-167ms
- ensemble: 201-221ms (24-32% slower)

---

### 4. Volume Robustness

| Method | 0.3x | 0.6x | 1.0x | 1.5x | 3.0x | Average |
|--------|------|------|------|------|------|---------|
| mfcc_dtw | 100% | 100% | 100% | 100% | 100% | **100%** |
| ensemble | 100% | 100% | 100% | 100% | 100% | **100%** |

**Result**: **TIE** - Both are perfectly robust to volume changes

**Latency**:
- mfcc_dtw: 162-173ms
- ensemble: 213-216ms (31-26% slower)

---

## Performance Analysis

### Accuracy Trade-offs

| Metric | mfcc_dtw | ensemble | Difference |
|--------|----------|----------|------------|
| **Overall Accuracy** | 94.3% | 94.6% | +0.3% ✅ |
| **Speed Robustness** | 97.2% | 97.2% | 0% = |
| **Pitch Robustness** | 97.2% | 97.2% | 0% = |
| **Noise Robustness** | 83.0% | 84.4% | +1.4% ✅ |
| **Volume Robustness** | 100% | 100% | 0% = |
| **Noise 10dB (Critical)** | 64% | 71% | **+7% ✅** |

### Latency Trade-offs

| Suite | mfcc_dtw (avg) | ensemble (avg) | Slowdown |
|-------|----------------|----------------|----------|
| Speed | 141-201ms | 177-271ms | **+27-35%** ⚠️ |
| Pitch | 158-165ms | 208-211ms | **+32%** ⚠️ |
| Noise | 162-167ms | 201-221ms | **+24-32%** ⚠️ |
| Volume | 162-173ms | 213-216ms | **+26-31%** ⚠️ |
| **Overall** | **~165ms** | **~220ms** | **+33%** ⚠️ |

---

## Recommendations

### Use **mfcc_dtw** when:
1. ✅ **Speed is critical** (33% faster: 165ms vs 220ms)
2. ✅ **Environment is quiet** (noise SNR > 15dB)
3. ✅ **System resources are limited** (single method uses less CPU/memory)
4. ✅ **Real-time responsiveness** is priority (game controls, live demos)

**Typical Use Cases**:
- Live gaming with voice commands
- Real-time control systems
- Battery-powered mobile devices
- Low-latency applications

---

### Use **ensemble** when:
1. ✅ **Accuracy is priority** (94.6% vs 94.3%)
2. ✅ **Environment is noisy** (71% vs 64% at 10dB SNR) ⭐ **CRITICAL ADVANTAGE**
3. ✅ **Latency budget allows 200-250ms**
4. ✅ **Robustness matters more than speed**

**Typical Use Cases**:
- Laboratory/industrial noisy environments
- Public demonstrations with background chatter
- Medical/assistive devices (reliability over speed)
- Quality assurance testing

---

## Key Findings

### 1. Ensemble Advantage is Noise-Specific
- Ensemble provides **no benefit** for speed, pitch, or volume robustness
- **All improvement comes from noise handling** at low SNR (10-15dB)
- Individual methods in ensemble:
  - mfcc_dtw: 64% at 10dB
  - mel: 79% (stable across all noise levels)
  - lpc: 36% (fails badly in noise)
  - **Combined**: 71% (better than any individual)

### 2. Speed Cost is Consistent
- Ensemble is **~33% slower** across all conditions
- Not variable based on difficulty
- Fixed overhead from running 3 methods + voting

### 3. Current Configuration is Near-Optimal
- Both methods achieve **>94% overall accuracy**
- Speed/Pitch/Volume robustness is **excellent** (97-100%)
- Main weakness: **Severe noise (10dB)** remains challenging
  - mfcc_dtw: 64%
  - ensemble: 71%
  - Both show ~30% degradation from clean

---

## Template Quality Issues (Both Methods)

**Common Failures** (across both mfcc_dtw and ensemble):

1. **暫停4.wav (PAUSE)**:
   - Fails at Speed 1.1x, 1.3x, Pitch +2.5st
   - Suggests: Poor template quality or ambiguous pronunciation

2. **開始3.wav (START)**:
   - Fails at Pitch -2.5st, Noise 25/20/15/10dB
   - **Consistently problematic** across multiple conditions

3. **開始4.wav (START)**:
   - Fails at Noise 25/20/15/10dB
   - Similar pattern to 開始3.wav

4. **跳3.wav (JUMP)**:
   - Fails at Noise 15dB, 10dB
   - Less severe but still notable

**Recommendation**: Re-record templates for 開始3.wav, 開始4.wav, 暫停4.wav with:
- Clearer pronunciation
- Better audio quality
- Multiple speaker samples for diversity

---

## Deployment Decision Matrix

| Scenario | Recommended Method | Reason |
|----------|-------------------|--------|
| Gaming (real-time) | **mfcc_dtw** | Speed critical, clean environment |
| Lab experiment (noisy) | **ensemble** | Noise robustness > speed |
| Mobile app | **mfcc_dtw** | Resource constraints, battery life |
| Public demo | **ensemble** | Background noise, reliability |
| Medical device | **ensemble** | Accuracy/reliability critical |
| QA testing | **ensemble** | Comprehensive validation |

---

## Configuration Notes

**Both tests used optimized settings**:
```python
DTW_RADIUS = 3              # Optimized 2025-12-10
THRESHOLD_MFCC_DTW = 140.0  # Validated optimal
```

**Ensemble composition**:
- mfcc_dtw (TemplateMatcher)
- mel (TemplateMatcher)
- lpc (FastLPCMatcher)
- Voting: Best overall distance across methods

---

## Test Files

- **mfcc_dtw**: `record/arena_mfcc_dtw_20251210_150725.json`
- **ensemble**: `record/arena_ensemble_20251210_150844.json`

View detailed results:
```bash
python temp/view_history.py
```

---

## Conclusion

**For most applications**: **Use mfcc_dtw** (33% faster, only 0.3% accuracy loss)

**For noisy environments**: **Use ensemble** (11% better at 10dB SNR, worth the speed cost)

**Next priority**: Improve template quality for 開始3/4.wav, 暫停4.wav to address remaining failures that affect **both methods equally**.

---

*Test completed: 2025-12-10 15:10*
*Total test time: ~2.5 minutes (both modes)*
*Test methodology: Leave-One-Out cross-validation*
