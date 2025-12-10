# Bio-Voice Commander: Experimental Logs & Legacy Insights

此文件存檔了開發過程中的詳細實驗數據與早期洞察，避免在主文件更新時遺失。

---

## [New] Phase 8: Ensemble Strategy Evolution (2025-12-10)

*探索比單純加權平均 (Soft Voting) 更佳的集成策略。*

### 1. 實驗設計
*   **Baseline**: `Adaptive Ensemble` (Soft Voting) - 加權各方法的信心分數 (Distance based)。
*   **Challenger**: `Voting Ensemble` (Hard Voting) - 各方法 "投一票" (加權)，不看距離絕對值，只看排名。
    *   *原理*: 避免單一方法因距離異常 (Outlier) 而綁架整個決策。

### 2. 測試結果 (Arena Comparison)
| Scenario | Adaptive (Soft) | Voting (Hard) | Analysis |
|----------|-----------------|---------------|----------|
| **Pitch -2.5st** | 93% | **100%** | Hard Voting 修復了 `頝3.wav` 的誤判 |
| Noise 10dB | 93% | 93% | 平手 |
| Speed 1.3x | 93% | 93% | 平手 (皆在 `暫停4` 失敗) |
| Volume | 100% | 100% | 平手 |

### 3. 結論
*   **Hard Voting 勝出**: 在極端變調 (Pitch -2.5st) 情況下，Hard Voting 展現了更好的穩健性。
*   **機制更新**: 已在 `src/recognizers.py` 中實作 `recognize_voting` 方法，並支援信心分數計算 (`votes / total_weights`)。

---

## [New] Phase 7: RASTA-PLP Feasibility Study (2025-12-10)

*此階段驗證了 RASTA-PLP (Approximation) 特徵是否能進一步提升抗噪能力。*

### 1. 實驗設計
*   **方法**: 實作 `extract_rasta_plp`，在 Log Mel Spectrogram 上應用 RASTA 濾波器 ($H(z) \approx 0.1 z^4 \frac{2 + z^{-1} - z^{-3} - 2z^{-4}}{1 - 0.98z^{-1}}$)，再進行 DCT。
*   **目的**: 測試其是否能在 10dB 噪音下超越現有的 Adaptive Ensemble。

### 2. 測試結果 (Arena RASTA_PLP)
*   **Speed/Pitch/Volume**: 表現極佳 (98%+, 100%)，與 MFCC 相當。
*   **Noise Robustness**:
    *   25dB: 86%
    *   20dB: 93% (表現優異，單一特徵能達到此水準很強)
    *   15dB: 86%
    *   **10dB: 57%** (崩潰點)

### 3. 結論
*   RASTA-PLP 在中度噪音 (20dB) 下表現強勁，但在高噪音 (10dB) 下不如 Adaptive Ensemble (93%)。
*   **決策**: 保留程式碼作為備用特徵，但不加入預設 Ensemble，因為 Adaptive Ensemble 目前已能完美處理 20dB (100%) 和 10dB (93%) 的情況。

---

## [Archive] Phase 6: Extreme Robustness Optimization (2025-12-10)

*此階段目標是解決 `adaptive_ensemble` 在中度噪聲 (20-25dB) 和極端變速 (1.3x) 下的剩餘錯誤。*

### 1. 問題診斷
*   **Speed/Pitch**: `暫停4.wav` 在 1.1x/1.3x 速度下被誤判為 `START`。推測是 DTW 搜尋半徑過小，無法捕捉時間軸變形。
*   **Noise**: `開始` 指令在 25dB-15dB 區間偶爾被誤判。推測是 MFCC/LPC 在此區間權重過高，而 Mel 權重不足。

### 2. 優化行動
1.  **DTW Radius**: 從 `3` 增加到 `6`。
    *   *目的*: 增加對時間伸縮的容忍度。
    *   *代價*: 平均延遲從 ~160ms 增加到 ~270ms (仍可接受)。
2.  **Adaptive Weights**: 調整 "Moderate Noise" (15-30dB) 的權重分配。
    *   *舊*: `mfcc: 3.0, mel: 3.0, lpc: 1.0`
    *   *新*: `mfcc: 3.0, mel: 4.0, lpc: 0.5`
    *   *原理*: 降低對噪聲敏感的 LPC 依賴，提高對噪聲穩健的 Mel 依賴。
3.  **Mel Threshold**: 微調至 `0.50` (從 0.40 -> 0.45 -> 0.50 -> 0.55 測試後回退)。

### 3. 最終測試結果 (Arena Extreme & Mixed)
*   **Standard Arena**: 總體準確率 **97.9%**。
    *   **Noise**: 100dB, 25dB, 20dB 皆達到 **100%**。15dB, 10dB 維持 **93%**。
    *   **Speed/Pitch**: 大部分場景 100%，僅極端 pitch (+2.5st) 有少量誤判。
*   **Extreme Arena**:
    *   **0dB SNR**: **93% 準確率** (噪音與信號一樣大時仍能穩定工作)。
    *   **-5dB SNR**: 79% (系統極限)。
*   **Mixed Conditions**:
    *   **Indoor/Fast/Distant/Tired**: **100%**。
    *   **Stress Test (Combined distortions)**: **92.9%**。

### 結論
透過動態權重調整與參數微調，系統已達到極致穩健性。無需引入新的特徵提取方法 (如 RASTA-PLP) 即可滿足絕大多數應用場景。

---

## [Archive] 對抗噪音的策略演進 (From Early Insight)

*此章節記錄了開發過程中對抗噪音的五個演進階段。*

