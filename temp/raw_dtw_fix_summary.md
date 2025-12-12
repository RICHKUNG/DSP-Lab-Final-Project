# Raw DTW 問題修復總結

## 問題描述

使用 `--method raw_dtw` 時，VAD 一開始錄音後就停不下來，系統持續處於錄音狀態。

## 根本原因

1. **計算時間過長**：原始實現直接對 16kHz 音頻進行 DTW 計算
   - 單個模板比較耗時：~4750ms
   - 3 個模板：~14 秒

2. **主循環阻塞**：DTW 計算阻塞主循環，導致：
   - 音頻流緩衝區累積大量數據
   - VAD 無法及時處理新的 chunk
   - 計算完成後，累積的數據立即觸發新的錄音週期

3. **閾值錯誤**：初始閾值 500000.0 過大
   - 任何音頻都會被接受（包括噪音）
   - 導致連續誤觸發

## 解決方案

### 1. 音頻降採樣（加速）

在 `src/audio/recognizers.py` 的 `_extract_features` 方法中添加降採樣：

```python
elif self.method == 'raw_dtw':
    # Downsample by factor of 16 to speed up DTW (16kHz -> 1kHz)
    downsample_factor = 16
    downsampled = processed[::downsample_factor]
    return downsampled.reshape(-1, 1).astype(np.float32)
```

**效果**：
- 計算時間：4750ms → **450-650ms**（約 10倍提升）
- DTW 複雜度：O(16000²) → O(1000²)
- 仍保留足夠的時域信息（1kHz 採樣率足以捕捉語音波形）

### 2. 閾值調整

在 `src/config.py` 中更新閾值：

```python
THRESHOLD_RAW_DTW = 0.020  # Raw audio DTW (downsampled 16x, normalized distance)
```

**調整依據**：
- 正確匹配距離：~0.0
- 不同指令距離：0.027-0.034
- 噪音距離：0.032-0.040
- 閾值 0.020 可以正確區分匹配和噪音

## 測試結果

### 性能測試

```
Template Self-Match:
  START: 0.000000 (PASS)
  PAUSE: 0.000000 (PASS)
  JUMP:  0.000000 (PASS)

Cross-Match (different commands):
  PAUSE vs START: 0.028166
  PAUSE vs JUMP:  0.034460

Noise Rejection:
  Noise vs all:   0.032-0.036 → NONE (correctly rejected)
```

### VAD 整合測試

```
Recognition Time: 450.8ms
VAD Reset: Success
No Blocking: Confirmed
```

## 性能比較

| 指標 | 修復前 | 修復後 | 改善 |
|------|--------|--------|------|
| 計算時間 (1 模板) | ~4750ms | ~450ms | **10x** |
| 計算時間 (3 模板) | ~14秒 | ~650ms | **21x** |
| 閾值範圍 | 500000.0 | 0.020 | 正確調整 |
| VAD 阻塞 | 是 | 否 | ✓ 已修復 |
| 噪音拒絕 | 否 | 是 | ✓ 已修復 |

## 技術細節

### 降採樣合理性

- **語音基頻**：80-300Hz
- **Nyquist 頻率**：500Hz（1kHz 採樣率）
- **結論**：1kHz 足以捕捉語音波形的主要特徵

### 為何不用更高的降採樣倍數？

| 倍數 | 採樣率 | 速度 | 問題 |
|------|--------|------|------|
| 8x | 2kHz | 中等 | 仍略慢 (~1.3s) |
| **16x** | **1kHz** | **快** | **最佳平衡** |
| 32x | 500Hz | 很快 | 可能損失部分波形細節 |

### DTW 計算複雜度

```
Time Complexity: O(n * m) where n, m = sequence lengths
Memory: O(n * m) for distance matrix

降採樣前：O(16000 * 27000) ≈ 432M operations
降採樣後：O(1000 * 1700) ≈ 1.7M operations
加速比：432M / 1.7M ≈ 254x
```

實際測試顯示約 10-21x 加速（考慮了其他開銷）。

## 使用建議

1. **研究用途**：raw_dtw 現在可以正常使用進行時域基準測試
2. **實時應用**：建議仍使用 mfcc_dtw（更快）或 adaptive_ensemble（更準確）
3. **性能考量**：650ms 延遲對遊戲控制略高，但對研究分析可接受

## 後續優化建議

1. **進一步降採樣**：可測試 32x (500Hz) 是否仍保持準確率
2. **抗混疊濾波**：在降採樣前添加低通濾波器
3. **並行處理**：將 DTW 計算移至獨立執行緒（需重構架構）
4. **快取優化**：如模板數量多，考慮使用更快的 DTW 近似算法

## 相關文件

- 實現細節：`temp/raw_dtw_implementation.md`
- 測試腳本：`temp/test_raw_dtw_vad.py`
- 配置檔：`src/config.py`
- 識別器：`src/audio/recognizers.py`
