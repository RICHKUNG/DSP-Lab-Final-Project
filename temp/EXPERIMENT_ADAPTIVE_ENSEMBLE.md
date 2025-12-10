# Experiment: Noise-Adaptive Ensemble

**Date**: 2025-12-10
**Experimenter**: Claude
**Goal**: 提升 10dB 噪音準確率從 71% → 75%+，同時降低平均延遲

---

## 📋 實驗計劃

### 問題定義

**Current Baseline** (from test_20251210_method_comparison.md):
- Ensemble 在 10dB 噪音: **71%** (vs mfcc_dtw: 64%)
- Ensemble 平均延遲: **220ms** (vs mfcc_dtw: 165ms)
- **問題**: Ensemble 在安靜環境浪費時間跑 3 個方法，但只在噪音下有優勢

**Key Insight** (from Arena results):
- mel 方法在**所有噪音等級都穩定在 79%** (100dB→10dB 不變)
- mfcc_dtw 在安靜環境最快最準 (100dB: 100%, 165ms)
- lpc 在噪音下崩潰 (10dB: 36%)

**Hypothesis**:
> 如果根據噪音程度動態調整方法權重，可以：
> 1. 安靜環境：接近 mfcc_dtw 速度 (165ms)
> 2. 噪音環境：接近 mel 穩定性 (79%)
> 3. 整體效果：比固定 ensemble 更好

---

## 🎯 實驗目標

### Success Metrics

| Metric | Baseline | Target | Stretch Goal |
|--------|----------|--------|--------------|
| **10dB Accuracy** | 71% | **75%** | 80% |
| **Clean Accuracy** | 100% | **100%** | 100% |
| **Avg Latency (Clean)** | 220ms | **<180ms** | <170ms |
| **Avg Latency (10dB)** | 216ms | **<200ms** | <180ms |
| **Overall Accuracy** | 94.6% | **95%+** | 96%+ |

### Risk Assessment

**Low Risk** ✅:
- 不改變現有架構
- 可隨時回退到固定權重
- 只是智能化現有的 ensemble

---

## 🔬 實驗設計

### Phase 1: SNR 估計 (Signal-to-Noise Ratio)

**方法**: 基於能量的 SNR 估計

```python
def estimate_snr(audio: np.ndarray, sample_rate: int = 16000) -> float:
    """
    估計音訊的 SNR (dB)

    方法：
    1. 偵測語音段和靜音段
    2. 計算語音能量 vs 靜音能量比
    3. 轉換為 dB

    Returns:
        SNR in dB (估計值，可能不準確但足夠分類用)
        - >30dB: 認為是安靜環境
        - 15-30dB: 中度噪音
        - <15dB: 嚴重噪音
    """
    # Implementation details below
```

**驗證**: 對 Arena test 的噪音樣本測試，確認能大致分類

---

### Phase 2: Adaptive Weighting Strategy

**策略設計**:

```python
def get_adaptive_weights(estimated_snr: float) -> dict:
    """
    根據 SNR 返回各方法的權重

    Args:
        estimated_snr: 估計的 SNR (dB)

    Returns:
        weights: {'mfcc_dtw': w1, 'mel': w2, 'lpc': w3}
    """
    if estimated_snr > 30:
        # Clean environment - favor mfcc_dtw (fast & accurate)
        return {
            'mfcc_dtw': 0.7,  # 主力
            'mel': 0.2,
            'lpc': 0.1
        }
    elif estimated_snr > 15:
        # Moderate noise - balanced
        return {
            'mfcc_dtw': 0.4,
            'mel': 0.4,
            'lpc': 0.2
        }
    else:
        # Severe noise (<=15dB) - favor mel (stable in noise)
        return {
            'mfcc_dtw': 0.2,
            'mel': 0.7,  # mel 在噪音下穩定
            'lpc': 0.1   # lpc 在噪音下很差
        }
```

**Alternative Strategy** (可測試):
```python
# 更激進：安靜時只用 mfcc_dtw
if estimated_snr > 30:
    return {'mfcc_dtw': 1.0, 'mel': 0.0, 'lpc': 0.0}  # Skip others!
```

---

### Phase 3: Implementation

**修改位置**: `src/recognizers.py` - `MultiMethodMatcher.recognize()`

**Before** (固定權重):
```python
def recognize(self, audio: np.ndarray, mode: str = 'best') -> Dict:
    # Run all methods
    results = {}
    for method_name, matcher in self.matchers.items():
        results[method_name] = matcher.recognize(audio)

    # Equal weight voting
    best_command = vote_ensemble(results)  # 每個方法權重相同
    return {'command': best_command, 'all_results': results}
```

