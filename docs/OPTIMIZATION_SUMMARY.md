# 優化成果總結

**日期:** 2025-12-09
**目標:** 在維持高準確率的前提下，提升系統速度

---

## 📊 最終成果

| 指標 | 原始版本 | 優化後 | 改善 |
|------|---------|--------|------|
| **延遲** | ~700ms | **217ms** | **3.2x 加速** ✅ |
| **整體準確率** | 80.3% | 80.0% | -0.3% (可接受) |
| **Clean 準確率** | 86.7% | 86.7% | 維持 ✅ |
| **10dB 準確率** | 60.0% | 60.0% | 維持 ✅ |
| **速度穩健性** | 80-87% | 80-87% | 維持 ✅ |

---

## 🔧 優化歷程

### Phase 1: FastLPCMatcher
**時間:** 2025-12-09 (前期)
**問題:** LPC DTW 匹配太慢 (480ms)

**解法:**
```python
class FastLPCMatcher:
    def _extract_features(self, audio):
        lpc = extract_lpc_features(processed)
        # Resize to fixed 30 frames
        lpc = zoom(lpc, (zoom_factor, 1), order=1)
        return lpc.flatten()  # Use Euclidean distance
```

**成果:**
- 延遲: 700ms → 330ms (2.1x)
- 準確率: 維持 100%

**記錄:** `exp_fast_1.md`

---

### Phase 2: DTW Radius 優化
**時間:** 2025-12-09 (後期)
**問題:** MFCC DTW 是新瓶頸 (330ms, 佔 88%)

**分析:**
```
MFCC matching (DTW):  330ms  88.1%  ========================================
LPC extraction:        21ms   5.7%  ==
LPC matching:          16ms   4.4%  ==
MFCC extraction:        4ms   1.0%
Mel extraction:         3ms   0.7%
```

**解法:**
```python
# src/config.py
DTW_RADIUS = 2  # 從預設 5 降至 2

# src/recognizers.py
def _compute_distance(self, feat1, feat2):
    if self.method == 'mfcc_dtw':
        return dtw_distance_normalized(feat1, feat2, radius=config.DTW_RADIUS)
```

**測試結果:**
| Radius | 延遲 | 加速比 |
|--------|------|--------|
| 5 (原始) | 330ms | 1.0x |
| 3 | 275ms | 1.2x |
| **2** | **217ms** | **1.5x** |

**成果:**
- 延遲: 330ms → 217ms (1.5x)
- 準確率: 80.3% → 80.0% (-0.3%)

**記錄:** `exp_fast_2.md`

---

## 📈 詳細比較

### 噪音穩健性
| SNR | 原始 (r=5) | 優化後 (r=2) | 差異 |
|-----|-----------|-------------|------|
| Clean (100dB) | 87% | 87% | 0 |
| 25dB | 73% | 73% | 0 |
| **20dB** | **73%** | **67%** | **-6%** ⚠️ |
| 15dB | 60% | 60% | 0 |
| 10dB | 60% | 60% | 0 |

**分析:**
- 20dB 有輕微下降 (73% → 67%)
- 高噪音環境 (10-15dB) 維持不變
- 整體仍可接受

### 速度/音高/音量穩健性
- **速度變化 (0.7x-1.3x):** 維持 80-87%
- **音高變化 (-2.5 ~ +2.5):** 維持 73-87%
- **音量變化 (0.3x-3.0x):** 維持 87%

---

## 💡 關鍵發現

### 1. LPC 不是瓶頸
FastLPCMatcher 已經將 LPC 從 480ms 降至 37ms，非常成功。

### 2. MFCC DTW 是主要瓶頸
佔總時間的 88%，必須優化。

### 3. DTW Radius 可以降低
從 5 降至 2，速度提升 1.5x，準確率幾乎不變。

### 4. Mel 方法很輕量
只需 3ms，但提供噪音穩健性，建議保留。

---

## 🎯 最佳配置

```python
# src/config.py
DTW_RADIUS = 2          # 速度優化
HOP_LENGTH = 512        # 已優化
THRESHOLD_MFCC_DTW = 140.0
THRESHOLD_MEL = 0.45
THRESHOLD_LPC = 80.0    # FastLPCMatcher 使用 100.0

# src/recognizers.py
# 使用 FastLPCMatcher (固定尺寸 + Euclidean)
# MFCC 使用 radius=2 DTW
```

---

## 📂 測試記錄

### Arena Test 結果
1. **Baseline (radius=5):** `record/arena_20251209_221658.json`
2. **Optimized (radius=2):** `record/arena_20251209_224402.json`

### 查看比對
```bash
python temp/view_history.py
> compare 1 2
```

---

## 🚀 進一步優化空間（未實作）

如果需要更快：

### Option 1: Radius = 1
- 預期延遲: ~140ms (2.4x 加速)
- 風險: 速度變化可能準確率下降

### Option 2: 自適應模式
```python
if mfcc_confidence > 0.85:
    return mfcc_result  # 快速路徑 ~150ms
else:
    return ensemble_result  # 完整路徑 ~217ms
```

### Option 3: 模板降採樣
- 每個指令只保留最佳 2-3 個模板
- 減少匹配次數

---

## ✅ 結論

**成功達成目標：**
- ✅ 延遲從 700ms 降至 217ms (3.2x 加速)
- ✅ 準確率維持 80% (僅下降 0.3%)
- ✅ 噪音穩健性基本維持
- ✅ 速度/音高/音量穩健性完全維持

**Trade-off:**
- 20dB 噪音準確率從 73% → 67% (可接受)

**建議:**
- 當前配置 (radius=2) 適合部署
- 如需更高噪音穩健性，可用 radius=3 (275ms, 73%)
- 如需極致速度，可試 radius=1 (需額外測試)

---

**最終配置已部署在:** `src/config.py`, `src/recognizers.py`
**測試結果已保存在:** `record/arena_20251209_224402.json`
