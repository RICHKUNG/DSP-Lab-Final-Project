# Bio-Voice Commander - Complete Experiment Roadmap

**Date**: 2025-12-10
**Status**: Planning Phase
**Goal**: 系統化提升系統性能，突破當前瓶頸

---

## 📊 Current System Status

### Performance Metrics (2025-12-10)

| Metric | mfcc_dtw | ensemble | Status |
|--------|----------|----------|--------|
| Overall Accuracy | 94.3% | 94.6% | ✅ Excellent |
| Clean Accuracy | 100% | 100% | ✅ Perfect |
| Noise 10dB | 64% | 71% | ⚠️ **Bottleneck** |
| Average Latency | 165ms | 220ms | ✅ Good |
| Speed Robustness | 97.2% | 97.2% | ✅ Excellent |
| Pitch Robustness | 97.2% | 97.2% | ✅ Excellent |
| Volume Robustness | 100% | 100% | ✅ Perfect |

### Key Findings
- ✅ **Strengths**: Speed/Pitch/Volume 穩健性極佳
- ⚠️ **Bottleneck**: 噪音 10dB 準確率僅 64-71% (目標 >80%)
- 🐛 **Template Issues**: 開始3.wav, 開始4.wav 多次失敗
- 💡 **Insight**: mel 方法在噪音下穩定 (79% 不受 SNR 影響)

---

## 🗺️ Experiment Roadmap

### Phase 1: Quick Wins (A1) ⭐ PRIORITY
**Timeline**: Week 1 (1-2 days)
**Goal**: 快速驗證 adaptive ensemble 概念

### Phase 2: Advanced Features (A2, A3)
**Timeline**: Week 2-3 (1-2 weeks)
**Goal**: 深度優化噪音處理

### Phase 3: Comprehensive Testing (B1, B2)
**Timeline**: Week 4 (3-5 days)
**Goal**: 更嚴格的評估標準

### Phase 4: Fine-tuning (C1, C2)
**Timeline**: Week 5 (2-3 days)
**Goal**: 參數精調，追求極致

---

# 📋 Experiment Details

---

## A1: Noise-Adaptive Ensemble ⭐ **START HERE**

### Overview
**Type**: Advanced Feature
**Difficulty**: ⭐⭐☆☆☆ (Low-Medium)
**Time**: ~50 minutes
**Risk**: Low (可隨時回退)

### Problem
- Ensemble 在安靜環境浪費時間跑 3 個方法
- Ensemble 優勢僅在噪音環境（10dB: +7%）
- 需要智能化：安靜時快速，噪音時穩定

### Hypothesis
> 根據 SNR 動態調整方法權重，可以在保持噪音穩健性的同時降低延遲

### Strategy
```python
SNR > 30dB (Clean):  mfcc_dtw=0.7, mel=0.2, lpc=0.1  # Fast
15-30dB (Moderate):  mfcc_dtw=0.4, mel=0.4, lpc=0.2  # Balanced
SNR < 15dB (Noisy):  mfcc_dtw=0.2, mel=0.7, lpc=0.1  # Stable (mel 抗噪)
```

### Success Metrics
| Metric | Baseline | Target | Stretch |
|--------|----------|--------|---------|
| 10dB Accuracy | 71% | **75%** | 78% |
| Clean Latency | 220ms | **180ms** | 170ms |
| Overall Accuracy | 94.6% | **95%** | 96% |

### Implementation Steps
1. ✅ **Plan** - Done
2. ⏳ Create `src/audio_utils.py` - SNR estimation (10 min)
3. ⏳ Add `get_adaptive_weights()` to `recognizers.py` (5 min)
4. ⏳ Modify `MultiMethodMatcher.recognize()` (10 min)
5. ⏳ Update `test_arena.py` - add `adaptive_ensemble` (5 min)
6. ⏳ Run baseline test (5 min)
7. ⏳ Run adaptive test (5 min)
8. ⏳ Analyze & document (10 min)

