# ECG Pulse Runner - 整合系統說明

**DSP 期末專案 - 心電圖跑酷遊戲**

整合語音辨識 + ECG 訊號處理 + 網頁遊戲的即時互動系統

---

## 🎯 系統架構

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ VoiceControl │     │  ECGManager  │     │  GameServer  │
│  (語音辨識)   │     │  (心電訊號)   │     │  (網頁遊戲)   │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                    │
       │   publish events   │   publish events   │   subscribe
       └────────────────────┼────────────────────┘
                            ▼
                      ┌──────────┐
                      │ EventBus │
                      └──────────┘
                            │
                            │ emit via SocketIO
                            ▼
                      ┌──────────┐
                      │ Browser  │
                      │  (遊戲)   │
                      └──────────┘
```

---

## 🚀 快速開始

### 1. 環境設定

```bash
# 使用 conda 環境
conda env create -f dspfp_env.yml
conda activate dspfp

# 或使用 pip
pip install -r requirements.txt
```

### 2. 啟動系統

```bash
# 完整系統（ECG + 語音 + 遊戲）
python app.py

# 測試模式（不使用 ECG）
python app.py --no-ecg

# 測試模式（不使用語音）
python app.py --no-voice

# 指定 ECG Port
python app.py --ecg-port COM3

# 指定語音辨識方法
python app.py --voice-method mfcc_dtw    # 最快 (~160ms)
python app.py --voice-method adaptive_ensemble  # 最準 (97.9%)

# 自訂網頁埠號
python app.py --web-port 8080
```

### 3. 開啟遊戲

瀏覽器訪問: `http://localhost:5000`

---

## 🎮 遊戲控制

### 語音指令

- **開始** - 開始遊戲
- **暫停** - 暫停/繼續
- **跳** - 角色跳躍

### 鍵盤控制（備用）

- **↑ (上箭頭)** - 跳躍
- **Space** - 暫停/繼續

### ECG 訊號

- R-R 峰值自動生成障礙物
- BPM 顯示在遊戲畫面上方

---

## 📁 專案結構

```
C:\Users\user\Desktop\DSPLab\Final/
├── app.py                      # 主程式入口
├── requirements.txt            # Python 套件
├── dspfp_env.yml              # Conda 環境
├── great_merge.md              # 整合進度追蹤
│
├── src/                        # 原始碼
│   ├── event_bus.py           # 事件匯流排
│   │
│   ├── audio/                  # 語音模組
│   │   ├── __init__.py
│   │   ├── controller.py      # VoiceController
│   │   ├── io.py              # 音訊 I/O
│   │   ├── vad.py             # 語音活動檢測
│   │   ├── features.py        # 特徵提取
│   │   └── recognizers.py     # 辨識引擎
│   │
│   ├── ecg/                    # ECG 模組
│   │   ├── __init__.py
│   │   └── manager.py         # ECGManager
│   │
│   └── game/                   # 遊戲模組
│       ├── __init__.py
│       ├── server.py          # Flask + SocketIO
│       └── templates/
│           └── index.html     # 遊戲前端
│
├── cmd_templates/              # 語音指令模板
├── tests/                      # 測試檔案
└── docs/                       # 文件
```

---

## 🔧 模組說明

### 1. EventBus（事件匯流排）

- **功能**: 執行緒安全的 pub/sub 事件系統
- **位置**: `src/event_bus.py`
- **事件類型**:
  - `ECG_PEAK` - R 波峰值偵測
  - `ECG_BPM_UPDATE` - BPM 更新
  - `VOICE_COMMAND` - 語音指令辨識
  - `VOICE_NOISE` - 噪音偵測
  - `SYSTEM_SHUTDOWN` - 系統關閉

### 2. VoiceController（語音控制器）

- **功能**: 整合音訊輸入、VAD、特徵提取、辨識
- **位置**: `src/audio/controller.py`
- **辨識方法**:
  - `mfcc_dtw` - 僅 MFCC（預設，最快 ~160ms）
  - `ensemble` - 固定權重 Ensemble
  - `adaptive_ensemble` - SNR 自適應（最準 97.9%，需環境校準）
- **準確率**: 97.9% (Adaptive Ensemble)
- **支援指令**: START, PAUSE, JUMP

### 3. ECGManager（ECG 管理器）

- **功能**: Serial 通訊、濾波、R-R 峰值偵測、BPM 計算
- **位置**: `src/ecg/manager.py`
- **濾波鏈**: MA → 差分 → 平方 → MWI
- **特色**:
  - 自動偵測 COM Port
  - Refractory Period (250ms)
  - 動態閾值調整
  - R-R 間隔歷史平均

### 4. GameServer（遊戲伺服器）

- **功能**: Flask 網頁伺服器 + SocketIO 即時通訊
- **位置**: `src/game/server.py`
- **事件轉發**:
  - `ECG_PEAK` → `spawn_obstacle`
  - `ECG_BPM_UPDATE` → `bpm_update`
  - `VOICE_COMMAND` → `player_action`

---

## 📊 效能指標

| 模組 | 目標 | 實測 | 狀態 |
|------|------|------|------|
| ECG 濾波 | <1ms | - | 待測 |
| 語音辨識 (MFCC) | <200ms | ~160ms | ✅ |
| 語音辨識 (Ensemble) | <300ms | ~270ms | ✅ |
| EventBus | <1ms | <10ms | ✅ |
| 端對端 | <500ms | - | 待測 |

---

## 🔨 開發工具

### 執行測試

```bash
# 延遲基準測試（建立後）
python tests/bench_latency.py

# 語音模組測試
python tests/test_voice.py

# ECG 模組測試（需要硬體）
python tests/test_ecg.py
```

### 查看進度

查看 `great_merge.md` 了解整合進度和已知問題

---

## 📝 技術細節

### GIL 處理

- 使用 NumPy 向量化操作（釋放 GIL）
- 關鍵迴圈中使用 `socketio.sleep(0)`

### 前後端同步

- 遊戲邏輯在前端（JavaScript）
- 後端僅發送事件
- ECG 障礙物在右側生成，有緩衝時間

### Import 路徑

- 音訊模組已移至 `src/audio/`
- 相對 import 已修正為 `from .. import config`

---

## 🐛 疑難排解

### 找不到音訊裝置

```bash
# 檢查可用裝置
python scripts/check_audio_devices.py
```

### ECG 無法連接

```bash
# 檢查 COM Port
python -m serial.tools.list_ports

# 手動指定 Port
python app.py --ecg-port COM3
```

### 語音辨識不準確

```bash
# 使用不同方法
python app.py --voice-method mfcc_dtw

# 重新校準（在安靜環境啟動）
```

---

## 👥 團隊

- 111061223 江品萱
- 111061155 林川祐
- 111061233 孔祥有

---

## 📖 參考文件

- [原語音系統 README](README.md)
- [實驗記錄](docs/)
- [整合計畫](C:\Users\user\.claude\plans\snuggly-cooking-pond.md)
- [進度追蹤](great_merge.md)

---

**🎉 Enjoy the game!**