**After** (adaptive 權重):
```python
def recognize(self, audio: np.ndarray, mode: str = 'best',
              adaptive: bool = True) -> Dict:
    # Estimate SNR
    snr = estimate_snr(audio) if adaptive else 50.0  # 50 = assume clean

    # Get adaptive weights
    weights = get_adaptive_weights(snr)

    # Run all methods
    results = {}
    for method_name, matcher in self.matchers.items():
        results[method_name] = matcher.recognize(audio)

    # Weighted voting
    best_command = vote_ensemble_weighted(results, weights)

    return {
        'command': best_command,
        'all_results': results,
        'snr_estimate': snr,  # For debugging
        'weights_used': weights
    }
```

---

### Phase 4: Testing Protocol

**Test Sequence**:

1. **Baseline** - Re-run ensemble (確認可重現)
   ```bash
   python test_arena.py --method ensemble
   # Expected: 94.6%, 220ms, 10dB=71%
   ```

2. **Adaptive Ensemble** - 新方法測試
   ```bash
   python test_arena.py --method adaptive_ensemble
   # Target: 95%+, <200ms, 10dB=75%+
   ```

3. **Comparison** - 使用 view_history.py 比較

4. **Analysis**:
   - 檢查 SNR 估計是否合理
   - 檢查權重分配是否符合預期
   - 分析哪些場景改善、哪些變差

---

## 📊 預期結果

### Best Case Scenario 🎉

| Condition | Baseline | Adaptive | Improvement |
|-----------|----------|----------|-------------|
| Clean (100dB) | 100% / 214ms | 100% / **170ms** | **-21% latency** |
| 25dB | 86% / 221ms | **90%** / 190ms | +4% acc, -14% latency |
| 10dB | 71% / 216ms | **78%** / 200ms | +7% acc, -7% latency |
| Overall | 94.6% / 220ms | **96%** / **190ms** | +1.4% acc, -14% latency |

### Realistic Scenario ✅

| Condition | Baseline | Adaptive | Improvement |
|-----------|----------|----------|-------------|
| Clean | 100% / 214ms | 100% / **180ms** | **-16% latency** |
| 10dB | 71% / 216ms | **75%** / 210ms | +4% acc |
| Overall | 94.6% / 220ms | **95%** / **200ms** | +0.4% acc, -9% latency |

### Worst Case Scenario ⚠️

- SNR 估計不準 → 權重分配錯誤 → 性能下降
- **Mitigation**: 保守的權重設計，避免極端權重

---

## 🛠️ Implementation Steps

### Step 1: SNR Estimation Function ⏱️ 10 min

**File**: `src/audio_utils.py` (new file)

```python
import numpy as np
from scipy import signal

def estimate_snr(audio: np.ndarray, sample_rate: int = 16000,
                 frame_length_ms: int = 20) -> float:
    """
    估計音訊的信噪比 (SNR)

    簡化方法：
    1. 計算短時能量
    2. 找出語音段（高能量）和靜音段（低能量）
    3. SNR = 10 * log10(語音能量 / 噪音能量)

    Returns:
        Estimated SNR in dB (粗略估計)
    """
    # Convert to float
    if audio.dtype == np.int16:
        audio = audio.astype(np.float32) / 32767.0

    # Compute short-time energy
    frame_length = int(sample_rate * frame_length_ms / 1000)
    hop_length = frame_length // 2

    energy = []
    for i in range(0, len(audio) - frame_length, hop_length):
        frame = audio[i:i+frame_length]
        energy.append(np.sum(frame ** 2))

    energy = np.array(energy)

    # Separate signal and noise using threshold
    threshold = np.percentile(energy, 40)  # Bottom 40% as noise

    noise_energy = np.mean(energy[energy < threshold])
    signal_energy = np.mean(energy[energy >= threshold])

    # Compute SNR
    if noise_energy > 0:
        snr_db = 10 * np.log10(signal_energy / noise_energy)
    else:
        snr_db = 100.0  # Very clean

    return float(snr_db)
```

**Test**:
```python
# Test on known SNR samples from Arena
# Verify: 100dB → high SNR (>30)
#         10dB → low SNR (<15)
```

---

### Step 2: Adaptive Weighting ⏱️ 5 min

**File**: `src/recognizers.py` - add helper function

```python
def get_adaptive_weights(snr_db: float) -> Dict[str, float]:
    """
    根據估計的 SNR 返回各方法權重

    Strategy:
    - Clean (>30dB): Favor mfcc_dtw (fast, accurate)
    - Moderate (15-30dB): Balanced
    - Noisy (<15dB): Favor mel (stable in noise)
    """
    if snr_db > 30:
        return {'mfcc_dtw': 0.7, 'mel': 0.2, 'lpc': 0.1}
    elif snr_db > 15:
        return {'mfcc_dtw': 0.4, 'mel': 0.4, 'lpc': 0.2}
    else:
        return {'mfcc_dtw': 0.2, 'mel': 0.7, 'lpc': 0.1}
```