### Files to Create/Modify
- **New**: `src/audio_utils.py`
- **Modify**: `src/recognizers.py`, `test_arena.py`
- **Output**: `record/arena_adaptive_ensemble_*.json`

### Next Steps if Success
- Fine-tune weight thresholds
- Try aggressive strategy (skip methods in clean env)
- Move to A2 (Spectral Subtraction)

### Next Steps if Failure
- Analyze SNR estimation accuracy
- Adjust weight allocation
- **Pivot**: Move to A2 (preprocessing approach)

---

## A2: Spectral Subtraction

### Overview
**Type**: Advanced Feature (Preprocessing)
**Difficulty**: ⭐⭐⭐☆☆ (Medium)
**Time**: ~2-3 hours
**Risk**: Medium (可能引入失真)

### Problem
- 噪音直接污染音訊信號
- 無論用什麼特徵，噪音都會影響辨識
- 需要在特徵提取前先移除噪音

### Hypothesis
> 在特徵提取前估計並減去噪音頻譜，可顯著提升 10dB 準確率

### Strategy

**Spectral Subtraction 原理**:
1. 估計噪音功率譜（從靜音段）
2. 從整體信號功率譜減去噪音功率譜
3. 重建乾淨的音訊信號

```python
def spectral_subtraction(noisy_audio, sr=16000, alpha=2.0):
    """
    頻譜減法噪音消除

    Args:
        noisy_audio: 含噪音的音訊
        alpha: 過減因子 (over-subtraction factor)

    Returns:
        Enhanced audio
    """
    # 1. STFT
    D = librosa.stft(noisy_audio)
    magnitude = np.abs(D)
    phase = np.angle(D)

    # 2. 估計噪音譜 (假設前 5 幀是純噪音)
    noise_magnitude = np.mean(magnitude[:, :5], axis=1, keepdims=True)

    # 3. 頻譜減法
    enhanced_magnitude = magnitude - alpha * noise_magnitude
    enhanced_magnitude = np.maximum(enhanced_magnitude, 0.1 * magnitude)  # Floor

    # 4. ISTFT 重建
    enhanced_D = enhanced_magnitude * np.exp(1j * phase)
    enhanced_audio = librosa.istft(enhanced_D)

    return enhanced_audio
```

### Success Metrics
| Metric | Baseline | Target | Stretch |
|--------|----------|--------|---------|
| **10dB Accuracy** | 71% | **80%** | 85% |
| 15dB Accuracy | 79% | **85%** | 90% |
| Clean Accuracy | 100% | **100%** | 100% (不能退化) |
| Latency Overhead | - | **<20ms** | <10ms |

### Implementation Steps
1. ⏳ Research librosa spectral enhancement methods (30 min)
2. ⏳ Implement `spectral_subtraction()` in `audio_utils.py` (45 min)
3. ⏳ Add preprocessing option to recognizers (15 min)
4. ⏳ Test on Arena with/without preprocessing (20 min)
5. ⏳ Fine-tune alpha parameter (30 min)
6. ⏳ Document results (20 min)

### Hyperparameters to Tune
```python
ALPHA = [1.5, 2.0, 2.5, 3.0]  # Over-subtraction factor
NOISE_FRAMES = [3, 5, 10]     # 假設前 N 幀是噪音
FLOOR_RATIO = [0.1, 0.2]      # 避免過度減法
```

### Risks & Mitigations
- ⚠️ **Risk**: 可能引入 musical noise（頻譜失真）
  - **Mitigation**: 使用 floor 限制，避免過度減法
- ⚠️ **Risk**: 假設前幾幀是純噪音可能不成立
  - **Mitigation**: 使用 VAD 找真正的靜音段

### Files to Create/Modify
- **Modify**: `src/audio_utils.py` - add spectral_subtraction
- **Modify**: `src/recognizers.py` - add preprocessing option
- **Modify**: `test_arena.py` - add `--preprocess spectral_sub`
- **Output**: `record/arena_spectral_sub_*.json`

### Next Steps if Success
- Combine with A1 (adaptive + preprocessing)
- Try other preprocessing: Wiener filtering
- Move to A3 (new features)

