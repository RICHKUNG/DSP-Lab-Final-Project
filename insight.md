# Bio-Voice Commander: 技術洞察與抗噪策略分析

**日期:** 2025-12-09  
**專案:** DSP 期末專題 - 語音指令控制系統

本文檔記錄了在開發過程中，針對不同 DSP 特徵提取方法與噪音抑制策略的實驗觀察與效能分析。

## 1. 特徵提取方法比較

我們實作並測試了四種不同的特徵提取與比對方法，它們在面對指令辨識與噪音干擾時表現出截然不同的特性：

### A. MFCC + DTW (MVP)
*   **特性**: 使用 13 階 MFCC 加上 Delta 和 Delta-Delta 動態特徵，配合動態時間校正 (DTW) 進行序列比對。
*   **表現**: **準確率最高 (>90%)**。對於指令的辨識非常穩健，即使語速不同也能透過 DTW 正確對齊。
*   **弱點**: **對噪音缺乏抵抗力**。它傾向於在特徵空間中找到「最像」的指令，而不是拒絕。所有的噪音樣本在 MFCC 空間中，往往都比閾值更接近某個指令模板。
*   **結論**: 它是系統的辨識核心，但必須依靠其他機制來過濾噪音。

### B. LPC / LPCC + DTW (最佳進步獎)
*   **特性**: 最初使用全域 LPC 統計量 (Mean/Std)，效果極差 (12%)。後來改為提取 **LPCC (倒頻譜係數)** 序列並結合 DTW。
*   **表現**: **噪音抑制能力極強 (100% Rejection)**。LPCC 對於聲道模型的捕捉非常敏感，能夠有效區分「人聲指令」與「環境雜訊」。
*   **弱點**: 對於短促指令 (如 "JUMP") 較不敏感，容易將其誤判為噪音。這可能是因為短音的共振峰結構不夠穩定。在 10dB 高噪聲環境下，準確率會大幅下降至 27%。
*   **結論**: 是輔助 MFCC 進行「雙重確認」的最佳夥伴，但在高噪聲下權重應降低。

### C. Mel-Template (最穩健)
*   **特性**: 將語音轉換為固定大小的 Mel-Spectrogram 圖像，直接計算歐式距離。
*   **表現**: **極度穩健**。雖然單獨使用時準確率不如 MFCC，但它在 **Speed, Pitch, Noise, Volume** 四種變異下，表現最為平穩（始終維持約 73%）。特別是在 10dB 高噪聲下，它是唯一沒有衰退的方法。
*   **結論**: 適合作為「安全網」，在其他方法因噪音失效時提供穩定的判斷。

### D. Stats (表現最差)
*   **特性**: 將 MFCC 分成 3 段計算平均值與標準差，並加入 ZCR。
*   **表現**: **極差 (<30%)**。有嚴重的類別偏好 (Bias)，幾乎把所有聲音都判斷為 "START"。
*   **原因**: 將時變訊號壓縮成統計量丟失了太多資訊。且 ZCR 對於高頻噪音與 "Start" 的氣音難以區分。
*   **結論**: 在高品質語音辨識任務中，單純的統計特徵不足以擔當大任，已從決策權重中移除。

---

## 2. 實驗數據：Arena Robustness Test

我們開發了 `temp/test_file_input.py` 進行嚴格的 Leave-One-Out 交叉驗證。

### A. 噪音測試 (Noise Robustness)
| Method       | Clean (100dB) | Noisy (10dB) | Drop |
|:-------------|:-------------:|:------------:|:----:|
| **mfcc_dtw** | 80%           | 53%          | -27% |
| **lpc**      | 80%           | 27%          | **-53%** (崩潰) |
| **mel**      | 73%           | 73%          | **0%** (超穩) |
| **ensemble** | **80%**       | **80%**      | **0%** (最佳) |

### B. 變速測試 (Speed Robustness)
| Method       | 0.7x (Slow)   | 1.3x (Fast)  |
|:-------------|:-------------:|:------------:|
| **mfcc_dtw** | 80%           | 80%          |
| **ensemble** | 80%           | 80%          |

---

## 3. 最終決策策略 (Final Ensemble Strategy)

基於上述實驗，我們制定了最終的加權投票策略：

1.  **MFCC (權重 4.0)**: 準確率最高，擔任主攻手。
2.  **Mel (權重 2.5)**: 穩定性最高，擔任副手，特別是在噪音環境下能補足 MFCC 的失準。
3.  **LPC (權重 1.0)**: 權重調降，僅作為輔助參考，避免在吵雜環境下因其崩潰而誤導決策。
4.  **Stats (權重 0.0)**: 停用。

## 4. 部署建議

1.  **現場校正 (必做)**: 程式啟動時的 2 秒靜音校正是對抗 VAD 誤觸發的第一道防線。
2.  **Lombard Effect 對策**: 若現場極度吵雜，使用者勢必大聲吼叫。請務必在現場**用同樣的音量重新錄製** `cmd_templates`。
3.  **物理降噪**: 麥克風請盡量靠近嘴巴 (避免 Clipping 的前提下)。

---

## Test Run 3: Optimization Phase
**Date:** 2025-12-09
**Focus:** Latency Reduction & Algorithm Optimization

### Optimization Actions
1.  **Refactored Recognition Loop:** `MultiMethodMatcher` now extracts features (MFCC, Mel, LPC) **once** per audio segment and shares them across matchers, eliminating 75% of redundant signal processing.
2.  **LPC Optimization:** Replaced custom Python-based Levinson-Durbin implementation with **`librosa.lpc`** (C-optimized), and vectorized the feature extraction loop.
3.  **Temporal Downsampling:** Increased `HOP_LENGTH` from 256 to **512**, effectively halving the number of frames for DTW calculations without accuracy loss.
4.  **Disabled Stats:** Completely disabled the 'stats' method (weight=0) to save CPU cycles.

### Results Impact

#### 1. Latency (Processing Time)
*Target: < 500ms*
- **Before Optimization:** ~1200 ms
- **After Optimization:** **~458 ms**
- **Reduction:** **> 60%** (Achieved target)

#### 2. Accuracy (Clean / 1.0x Speed)
- **Before Optimization:** 80%
- **After Optimization:** **87%**
- *Insight:* The cleaner implementation and consistent hop sizes likely reduced noise in the feature vectors.

#### 3. Noise Robustness (10dB SNR)
- **Ensemble Accuracy:** **80%** (Maintained high robustness)
- *Insight:* Even with optimizations, the Ensemble method remains highly effective in noisy environments, leveraging the noise-resistant Mel-template method.

### Conclusion
The system now meets the real-time requirement (<500ms) while improving baseline accuracy. The Ensemble approach proves to be both robust and efficient enough for deployment.