---

### Step 3: Modify MultiMethodMatcher ⏱️ 10 min

**File**: `src/recognizers.py`

```python
class MultiMethodMatcher:
    def recognize(self, audio: np.ndarray, mode: str = 'best',
                  adaptive: bool = False) -> Dict:
        """
        Args:
            adaptive: If True, use noise-adaptive weighting
        """
        # Run all methods
        results = {}
        for method_name, matcher in self.matchers.items():
            results[method_name] = matcher.recognize(audio)

        if adaptive:
            # Import SNR estimator
            from src.audio_utils import estimate_snr
            snr = estimate_snr(audio)
            weights = get_adaptive_weights(snr)
            best_command = self._weighted_vote(results, weights)
        else:
            # Original equal-weight voting
            best_command = self._simple_vote(results)

        return {
            'command': best_command,
            'all_results': results,
            'snr_estimate': snr if adaptive else None,
            'weights': weights if adaptive else None
        }

    def _weighted_vote(self, results: Dict, weights: Dict) -> str:
        """加權投票"""
        # Collect all commands with weighted distances
        command_scores = defaultdict(float)

        for method, result in results.items():
            cmd = result['command']
            if cmd not in ['NOISE', 'NONE']:
                # Lower distance = higher confidence
                # Use inverse distance as score
                dist = result.get('distance', result.get('min_distance', 999))
                score = weights.get(method, 0.33) / (dist + 1e-6)
                command_scores[cmd] += score

        if command_scores:
            return max(command_scores, key=command_scores.get)
        return 'NOISE'

    def _simple_vote(self, results: Dict) -> str:
        """原本的簡單投票"""
        votes = [r['command'] for r in results.values()]
        return max(set(votes), key=votes.count)
```

---

### Step 4: Update test_arena.py ⏱️ 5 min

**File**: `test_arena.py`

Add new method option:
```python
parser.add_argument('--method', choices=['mfcc_dtw', 'ensemble', 'adaptive_ensemble'])

# In run_arena():
if method == 'adaptive_ensemble':
    # Use ensemble with adaptive=True
    results = matcher.recognize(input_audio, mode='all', adaptive=True)
```

---

### Step 5: Run Tests ⏱️ 10 min

```bash
# Baseline comparison
python test_arena.py --method ensemble

# New adaptive method
python test_arena.py --method adaptive_ensemble

# Compare
python temp/view_history.py
```

---

## 📈 Success Criteria

### Minimum Success ✅
- 10dB accuracy ≥ 73% (current: 71%)
- Overall accuracy ≥ 95% (current: 94.6%)
- No degradation in clean environment

### Target Success 🎯
- 10dB accuracy ≥ 75%
- Average latency < 200ms (current: 220ms)
- Clean environment latency < 180ms

### Stretch Success 🚀
- 10dB accuracy ≥ 78%
- Average latency < 190ms
- Ready for deployment

---

## 🔄 Iteration Plan

### If Success → Phase 2

1. Fine-tune weight thresholds
2. Test more aggressive strategies (e.g., skip methods entirely in clean env)
3. Add confidence-based fallback

### If Partial Success → Analyze & Adjust

1. Check SNR estimation accuracy
2. Adjust weight allocation
3. Try alternative voting mechanisms

### If Failure → Pivot

→ Move to **Spectral Subtraction** (noise removal preprocessing)

---

## 📝 Documentation

**Files to Create**:
- `src/audio_utils.py` - SNR estimation
- `record/arena_adaptive_ensemble_*.json` - Test results
- `record/test_adaptive_ensemble_report.md` - Analysis report

**Files to Update**:
- `src/recognizers.py` - Add adaptive weighting
- `test_arena.py` - Add adaptive_ensemble option
- `README.md` - Document new method

---

## ⏱️ Timeline

| Step | Task | Time | Status |
|------|------|------|--------|
| 1 | Create SNR estimation | 10 min | ⏳ Pending |
| 2 | Add adaptive weights | 5 min | ⏳ Pending |
| 3 | Modify MultiMethodMatcher | 10 min | ⏳ Pending |
| 4 | Update test_arena.py | 5 min | ⏳ Pending |
| 5 | Run baseline test | 5 min | ⏳ Pending |
| 6 | Run adaptive test | 5 min | ⏳ Pending |
| 7 | Analyze & document | 10 min | ⏳ Pending |

**Total Estimated Time**: ~50 minutes

---

## 🎯 Ready to Start?

Next action: Create `src/audio_utils.py` with SNR estimation function.

Shall I proceed? 🚀