### Next Steps if Failure
- Try simpler preprocessing (bandpass filter)
- **Pivot**: Focus on template quality improvement

---

## A3: RASTA-PLP Features

### Overview
**Type**: Advanced Feature (New Feature Extractor)
**Difficulty**: ⭐⭐⭐⭐☆ (High)
**Time**: ~4-6 hours
**Risk**: High (大幅改動)

### Problem
- MFCC 在噪音下性能下降
- 需要更抗噪的特徵表示
- RASTA-PLP 專為噪音穩健性設計

### Hypothesis
> RASTA-PLP 特徵比 MFCC 更抗噪音，可提升 10dB 準確率

### Background

**RASTA-PLP vs MFCC**:
| Feature | MFCC | RASTA-PLP |
|---------|------|-----------|
| 頻率尺度 | Mel | Bark (更符合聽覺) |
| 噪音處理 | 無 | RASTA 濾波器（移除慢變噪音） |
| 通道效應 | 敏感 | 抗通道變化 |
| 計算複雜度 | 低 | 中 |

**RASTA Filter**:
- 高通濾波器，移除頻譜包絡的慢速變化
- 保留快速變化（語音特性）
- 去除穩態噪音

### Strategy

```python
# Using python_speech_features or custom implementation
from python_speech_features import rasta_plp

def extract_rasta_plp(audio, sr=16000, n_coeffs=13):
    """
    提取 RASTA-PLP 特徵

    Returns:
        RASTA-PLP coefficients (shape: [n_frames, n_coeffs])
    """
    features = rasta_plp(audio, samplerate=sr, numcep=n_coeffs)
    return features
```

### Success Metrics
| Metric | MFCC | RASTA-PLP Target | Improvement |
|--------|------|------------------|-------------|
| **10dB Accuracy** | 64% | **75%+** | +11% |
| 15dB Accuracy | 79% | **85%+** | +6% |
| Clean Accuracy | 100% | **98%+** | -2% (可接受) |

### Implementation Steps
1. ⏳ Research RASTA-PLP libraries (1 hour)
2. ⏳ Install dependencies (python_speech_features) (15 min)
3. ⏳ Create `RastaPLPMatcher` class (1 hour)
4. ⏳ Test on single template (30 min)
5. ⏳ Run Arena test (10 min)
6. ⏳ Compare with MFCC (30 min)
7. ⏳ Add to ensemble if successful (30 min)
8. ⏳ Document results (30 min)

### Files to Create/Modify
- **New**: `src/features.py` - RASTA-PLP extraction
- **New**: Class in `recognizers.py` - RastaPLPMatcher
- **Modify**: `MultiMethodMatcher` - add rasta_plp option
- **Output**: `record/arena_rasta_plp_*.json`

### Risks & Mitigations
- ⚠️ **Risk**: RASTA-PLP 可能在安靜環境表現較差
  - **Mitigation**: 只在噪音環境啟用，或加入 ensemble
- ⚠️ **Risk**: 實施複雜，可能引入 bugs
  - **Mitigation**: 從簡單實現開始，逐步優化
- ⚠️ **Risk**: 計算開銷增加
  - **Mitigation**: Profile 性能，必要時優化

### Next Steps if Success
- Add RASTA-PLP to adaptive ensemble
- Test combined effect (A1 + A2 + A3)
- **Goal**: 10dB accuracy >85%

### Next Steps if Failure
- RASTA-PLP 可能不適合此應用
- **Pivot**: 回到模板質量改善

---

## B1: Arena 極端條件測試

### Overview
**Type**: Testing Enhancement
**Difficulty**: ⭐☆☆☆☆ (Very Low)
**Time**: ~1 hour (implementation) + 10 min per test
**Risk**: None (純測試)

### Problem
- 當前 Arena 測試可能不夠嚴格
- 不知道系統的真正極限在哪裡
- 需要更極端的條件來暴露弱點

### Hypothesis
> 更極端的測試條件會暴露當前系統的極限，幫助找到下一步優化方向

### New Test Suites

