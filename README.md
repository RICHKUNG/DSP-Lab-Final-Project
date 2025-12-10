# Bio-Voice Commander

語音指令控制系統 - DSP 期末專題

## 🎯 專案目標

1. **語音指令控制跑酷遊戲** - 支援 5 個指令：`START`, `PAUSE`, `JUMP`, `MAGNET`, `INVERT`
2. **Speaker-independent** - 任何人都能使用，不限於訓練者
3. **低延遲 + 高準確率** - ≤ 250ms 延遲，≥ 80% 準確率 ✅

## 📊 當前效能 (2025-12-10)

### 最新效能 - DTW_RADIUS=3 優化

| 指標 | MFCC_DTW | Ensemble | 狀態 |
|------|----------|----------|------|
| **延遲** | **165ms** | **220ms** | ✅ 達標 (目標 ≤250ms) |
| **準確率** | **94.3%** | **94.6%** | ✅ 優秀 |
| **噪音 10dB** | **64%** | **71%** ⭐ | ✅ Ensemble 優勢 |
| **加速比** | **4.2x** | **3.2x** | ✅ 從700ms優化 |

**方法選擇建議**:
- **MFCC_DTW**: 速度優先，安靜環境（33% 更快）
- **Ensemble**: 準確率優先，噪音環境（噪音下 +7% 準確率）

詳細比較請參考 [`record/test_20251210_method_comparison.md`](record/test_20251210_method_comparison.md)

詳細優化歷程請參考 [`docs/OPTIMIZATION_SUMMARY.md`](docs/OPTIMIZATION_SUMMARY.md)

## 🏗️ 系統架構

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  麥克風輸入  │ -> │  VAD 偵測   │ -> │  特徵提取   │ -> │  模板比對   │ -> Command
│ (PyAudio)   │    │ (能量+ZCR)  │    │ (Ensemble)  │    │ (DTW/L2)   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

## 🔬 識別方法

系統使用 **Ensemble** 集成方法，結合三種 DSP 特徵：

| 方法 | 特徵 | 比對方式 | 準確率 | 角色 |
|------|------|----------|--------|------|
| **MFCC+DTW** | 13 MFCC + Δ | Dynamic Time Warping | **80.0%** | 主力 ✅ |
| Mel-template | 128-bin Mel | Cosine 距離 | 44-53% | 輔助 |
| LPC (Fast) | 12階 LPCC | Fixed-size L2 | 50.7% | 輔助 |

### 關鍵優化

**Phase 1: FastLPCMatcher** (2x speedup)
- 使用固定尺寸 + Euclidean 距離取代 DTW
- 700ms → 330ms
- 準確率維持

**Phase 2: DTW Radius 優化** (1.5x speedup)
- DTW_RADIUS: 5 → 2
- 330ms → 217ms
- 準確率: 80.3% → 80.0% (可接受)

詳見 [`docs/exp_fast_1.md`](docs/exp_fast_1.md) 和 [`docs/exp_fast_2.md`](docs/exp_fast_2.md)

## 🚀 快速開始

### 安裝

```bash
# 建立 conda 環境
conda create -n dspfp python=3.10 -y
conda activate dspfp

# 安裝套件
conda install -c conda-forge numpy scipy librosa pyaudio matplotlib ffmpeg -y
pip install fastdtw
```

### 即時語音辨識

```bash
# 高速模式 - 用 \r 持續印出當前識別結果（預設 ensemble）
python test_live.py

# 使用 MFCC+DTW 單一方法（更快）
python test_live.py --method mfcc_dtw

# 使用 Ensemble 集成方法（更準確）
python test_live.py --method ensemble
```

### QA 測試模式

```bash
# QA1 - 每次偵測都詢問正確標籤（預設 ensemble）
python test_QA.py

# QA1 - 使用 MFCC+DTW 方法
python test_QA.py --method mfcc_dtw

# QA2 - 只在偵測到指令時詢問（噪音自動跳過）
python test_QA2.py

# QA2 - 使用 MFCC+DTW 方法
python test_QA2.py --method mfcc_dtw
```

## 📈 測試與評估

### Arena Test (完整評估)

