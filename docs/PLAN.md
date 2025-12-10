# Bio-Voice Commander – Audio Module Implementation Plan v2

## 0. 目標與設計哲學

### 0.1 專案目標（更新版）

1. **語音指令控制跑酷遊戲**  
   - 支援至少 5 個指令：`START`, `PAUSE`, `JUMP`, `MAGNET`, `INVERT`。
   - 延遲：從「說完指令」到遊戲收到 command ≤ 300 ms（在一般筆電上）。

2. **「任何人都能玩」的 speaker-independent 目標**
   - 不只訓練時的組員，其他同學/老師也能用自然語速下達指令。
   - 在「沒看過聲音的人」上仍能維持：
     - 單一指令 accuracy ≥ 80%（安靜環境）
     - 語速 / 語調差異不會讓系統完全失效。

3. **多種 DSP 方法的可行性探討**
   - 實作並比較至少 4 種方法：
     1. MFCC + DTW（baseline）
     2. 分段統計特徵（mean/std zonal coding）
     3. Mel-spectrogram 縮放模板
     4. LPC / Formant Fingerprint
   - 對每種方法從「準確度、穩定度、效能」三面向評估可行性。

### 0.2 成功條件摘要

系統被視為「成功」需滿足：

- **即時性**：平均語音處理延遲 < 150 ms，整體控制延遲（包含 VAD 等待） ≤ 300 ms。
- **準確度（已見 speaker）**：
  - 組員 3 人在安靜環境下，每個指令 accuracy ≥ 95%。
- **準確度（未見 speaker）**：
  - 至少 5 名未參與錄製模板的測試者，整體 accuracy ≥ 80%。
- **穩定度（變速/變調/加噪）**：
  - 在可接受的變速（±20%）、變調（±4 semitone）、SNR ≥ 10dB 下，accuracy 下降不超過 15%。

---

## 1. 系統架構概述

1. **I/O & Buffer 層**
   - 使用 PyAudio 非阻塞串流讀取麥克風。
   - 採用 ring buffer（約 0.5s）提供 pre-roll，避免 VAD 切到一半。
   - 以 thread-safe queue 將偵測到的語音 segment 傳給辨識核心。

2. **VAD Control 層**
   - 狀態機：`SILENCE → RECORDING → PROCESSING → SILENCE`。
   - 使用短期能量 + 零交越率判斷語音段落，並動態調整 threshold：
     - 啟動前 1–2 秒估計背景 RMS，作為 baseline。
     - threshold 維持在 [baseline * a, baseline * b] 範圍內（避免被長噪音拉高）。
   - 語音段限制：
     - 長度 < 200 ms 視為噪聲，直接丟棄。
     - 長度 > 1.5 s 強制切斷，以免錄進整段講話。

3. **DSP Recognition 核心（多路線）**
   - 對每一段 VAD 切出的語音，同步計算 4 種特徵/分數：
     1. MFCC+DTW 距離
     2. 分段統計向量距離
     3. Mel-template L2/cosine 距離
     4. LPC / Formant Fingerprint 距離
   - 每個方法各自選出最佳指令與距離，並具備獨立 threshold。
   - 實驗時可：
     - 單獨啟用某一種方法。
     - 未來視情況設計簡單 voting / fusion 規則。

4. **Command Decision & Game Integration**
   - 若某方法的最佳距離 < 其 `MATCH_THRESHOLD`，輸出對應指令 token；否則輸出 `NONE`（不動作）。
   - 在 demo/mode 設定中可選：
     - 單一方法模式（例如「只用 MFCC+DTW」）。
     - 比較模式（同時 log 多方法決策，但實際只用一種跟遊戲互動）。
   - 遊戲主執行緒從 command queue 取出 token，觸發角色動作或場景事件。

---

## 2. 語音辨識方法規劃

### 2.1 共通資料流與模板組織

- 指令集合：`{START, PAUSE, JUMP, MAGNET, INVERT}`。
- 每個指令收集：
  - 至少 6–8 位 speaker（含組員與其他同學）。
  - 每人每個指令 8–10 次。
- 檔案結構（示意）：
  - `data/raw/<speaker>/<command>_<take>.wav`
  - 對應的特徵快取：
    - `data/features/mfcc/...`
    - `data/features/stats/...`
    - `data/features/mel/...`
    - `data/features/lpc/...`

所有方法共用同一批 VAD 切過的語音片段，以便公平比較。

---

### 2.2 方案1：MFCC + DTW（Baseline）

- 前處理：
  - 16kHz, mono；去直流、pre-emphasis、RMS normalization。
- 特徵：
  - `n_mfcc = 13`, `n_fft = 1024`, `hop_length = 256`。
  - 加 delta, delta-delta；可做 cepstral mean normalization。
- 比對：
  - fastdtw 或自寫 DTW（Sakoe-Chiba band = ±3–5 frame）。
  - 距離採 L2。
- 決策：
  - 每個指令有多個 template；對輸入計算到所有 template 的 DTW 距離。
  - 取最小距離作為該指令分數；再取所有指令中的最小者為預測。
  - 若距離 > `TH_MFCC` 則視為 `NONE`。

---

### 2.3 方案2：分段統計特徵

- 流程：
  - 將 MFCC 序列在時間軸切為固定 3 等份（或依長度四捨五入）。
  - 每一段計算：
    - 每個 MFCC 維度的 mean, std。
  - 串接成一個長向量（維度 = `num_segment * num_coeff * 2`）。
- 比對：
  - Weighted Euclidean（可對低階 MFCC 權重較高）。
- 優點：
  - 特徵維度固定，計算非常快。
- 缺點：
  - 對於嚴重的語速變化可能較不穩。

---

### 2.4 方案3：Mel-spectrogram 縮放模板