```python
# Current (Baseline)
TEST_SUITES = {
    'Speed': [0.7, 0.9, 1.0, 1.1, 1.3],
    'Pitch': [-2.5, -1.0, 0.0, 1.0, 2.5],
    'Noise': [100, 25, 20, 15, 10],
    'Volume': [0.3, 0.6, 1.0, 1.5, 3.0]
}

# New (Extreme)
TEST_SUITES_EXTREME = {
    'Speed': [0.5, 0.7, 0.9, 1.0, 1.1, 1.3, 1.5],  # +2 extreme values
    'Pitch': [-5, -2.5, 0.0, 2.5, 5],              # Doubled range
    'Noise': [100, 25, 20, 15, 10, 5, 0],          # +2 extreme (5dB, 0dB)
    'Volume': [0.1, 0.3, 0.6, 1.0, 1.5, 3.0, 5.0]  # +2 extreme
}
```

### Test Matrix Comparison

| Suite | Current Conditions | Extreme Conditions | Added |
|-------|-------------------|-------------------|--------|
| Speed | 5 | **7** | +40% |
| Pitch | 5 | **5** | (doubled range) |
| Noise | 5 | **7** | +40% |
| Volume | 5 | **7** | +40% |
| **Total** | **20** | **26** | **+30% scenarios** |

### Success Metrics
**Goal**: 找出系統崩潰點

| Condition | Expected Accuracy | Failure Threshold |
|-----------|-------------------|-------------------|
| Speed 0.5x | 70-80% | <60% = serious issue |
| Speed 1.5x | 70-80% | <60% |
| Pitch ±5st | 60-70% | <50% |
| Noise 5dB | 40-50% | <30% = unusable |
| Noise 0dB | 20-30% | Expected to fail |
| Volume 0.1x | 50-60% | <40% |
| Volume 5.0x | 80-90% | <70% |

### Implementation Steps
1. ⏳ Create `test_arena_extreme.py` (copy from test_arena.py) (10 min)
2. ⏳ Update TEST_SUITES to extreme values (5 min)
3. ⏳ Run extreme test (10 min)
4. ⏳ Compare with baseline (10 min)
5. ⏳ Document failure modes (30 min)

### Analysis Questions
1. **At what noise level does the system become unusable?** (Target: >5dB)
2. **How extreme speed variation can it handle?** (Target: 0.5x-1.5x)
3. **Which condition degrades fastest?** (Likely: extreme noise)
4. **Are there catastrophic failure modes?** (e.g., all commands → NOISE)

### Files to Create
- **New**: `test_arena_extreme.py`
- **Output**: `record/arena_extreme_*.json`
- **Report**: `record/test_extreme_conditions_report.md`

### Next Steps
- Identify worst-performing conditions
- Prioritize optimization efforts
- Use as benchmark for future improvements

---

## B2: Arena 混合條件測試

### Overview
**Type**: Testing Enhancement
**Difficulty**: ⭐⭐☆☆☆ (Low-Medium)
**Time**: ~2 hours (implementation) + 15 min per test
**Risk**: None (純測試)

### Problem
- 當前測試只有單一條件變化
- 真實環境常是多種干擾同時存在
- 例如：快速說話 + 背景噪音 + 距離遠（音量小）

### Hypothesis
> 混合條件會暴露單一條件測試無法發現的弱點

### Test Scenarios