**推薦使用** - 完整測試系統在各種條件下的表現：

```bash
# Ensemble 完整測試（約 5 分鐘，預設）
python test_arena.py --method ensemble

# MFCC_DTW 單一方法測試（約 3-4 分鐘，更快）
python test_arena.py --method mfcc_dtw
```

**方法選擇**:
- `--method mfcc_dtw`: 單一方法測試（更快，適合快速驗證）
- `--method ensemble`: 完整集成方法測試（更準確，可看到各方法表現）

測試項目：
- **Speed**: 0.7x ~ 1.3x (語速變化)
- **Pitch**: -2.5 ~ +2.5 半音 (音高變化)
- **Noise**: 100dB ~ 10dB (噪音穩健性)
- **Volume**: 0.3x ~ 3.0x (音量變化)

結果自動保存至 `record/arena_YYYYMMDD_HHMMSS.json`

### 查看測試結果

```bash
# 快速查看最新結果
python temp/show_latest.py

# 查看歷史與比對
python temp/view_history.py
```

### 快速速度測試

```bash
# 測試當前配置的延遲
python temp/quick_speed_test.py
```

### 分析工具

```bash
# 分析哪些方法和條件失敗最多
python temp/analyze_failures.py

# 識別需要重新錄製的模板
python temp/find_bad_templates.py

# 分析延遲瓶頸
python temp/profile_latency.py
```

詳細說明請參考 [`docs/BENCHMARK_GUIDE.md`](docs/BENCHMARK_GUIDE.md)

## 📂 專案結構

```
Final/
├── src/                      # 核心程式碼
│   ├── config.py            # 全局設定（閾值、參數）
│   ├── audio_io.py          # 音訊 I/O
│   ├── vad.py               # 語音活動偵測
│   ├── features.py          # 特徵提取（MFCC/Mel/LPC）
│   ├── recognizers.py       # 辨識器（DTW/FastLPC/Ensemble）
│   └── main.py              # 主程式
│
├── docs/                     # 📚 文檔
│   ├── README.md            # 文檔目錄導覽
│   ├── OPTIMIZATION_SUMMARY.md   # 速度優化總結
│   ├── ACCURACY_ANALYSIS.md      # 準確率分析報告
│   ├── BENCHMARK_GUIDE.md        # 測試系統指南
│   ├── exp_fast_1.md        # FastLPCMatcher 實驗
│   ├── exp_fast_2.md        # DTW Radius 實驗
│   └── exp_log.md           # 其他實驗記錄
│
├── temp/                     # 🛠️ 開發工具
│   ├── README.md            # 工具說明文檔
│   ├── quick_speed_test.py  # 快速延遲測試
│   ├── view_history.py      # 歷史結果查看
│   ├── show_latest.py       # 最新結果摘要
│   ├── analyze_failures.py  # 失敗分析
│   ├── find_bad_templates.py # 問題模板識別
│   ├── profile_latency.py   # 延遲分析
│   └── archive/             # 已過時的腳本
│
├── cmd_templates/            # 指令模板（.wav）
├── record/                   # 測試結果（JSON/MD）
│   ├── arena_*.json         # Arena 測試結果
│   ├── test_*.md            # QA 測試報告
│   └── test_qa2_*.md        # QA2 測試報告
│
├── test_live.py             # 即時語音辨識（高速模式）
├── test_QA.py               # QA 測試（所有偵測都詢問）
├── test_QA2.py              # QA 測試（僅指令詢問）
├── test_arena.py            # Arena 測試（完整評估）
├── README.md                # 本文檔
├── CLAUDE.md                # 專案指示
└── insight.md               # 開發筆記
```

## 🎨 模板檔案命名規則

檔案名稱需包含中文指令名稱：

| 中文 | 英文指令 |
|------|----------|
| 開始 | START |
| 暫停 | PAUSE |
| 跳 | JUMP |
| 磁鐵 | MAGNET |
| 反轉 | INVERT |

範例：`開始1.wav`, `跳2.wav`, `暫停.m4a`

## ⚙️ 參數調整

編輯 `src/config.py` 可調整：

