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
- **自動偵測**: 系統會優先尋找 Arduino 裝置。
- **模擬模式**: 若找不到硬體，會自動切換至模擬模式，產生約 75 BPM 的虛擬心跳訊號，確保遊戲可玩。

## 🏗️ 系統架構

- **EventBus**: 中央事件匯流排，解耦各個模組 (`src/event_bus.py`)。
- **Audio Module**: 負責 VAD、特徵提取與語音辨識 (`src/audio/`)。
- **ECG Module**: 負責 Serial 通訊、訊號濾波與 R-R 峰值偵測 (`src/ecg/`)。
- **Game Server**: Flask + SocketIO 網頁伺服器 (`src/game/`)。

## 🧪 測試語音模組

若要單獨測試語音辨識功能，可以使用以下腳本：

1.  **即時語音測試 (Live)**:
    ```bash
    # 測試麥克風輸入與辨識結果
    python tests/test_live.py
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

## 📖 開發日誌

詳細的優化歷程與實驗數據請參閱 [`docs/exp_log.md`](docs/exp_log.md)。
未來實驗規劃請參閱 [`docs/EXPERIMENT_ROADMAP.md`](docs/EXPERIMENT_ROADMAP.md)。
