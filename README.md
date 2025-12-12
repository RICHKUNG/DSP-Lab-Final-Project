# Bio-Voice Commander & ECG Pulse Runner

生物訊號控制系統 - DSP 期末專題

## 🎯 專案目標

1.  **整合 ECG 與語音控制**: 利用心電圖 (ECG) 訊號生成遊戲障礙物，並用語音指令控制角色。
2.  **語音指令控制**: 支援 5 個指令：`START`, `PAUSE`, `JUMP`, `MAGNET`, `INVERT`。
3.  **Speaker-independent**: 任何人都能使用，不限於訓練者。
4.  **極致穩健性**: 抗 0dB 噪音、1.7x 變速、±5 半音變調。

## 📊 系統效能 (2025-12-10 Final)

我們提供多種辨識策略，預設使用 **mfcc_dtw** 以確保在一般環境下的穩定性與反應速度。若您處於複雜噪音環境，可切換至 **Adaptive Ensemble** 模式。

| 指標 | mfcc_dtw (Default) | Adaptive Ensemble (Optional) | 狀態 |
| :--- | :--- | :--- | :--- |
| **整體準確率** | **~94%** | **97.9%** | 🏆 極佳 |
| **乾淨環境** | **100%** | **100%** | ✅ 完美 |
| **噪音 20dB** | **90%** | **100%** | ✅ 穩定 |
| **噪音 10dB** | **64%** | **93%** | 🚀 突破性表現 |
| **平均延遲** | **~160ms** | ~270ms | ⚡ 極速 |

## 🚀 快速開始

### 安裝

```bash
# 建立 conda 環境
conda create -n dspfp python=3.10 -y
conda activate dspfp

# 安裝套件
pip install -r requirements.txt
```

### 啟動完整系統

```bash
# 自動偵測 ECG (若無則自動啟用模擬模式) 並開啟遊戲
python app.py
```

### 使用說明