**Scenario Design**:
```python
MIXED_SCENARIOS = {
    # Realistic scenarios
    'indoor_quiet': {
        'speed': 1.0,
        'pitch': 0.0,
        'noise_snr': 100,
        'volume': 1.0
    },
    'fast_speech_noisy': {  # 快速說話 + 噪音
        'speed': 1.3,
        'pitch': 0.0,
        'noise_snr': 15,
        'volume': 1.0
    },
    'distant_speaker': {  # 距離遠 + 輕微噪音
        'speed': 1.0,
        'pitch': 0.0,
        'noise_snr': 25,
        'volume': 0.3
    },
    'excited_speaker': {  # 激動說話（快速 + 音高高 + 大聲）
        'speed': 1.2,
        'pitch': 2.0,
        'noise_snr': 100,
        'volume': 2.0
    },
    'tired_speaker': {  # 疲倦說話（慢速 + 音高低 + 小聲）
        'speed': 0.8,
        'pitch': -2.0,
        'noise_snr': 100,
        'volume': 0.5
    },
    'outdoor_demo': {  # 戶外展示（噪音 + 距離 + 可能音高變化）
        'speed': 1.0,
        'pitch': 1.0,
        'noise_snr': 10,
        'volume': 0.5
    },
    'factory_environment': {  # 工廠環境（嚴重噪音）
        'speed': 1.0,
        'pitch': 0.0,
        'noise_snr': 5,
        'volume': 2.0  # 需要大聲說
    },
    'worst_case': {  # 最壞情況
        'speed': 1.3,
        'pitch': 2.5,
        'noise_snr': 10,
        'volume': 0.3
    }
}
```

### Expected Results

| Scenario | Expected Acc | Why |
|----------|-------------|-----|
| indoor_quiet | 100% | Baseline (clean) |
| fast_speech_noisy | 60-70% | Speed OK, but 15dB noise hurts |
| distant_speaker | 70-80% | Volume shouldn't matter much |
| excited_speaker | 90-95% | All factors within tolerance |
| tired_speaker | 85-90% | Slow is fine, low pitch OK |
| outdoor_demo | 50-60% | 10dB noise + volume = challenging |
| factory_environment | 40-50% | 5dB noise is very hard |
| worst_case | 30-40% | Everything wrong at once |

### Implementation Steps
1. ⏳ Design mixed scenarios (30 min)
2. ⏳ Modify `apply_augmentation()` to support multiple effects (30 min)
3. ⏳ Create `test_arena_mixed.py` (45 min)
4. ⏳ Run mixed tests (15 min)
5. ⏳ Analyze interaction effects (30 min)
6. ⏳ Document findings (30 min)

### Analysis Questions
1. **Do effects compound or cancel?**
   - E.g., speed + noise worse than sum of individual effects?
2. **Which combinations are worst?**
   - Likely: noise + speed or noise + volume
3. **Can we identify "safe zones"?**
   - E.g., "OK if SNR >15dB regardless of speed"

### Files to Create
- **New**: `test_arena_mixed.py`
- **Modify**: `apply_augmentation()` - support multi-effect
- **Output**: `record/arena_mixed_*.json`
- **Report**: `record/test_mixed_conditions_report.md`

### Next Steps
- Use findings to prioritize real-world optimization
- Create deployment guidelines (e.g., "works best in quiet <15dB")

---

## C1: MFCC 參數網格搜索

### Overview
**Type**: Hyperparameter Tuning
**Difficulty**: ⭐⭐☆☆☆ (Low-Medium)
**Time**: ~6-8 hours (mostly waiting)
**Risk**: Low

### Problem
- 當前 MFCC 參數可能不是最優
- 使用默認值：n_mfcc=13, n_fft=1024, hop_length=512
- 系統化搜索可能找到更好的組合

### Hypothesis
> 優化 MFCC 參數可提升 0.5-2% 準確率

### Search Space

```python
PARAM_GRID = {
    'n_mfcc': [10, 13, 16, 20],           # 4 values
    'n_fft': [512, 1024, 2048],           # 3 values
    'hop_length': [256, 512, 1024],       # 3 values
    'n_mels': [64, 128, 256],             # 3 values (for mel method)
    'fmin': [80, 100, 133],               # 3 values
    'fmax': [7600, 8000, 16000],          # 3 values
}

# Total combinations: 4 × 3 × 3 = 36 for MFCC alone
# With n_mels: 36 × 3 = 108 total
```

### Search Strategy

**Option A: Full Grid Search** (not recommended)
- 108 configurations × 5 min = **9 hours**
- Too slow

**Option B: Random Search** (recommended)
- Sample 20 random configurations
- 20 × 5 min = **100 minutes**
- Statistically likely to find good configs