- 特徵：
  - `n_mels = 128`, `hop_length = 256`, `fmin = 80`, `fmax = 7600`。
  - 對 power 做 `log1p`。
- 尺寸對齊：
  - 將時間軸縮放到固定長度（例如 50 frame）：
    - 使用 `scipy.ndimage.zoom` 等函式。
- 比對：
  - 對齊後的 128×50 矩陣做 L2 或 cosine 距離。
- 特性：
  - 對中小幅度語速變化、pitch shift 通常有不錯的穩定度。
  - 適合在 augmentation 測試中對比 MFCC/LPC 的差異。

---

### 2.5 方案4：LPC / Formant Fingerprint

- 前處理：
  - 16kHz, mono；pre-emphasis `α ≈ 0.97`。
  - frame：25ms，hop：10ms，Hamming window。
- LPC 參數：
  - order：10–14（實驗時可比較 10/12/14）。
- 特徵設計（兩種 route，可視時間都做）：

  **Route A：LPC 係數向量**
  - 每一 frame 計算 LPC 係數 `a_1 ... a_p`。
  - 針對整段語音計算：
    - 每一係數的 mean / std
    - 或使用更穩定的轉換（如 LAR）後再取 mean/std。
  - 得到固定維度的指令 fingerprint。

  **Route B：Formant 頻率向量**
  - 從 LPC 多項式根找出複數共軛根，轉成抗共振頻率。
  - 擷取前 2–3 個 formant（F1, F2, F3），並在整段上取中位數/均值。
  - 不同指令會呈現不同的 formant pattern。

- 比對：
  - 對 LPC 或 formant 向量使用 L2 / Mahalanobis distance。
  - 或將 frame-level 向量沿時間排列後使用 DTW（LPC-DTW）。

- 優缺點預期：
  - Idle CPU usage 極低，適合作為「輕量路線」。
  - 對於 pitch shift（±幾個 semitone）理論上比 MFCC 更穩定。
  - 但對強噪音或 channel effect 需仰賴良好前處理。

---

## 3. VAD 與錯誤保護機制

1. **背景量測**
   - 啟動時先錄 1–2 秒，估計背景 RMS 與 ZCR，作為 baseline。
2. **動態 threshold 限制**
   - energy threshold 在 `[baseline * a, baseline * b]` 內滑動（例如 a=1.5, b=5）。
3. **片段長度限制**
   - `< 200ms`：視為噪聲。
   - `> 1.5s`：強制切斷。
4. **錯誤時的行為**
   - 若所有方法的距離都 > 各自 threshold → 輸出 `NONE`，遊戲不做任何動作。
   - 絕不使用「猜猜看」的 fallback 觸發高風險指令（如 INVERT）。
5. **Log / Debug**
   - 對每一片段記錄：
     - 語音長度、peak energy
     - 四種方法的 top-1 指令與距離
   - 方便後續做錯誤分析與門檻調整。

---

## 4. 測試與評估計畫（真人 + Augmentation）

### 4.1 資料收集

1. **模板資料集（Template Set）**
   - Speaker：至少 6–8 人（含組員與幾位同學）。
   - 每人每個指令 8–10 次。
   - 用於訓練 template（四種方法共用）。

2. **測試資料集（Test Set – Unseen Speakers）**
   - 額外找 5–10 名「未參與模板錄製」的測試者。
   - 每人每個指令 5 次。
   - 用於 speaker-independent 評估。

---

### 4.2 Augmentation 穩定度測試

針對幾位 template speaker 的乾淨錄音，做下列轉換（用 `librosa` 或其他 DSP 工具）：

1. **變速 (time-stretch)**
   - rate ∈ {0.8, 0.9, 1.0, 1.1, 1.2}
2. **變調 (pitch-shift)**
   - semitone ∈ {-4, -2, 0, +2, +4}
3. **加噪音**
   - 加白噪或環境噪音
   - SNR ∈ {20dB, 10dB, 5dB}
4. **頻帶扭曲 / EQ**
   - 模擬手機/筆電麥克風（例如削掉低於 300Hz、或高於 4kHz）。

對於每種方法（MFCC+DTW、Stats、Mel、LPC），計算在各種條件組合下的 accuracy，畫出：

- 語速 vs accuracy 曲線
- pitch shift vs accuracy 曲線
- SNR vs accuracy 曲線

---

### 4.3 評估指標

1. **分類指標**
   - Overall accuracy
   - per-command accuracy
   - confusion matrix（可視化混淆情況）
2. **speaker-independent 指標**
   - leave-one-speaker-out / 未見 speaker 的平均 accuracy
3. **即時性指標**
   - 整體處理時間（從 VAD 結束到 command 推送）的平均與標準差。
4. **穩定度指標**
   - 在各 augmentation 條件下 accuracy 的變化量（相對乾淨條件）。

---

## 5. 風險與預期結果

1. **風險**
   - 真正做到「任何人都能玩」在少量資料下有挑戰，  
     但透過多 speaker template + Augmentation，可做到合理程度的泛化。
   - LPC/LPC-formant 在強噪音下可能不穩，需要仔細前處理。

2. **預期結果**
   - MFCC+DTW：整體表現最穩，作為主要 demo 路線。
   - Mel-template：對語速變化與頻帶扭曲可能比 MFCC/LPC 更穩。
   - Stats：效能最佳，用於輕量模式或作為對照組。
   - LPC/Formant：運算最快，對 pitch 變化相對穩定，適合在報告中放進「方法比較」章節。

3. **報告亮點**
   - 系統實際 demo：不同同學/老師上台說指令，遊戲即時反應。
   - 分析四種方法在「未見 speaker」與「變速/變調/噪音」下的表現差異，  
     實際回答「哪些 DSP 方法對於做 speaker-independent command 更有優勢？」這個 research question。