### 第一階段：靜態閾值 (Static Thresholds)
*   **做法**: 設定固定的距離門檻 (e.g., dist < 50)，超過就當作 `NONE`。
*   **問題**: 失敗。因為 VAD 切下來的噪音片段，有時候在特徵空間上離指令非常近 (False Positive)。若把門檻設太嚴，又會導致使用者稍微講不清楚就被拒絕。

### 第二階段：靜態噪音模板 (Static Noise Templates)
*   **做法**: 預先錄製一些「安靜」的檔案作為負樣本。
*   **問題**: 失敗。部署環境 (Demo 現場) 的背景音與開發環境完全不同。預錄的死寂錄音無法代表現場的空調聲或回音。

### 第三階段：動態環境校正 (Dynamic Calibration) - **成功關鍵**
*   **做法**: 程式啟動時，強制執行 2 秒鐘的「環境採樣」，錄製當下的背景音並生成 5-6 個 `noise_templates`。
*   **原理**: 讓系統記住「現在這個房間的安靜聲音長什麼樣」。
*   **效果**: 大幅提升了 VAD 誤觸發時的防禦力。當風吹草動觸發 VAD 時，辨識器發現這段聲音跟「環境模板」的距離比跟「指令模板」更近，因此果斷判定為 `NOISE`。

### 第四階段：人聲垃圾桶 (Human Garbage Class)
*   **做法**: 針對 VAD 無法過濾的「人聲噪音」(笑聲、咳嗽、嘆氣)，建立專門的負樣本類別。
*   **原理**: 這些聲音有能量也有共振峰，VAD 擋不住，MFCC 也會覺得像語音。唯一的解法是明確告訴電腦「這些特定的聲音是垃圾」。
*   **效果**: 有效解決了 "Bruh", "Uhh" 等人聲干擾。

### 第五階段：加權整合決策 (Weighted Ensemble)
*   **做法**: 不再一人一票。
    *   **MFCC (權重 4.0)**: 負責主要的指令辨識。
    *   **LPC (權重 1.5)**: 負責檢查聲道特徵是否異常 (噪音檢測)。
    *   **Mel (權重 2.0)**: 負責保守過濾。
    *   **Stats (權重 0.0)**: 停用。
*   **邏輯**: 
    1. 計算各方法的加權信心分數。
    2. 加入 **Mel 否決權**：如果 Mel 強烈認為是噪音，且 MFCC 信心不足，則強制判定為噪音。

---

## [Raw Data] Arena Test Run 2 (Detailed Logs)

*此區段記錄了 `temp/test_file_input.py` 的詳細輸出，包含每個檔案在不同變異下的辨識結果。*

**Date:** 2025-12-09
**Tool:** `temp/test_file_input.py`

### 1. Speed Robustness (0.7x ~ 1.3x)
```text
Method       |    0.7x |    0.9x |      1x |    1.1x |    1.3x |
----------------------------------------------------------------
mfcc_dtw     |     80% |     80% |     80% |     80% |     80% |
stats        |     53% |     53% |     60% |     53% |     53% |
mel          |     73% |     73% |     73% |     73% |     73% |
lpc          |     80% |     80% |     80% |     80% |     73% |
ensemble     |     80% |     80% |     80% |     80% |     80% |
```

### 2. Pitch Robustness (-2.5st ~ +2.5st)
```text
Method       |  -2.5st |  -1.0st |  +0.0st |  +1.0st |  +2.5st |
----------------------------------------------------------------
mfcc_dtw     |     80% |     87% |     80% |     80% |     80% |
stats        |     53% |     53% |     60% |     60% |     53% |
mel          |     67% |     73% |     73% |     73% |     73% |
lpc          |     67% |     67% |     80% |     80% |     80% |
ensemble     |     80% |     87% |     80% |     80% |     80% |
```

### 3. Noise Robustness (100dB ~ 10dB SNR)
*Note the performance drop of LPC in high noise (10dB).*
```text
Method       |   100dB |    25dB |    20dB |    15dB |    10dB |
----------------------------------------------------------------
mfcc_dtw     |     80% |     73% |     67% |     60% |     67% |
stats        |     60% |     67% |     53% |     47% |     40% |
mel          |     73% |     73% |     73% |     73% |     73% |
lpc          |     80% |     47% |     40% |     27% |     27% |
ensemble     |     80% |     87% |     80% |     73% |     80% |
```

### 4. Volume Robustness (0.3x ~ 3.0x)
```text
Method       |    0.3x |    0.6x |      1x |    1.5x |      3x |
----------------------------------------------------------------
mfcc_dtw     |     80% |     80% |     80% |     80% |     80% |
stats        |     60% |     60% |     60% |     60% |     60% |
mel          |     73% |     73% |     73% |     73% |     73% |
lpc          |     80% |     80% |     80% |     80% |     80% |
ensemble     |     80% |     80% |     80% |     80% |     80% |
```

### Detailed File Analysis (Sample)

**Outliers Identified:**
- `暫停.wav` (PAUSE): Consistently misclassified as START across multiple tests.
- `跳.wav` (JUMP): Consistently misclassified as START.
- `開始.wav` (START): Often misclassified as PAUSE or JUMP.

*Reasoning: The base templates (without numbers) might have been recorded in a different session or with different microphone settings compared to the numbered templates (1-4), causing a domain shift.*

---

## [Archive] QA Test Reports

Previous QA test logs are preserved in the `record/` directory:
- `record/test_20251209_184323.md`: Initial Baseline
- `record/test_20251209_190753.md`: After Noise Templates Added
- `record/test_20251209_191740.md`: After LPC Upgrade & Weight Tuning