系統啟動後會自動開啟瀏覽器 (http://localhost:5000)。

#### 🎮 遊戲控制 (Controls)

| 動作 | 語音指令 (Voice) | 鍵盤 (Keyboard) | 說明 |
| :--- | :--- | :--- | :--- |
| **開始** | "開始" (START) | - | 開始遊戲 |
| **跳躍** | "跳" (JUMP) | **[↑] 上箭頭** | 跳過障礙物 |
| **暫停** | "暫停" (PAUSE) | **[Space] 空白鍵** | 暫停/繼續遊戲 |

#### ❤️ ECG 模組

**連接與動態 Fallback**
- **自動偵測**: 系統會優先尋找 Arduino 裝置並使用真實 ECG 訊號。
- **動態切換 Fallback**: 智能監控並自動切換模式：
  - **切換到 Fallback**: 當發生以下情況時
    - 找不到 ECG 硬體
    - BPM 低於閾值 (預設 -10 BPM，幾乎不會觸發)
    - 超過 5 秒沒有收到訊號
  - **自動恢復真實訊號**: 每 10 秒重試連接真實 ECG
  - **無縫切換**: 自動在真實訊號和假訊號間切換，無需手動干預
- **假訊號模式**: 產生穩定的 75 BPM 虛擬心跳訊號，確保遊戲可玩。
- **參數調整**: 可透過命令列參數自訂行為：
  ```bash
  # 基本使用 (使用預設值)
  python app.py

  # 自訂切換閾值與重試間隔
  python app.py --bpm-threshold 30 --bpm-recovery 50 --retry-interval 15

  # 調整假訊號 BPM
  python app.py --fallback-bpm 80
  ```

**訊號處理流程 (ecg_reader.py - Pan-Tompkins Algorithm)**

系統使用 `src/ecg/ecg_reader.py` 中的 `ECGProcessor` 進行真實 ECG 處理：

1. **Notch Filter (60 Hz, Q=20)**: IIR notch 濾波器，移除電源線干擾
2. **Low-pass Filter (40 Hz)**: 2 階 Butterworth 濾波器，去除高頻雜訊
3. **MA1 (8-point)**: 移動平均平滑
4. **Derivative**: 差分運算，強化 QRS 斜率
5. **Squaring**: 平方運算，放大高頻成分
6. **MWI (150ms)**: 移動窗積分

**R 波峰值偵測**
- **動態閾值**: 每 50 個樣本根據最近 1 秒的 MWI 最大值更新 (0.5 × max, 下限 20)
- **Refractory Period**: 250ms，避免 T 波誤判
- **搜尋窗口**: 在原始訊號中回推 100ms 找到真實 R 波峰值
- **基線驗證**: R 波振幅必須 > 訊號平均值 + 20
- **BPM 計算**: 基於最近 5 個 R-R 間隔的平均值 (40-150 BPM 有效範圍)

## 🏗️ 系統架構

- **EventBus**: 中央事件匯流排，解耦各個模組 (`src/event_bus.py`)。
- **Audio Module**: 負責 VAD、特徵提取與語音辨識 (`src/audio/`)。
- **ECG Module**: 負責 Serial 通訊、訊號濾波與 R-R 峰值偵測 (`src/ecg/`)。
- **Game Server**: Flask + SocketIO 網頁伺服器 (`src/game/`)。

## 🎤 語音辨識方法

系統支援多種辨識方法，各有不同的特性與適用場景：

| 方法 | 特徵提取 | DTW | 速度 | 準確率 | 適用場景 |
| :--- | :--- | :---: | :--- | :--- | :--- |
| **mfcc_dtw** | MFCC (13 維) | ✓ | 極快 (~160ms) | ~94% | 預設模式，適合一般環境 |
| **raw_dtw** | 無 (降採樣 16x) | ✓ | 中慢 (~650ms) | 待測試 | 研究用途，時域基準比較 |
| **ensemble** | MFCC + Mel + LPC | ✓ | 中等 | ~95% | 固定權重組合 |
| **adaptive_ensemble** | MFCC + Mel + LPC | ✓ | 中等 (~270ms) | 97.9% | 高準確度，SNR 自適應 |

### 方法說明

1. **mfcc_dtw** (預設):
   - 使用 MFCC 特徵 + DTW 距離
   - 速度最快，穩定性高
   - 適合大多數使用場景

2. **raw_dtw** (時域 DTW):
   - 直接比較原始音訊波形（降採樣 16x 至 1kHz）
   - 不進行特徵提取 (MFCC, Mel, LPC 等)
   - 適用於研究與基準測試
   - 處理時間約 650ms（3 個模板）
   - 提供最原始的時域波形比對

3. **ensemble**:
   - 結合多種特徵方法 (MFCC, Mel, LPC)
   - 使用固定權重投票
   - 平衡速度與準確率

4. **adaptive_ensemble**:
   - 根據音訊 SNR 動態調整各方法權重
   - 高噪音環境下自動提升 Mel 特徵權重
   - 最高準確率，適合複雜環境

## 🧪 測試語音模組

若要單獨測試語音辨識功能，可以使用以下腳本：

1.  **即時語音測試 (Live)**:
    ```bash
    # 測試麥克風輸入與辨識結果 (只使用原始模板)
    python tests/test_live.py

    # 包含增強模板進行測試
    python tests/test_live.py --include-augmented

    # 只使用增強模板測試 (評估增強品質)
    python tests/test_live.py --augmented-only

    # 指定辨識方法
    python tests/test_live.py --method mfcc_dtw  # 快速模式 (預設)
    python tests/test_live.py --method raw_dtw  # 時域 DTW (僅比較原始音訊)
    python tests/test_live.py --method adaptive_ensemble  # 高準確度模式
    ```

2.  **檔案回放測試**:
    ```bash
    # 測試特定音訊檔
    python app.py --test path/to/audio.wav
    ```

3.  **Arena 基準測試**:
    ```bash
    # 執行完整的效能評估 (預設 mfcc_dtw)
    python tests/test_arena.py --mode mfcc_dtw
    
    # 或測試高準度的 adaptive_ensemble
    python tests/test_arena.py --mode adaptive_ensemble
    ```

## 🔊 音訊模板資料增強

為提升系統對不同語速、音調與噪音環境的穩健性，我們提供了音訊資料增強工具。該工具會對原始語音模板進行多種變換，產生更豐富的訓練資料。

### 使用方法

```bash
# 預覽模式：查看將產生的檔案，不實際寫入
python temp/augment_templates.py --dry-run

# 執行模式：實際產生增強檔案
python temp/augment_templates.py --execute
```

### 增強策略

每個原始模板會產生 **6 個增強版本**，套用以下變換：

| 編號 | 增強類型 | 參數 | 說明 |
| :---: | :--- | :--- | :--- |
| 1 | 速度調整 | 0.85x | 模擬較慢的說話速度 |
| 2 | 速度調整 | 1.15x | 模擬較快的說話速度 |
| 3 | 音高偏移 | -1.5 半音 | 模擬較低的音調 |
| 4 | 音高偏移 | +1.5 半音 | 模擬較高的音調 |
| 5 | 噪音添加 | SNR 20dB | 中度背景噪音 |
| 6 | 組合變換 | 速度 1.0x + 音高 +1.0st + SNR 25dB | 輕微組合變換 |

### 輸出位置

增強檔案會儲存在 `cmd_templates/augmented/` 目錄下，檔名格式為：

```
{原檔名}_aug{編號}_{增強描述}.wav
```

例如：
- `開始_aug1_speed0.85x.wav`
- `跳_aug3_pitch-1.5st.wav`
- `暫停_aug6_pitch+1.0st_speed1.00x_snr25db.wav`

### 實作細節

增強方法參考 `tests/test_arena.py` 的測試基準：

- **速度調整**: 使用 `librosa.effects.time_stretch()`
- **音高偏移**: 使用 `librosa.effects.pitch_shift()`
- **噪音添加**: 根據 SNR 公式添加高斯白噪音

## ⚙️ 關鍵參數調整 (src/config.py)

如需自行微調，關注以下參數：

```python
# DTW 搜索半徑 (越大越能容忍變速，但越慢)
DTW_RADIUS = 6 

# 辨識閾值 (越小越嚴格)
THRESHOLD_MEL = 0.50
THRESHOLD_MFCC_DTW = 140.0

# VAD 閾值 (環境噪音較大時可調高)
VAD_ENERGY_THRESHOLD_MULT_LOW = 2.0
```

## 🔧 ECG 訊號處理技術細節

**Filter Initialization**
- 所有濾波器使用 `lfilter_zi` 初始化狀態向量為零，確保濾波器穩定啟動
- Notch 和 Low-pass 濾波器使用 IIR 設計，需要正確的初始狀態

**Peak Detection Algorithm**
- 三點局部極大值檢測：確保當前點大於前後兩點
- 動態閾值：每 50 個樣本根據最近 1 秒的 MWI 最大值更新
- Refractory Period：250ms 內不重複偵測，避免 T 波誤判
- 搜尋窗口：在原始濾波訊號中回推 100ms 找到真實 R 波振幅
- 基線驗證：R 波必須高於訊號平均值 20 以上

**BPM Calculation**
- 基於最近 5 個 R-R 間隔的平均值
- 有效範圍：40-150 BPM (0.4-1.5 秒的 R-R 間隔)
- 過濾異常值以提高準確度

## 📖 開發日誌

詳細的優化歷程與實驗數據請參閱 [`docs/exp_log.md`](docs/exp_log.md)。
未來實驗規劃請參閱 [`docs/EXPERIMENT_ROADMAP.md`](docs/EXPERIMENT_ROADMAP.md)。