### 關鍵參數
```python
# 速度優化
DTW_RADIUS = 2              # DTW 搜索半徑 (2=快, 5=慢但準)
HOP_LENGTH = 512            # 特徵提取 hop size

# 辨識閾值
THRESHOLD_MFCC_DTW = 140.0  # MFCC 閾值
THRESHOLD_MEL = 0.40        # Mel 閾值（Cosine距離）
THRESHOLD_LPC = 100.0       # LPC 閾值

# VAD 參數
VAD_MIN_SPEECH_MS = 200     # 最短語音長度
VAD_MAX_SPEECH_MS = 1500    # 最長語音長度
VAD_SILENCE_MS = 300        # 靜音判定時間
```

### 噪音環境調整

如在嘈雜環境中使用，啟用噪音模式（取消註解）：
```python
# src/config.py
VAD_ENERGY_THRESHOLD_MULT_LOW = 3.5   # 提高靈敏度
VAD_ENERGY_THRESHOLD_MULT_HIGH = 6.0  # 減少誤觸發
```

## 📖 文檔導覽

### 想了解優化歷程？
1. [`docs/OPTIMIZATION_SUMMARY.md`](docs/OPTIMIZATION_SUMMARY.md) - 完整優化總結
2. [`docs/exp_fast_1.md`](docs/exp_fast_1.md) - LPC 優化實驗
3. [`docs/exp_fast_2.md`](docs/exp_fast_2.md) - DTW 優化實驗

### 想提升準確率？
1. [`docs/ACCURACY_ANALYSIS.md`](docs/ACCURACY_ANALYSIS.md) - 準確率分析與改進建議
2. 運行 `python temp/find_bad_templates.py` - 找出問題模板
3. 重新錄製低品質模板

### 想使用測試工具？
1. [`docs/BENCHMARK_GUIDE.md`](docs/BENCHMARK_GUIDE.md) - 測試系統完整指南
2. [`temp/README.md`](temp/README.md) - 各工具說明

## 🔍 常見問題

### Q: 如何選擇辨識方法？
A:
- **MFCC+DTW** (`--method mfcc_dtw`): 單一方法，速度更快，適合需要低延遲的場景
- **Ensemble** (`--method ensemble`，預設): 集成方法，準確率更高，適合需要高準確率的場景

測試建議：先用 `mfcc_dtw` 測試速度，若準確率不足再切換到 `ensemble`

### Q: 延遲太高怎麼辦？
A:
1. 使用 `--method mfcc_dtw` 切換到單一方法
2. 運行 `python temp/profile_latency.py` 找出瓶頸
3. 降低 `DTW_RADIUS` 到 1（可能影響準確率）

### Q: 準確率不夠高怎麼辦？
A:
1. 使用 `--method ensemble` 切換到集成方法
2. 運行 `python temp/find_bad_templates.py` 找出問題模板並重新錄製
3. 增加每個指令的模板數量（5個 → 7-8個）
4. 參考 [`docs/ACCURACY_ANALYSIS.md`](docs/ACCURACY_ANALYSIS.md) 的改進建議

### Q: 測試結果在哪裡？
A: `record/arena_*.json` - 使用 `python temp/view_history.py` 查看

### Q: 如何比較不同配置？
A: 修改 `config.py` 後運行 Arena test，然後用 `view_history.py` 比對結果

## 📊 效能基準

### 當前配置 (DTW_RADIUS=2)
- **延遲**: 217ms
- **整體準確率**: 80.0%
- **Clean 環境**: 86.7%
- **10dB 噪音**: 60.0%
- **速度變化**: 80-87%
- **音高變化**: 73-87%

### 備選配置 (如需更高噪音穩健性)
- **DTW_RADIUS=3**: 延遲 275ms, 準確率 80.3%, 20dB噪音 73%
- **DTW_RADIUS=5**: 延遲 330ms, 準確率 80.3%, 最佳噪音穩健性

## 🤝 貢獻

如發現問題或有改進建議：
1. 運行相關測試工具記錄問題
2. 查看 [`docs/`](docs/) 目錄中的分析文檔
3. 提交 Issue 或 Pull Request

## 📜 授權

DSP 期末專題 - 2025