**Option C: Bayesian Optimization** (advanced)
- Use Optuna or similar
- Intelligent sampling based on previous results
- ~30 trials = **150 minutes**
- Higher chance of finding global optimum

### Implementation Steps

**Phase 1: Setup** (30 min)
1. ⏳ Create `scripts/grid_search_mfcc.py`
2. ⏳ Implement parameter sampling
3. ⏳ Setup logging for all trials

**Phase 2: Search** (2-3 hours)
4. ⏳ Run random search (20 configs)
5. ⏳ Monitor progress
6. ⏳ Save all results

**Phase 3: Analysis** (1 hour)
7. ⏳ Rank configurations by overall accuracy
8. ⏳ Analyze parameter importance
9. ⏳ Test top 3 configs on Arena
10. ⏳ Document findings

### Success Metrics

| Metric | Current | Target | Stretch |
|--------|---------|--------|---------|
| Overall Accuracy | 94.3% | **95%** | 96% |
| 10dB Accuracy | 64% | **68%** | 70% |
| Latency | 165ms | **<170ms** | <165ms (no degradation) |

### Files to Create
- **New**: `scripts/grid_search_mfcc.py`
- **Output**: `record/grid_search_results.json`
- **Report**: `record/grid_search_report.md`

### Expected Findings
- n_mfcc: Likely 13-16 is optimal (more may overfit)
- n_fft: 1024 likely already optimal
- hop_length: May find 256 gives better time resolution

### Next Steps if Success
- Update `config.py` with best parameters
- Validate on fresh test set
- Combine with other improvements

---

## C2: Threshold 精調

### Overview
**Type**: Hyperparameter Tuning
**Difficulty**: ⭐⭐☆☆☆ (Low-Medium)
**Time**: ~4-6 hours (mostly waiting)
**Risk**: Low

### Problem
- 當前 thresholds 基於經驗設定
- THRESHOLD_MFCC_DTW = 140.0 (已驗證，但可能不是全局最優)
- THRESHOLD_MEL = 0.40
- THRESHOLD_LPC = 100.0

### Hypothesis
> 系統化搜索 threshold 組合可減少 false positives/negatives

### Search Space

```python
THRESHOLD_GRID = {
    'mfcc_dtw': [120, 130, 140, 150, 160],  # 5 values
    'mel': [0.35, 0.40, 0.45, 0.50],        # 4 values
    'lpc': [80, 90, 100, 110, 120],         # 5 values
}

# Total combinations: 5 × 4 × 5 = 100
# At ~5 min each = 500 minutes = 8+ hours (too slow)
```

### Search Strategy

**Option A: Sequential Optimization** (recommended)
1. Fix mel, lpc → optimize mfcc_dtw (5 trials)
2. Fix mfcc_dtw, lpc → optimize mel (4 trials)
3. Fix mfcc_dtw, mel → optimize lpc (5 trials)
4. **Total: 14 trials × 5 min = 70 minutes**

**Option B: Random Search**
- Sample 25 random combinations
- **Total: 125 minutes**

**Option C: Focus on mfcc_dtw only**
- Already validated 140 is good
- Fine search around it: [135, 138, 140, 142, 145]
- **Total: 5 trials × 5 min = 25 minutes**

### Metrics to Optimize

**Primary**: Overall Accuracy
**Secondary**: Balance between:
- False Positives (wrong command detected)
- False Negatives (NOISE when should be command)

**Ideal Threshold**:
```
Maximize: Correct commands
Minimize: Wrong commands + False alarms
```

### Implementation Steps

**Phase 1: Setup** (20 min)
1. ⏳ Create `scripts/threshold_search.py`
2. ⏳ Implement sequential optimization
3. ⏳ Add metrics tracking

**Phase 2: Search** (1-2 hours)
4. ⏳ Run sequential search
5. ⏳ Monitor FP/FN rates
6. ⏳ Save results

**Phase 3: Validation** (30 min)
7. ⏳ Test top 3 threshold sets on Arena
8. ⏳ Compare with baseline
9. ⏳ Document findings

### Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Overall Accuracy | 94.6% | **95%+** |
| FP Rate (wrong cmd) | ~3% | **<2%** |
| FN Rate (missed cmd) | ~2% | **<1.5%** |

### Files to Create
- **New**: `scripts/threshold_search.py`
- **Output**: `record/threshold_search_results.json`
- **Report**: `record/threshold_optimization_report.md`

### Expected Findings
- mfcc_dtw threshold: Likely 140 is already near-optimal (previously validated)
- mel threshold: May benefit from slight adjustment
- lpc threshold: May need increase (currently many false positives)

### Next Steps if Success
- Update `config.py` with optimal thresholds
- Validate stability across different test sets
- Combine with other improvements

---

# 🗺️ Complete Roadmap Summary

## Recommended Execution Order

### Week 1: Quick Wins
```
Day 1: A1 - Noise-Adaptive Ensemble (50 min) ⭐ START HERE
Day 2: B1 - Extreme Testing (1 hour)
Day 3: C2 - Threshold Fine-tune (2 hours)
```
**Expected Gain**: +1-2% accuracy, -10% latency

### Week 2: Deep Optimization
```
Day 1-2: A2 - Spectral Subtraction (3 hours)
Day 3: B2 - Mixed Conditions (2 hours)
```
**Expected Gain**: +5-10% at 10dB noise

### Week 3: Advanced Features (if needed)
```
Day 1-3: A3 - RASTA-PLP (6 hours)
Day 4-5: C1 - MFCC Grid Search (4 hours)
```
**Expected Gain**: +2-3% overall accuracy

---

## Success Milestones

### Milestone 1: 95% Overall Accuracy ✅
- **Path**: A1 + C2
- **Time**: 3 days
- **Probability**: High (80%)

### Milestone 2: 75% at 10dB Noise 🎯
- **Path**: A1 + A2
- **Time**: 1 week
- **Probability**: Medium (60%)

### Milestone 3: 80% at 10dB Noise 🚀
- **Path**: A1 + A2 + A3
- **Time**: 2-3 weeks
- **Probability**: Medium-Low (40%)

### Milestone 4: Production Ready 🏆
- **Path**: All optimizations + comprehensive testing
- **Time**: 4 weeks
- **Criteria**:
  - Overall ≥96%
  - 10dB ≥75%
  - Latency <200ms
  - Robust in mixed conditions

---

## Dependency Graph

```
A1 (Adaptive Ensemble) ⭐ START
├─→ A2 (Spectral Sub) [if A1 succeeds]
│   └─→ A3 (RASTA-PLP) [if A2 succeeds]
│
├─→ B1 (Extreme Test) [parallel, validation]
│   └─→ B2 (Mixed Test) [after B1]
│
└─→ C2 (Threshold) [quick win, parallel]
    └─→ C1 (MFCC Grid) [if time permits]
```

---

## Resource Requirements

| Experiment | Time | Compute | Risk | Priority |
|------------|------|---------|------|----------|
| A1 | 50 min | Low | Low | ⭐⭐⭐⭐⭐ |
| A2 | 3 hours | Medium | Medium | ⭐⭐⭐⭐☆ |
| A3 | 6 hours | Medium | High | ⭐⭐⭐☆☆ |
| B1 | 1 hour | Low | None | ⭐⭐⭐⭐☆ |
| B2 | 2 hours | Low | None | ⭐⭐⭐☆☆ |
| C1 | 4 hours | High | Low | ⭐⭐☆☆☆ |
| C2 | 2 hours | Medium | Low | ⭐⭐⭐⭐☆ |

---

## 🎯 Decision: What to Start?

**My Recommendation**: **A1 (Noise-Adaptive Ensemble)**

**Why?**
- ✅ Highest priority (⭐⭐⭐⭐⭐)
- ✅ Lowest risk
- ✅ Fastest implementation (50 min)
- ✅ High success probability
- ✅ Good foundation for A2, A3

**Ready to proceed with A1?** 🚀

Or would you like to:
- Review any specific experiment plan in detail?
- Adjust the roadmap?
- Start with a different experiment?
