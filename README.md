# Bio-Voice Commander

語音指令控制系統 - DSP 期末專題

## 專案目標

1. **語音指令控制跑酷遊戲** - 支援 5 個指令：`START`, `PAUSE`, `JUMP`, `MAGNET`, `INVERT`
2. **Speaker-independent** - 任何人都能使用，不限於訓練者
3. **低延遲** - 從說完指令到遊戲收到 command ≤ 300 ms

## 系統架構

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  麥克風輸入  │ -> │  VAD 偵測   │ -> │  特徵提取   │ -> │  模板比對   │ -> Command
│ (PyAudio)   │    │ (能量+ZCR)  │    │ (4種方法)   │    │ (DTW/L2)   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

## 四種 DSP 辨識方法

| 方法 | 特徵 | 比對方式 | 特性 |
|------|------|----------|------|
| MFCC+DTW | 13 MFCC + delta | Dynamic Time Warping | 最穩定，主要方法 |
| Stats | 分段統計 (mean/std) | Euclidean | 最快速，固定維度 |
| Mel-template | 128-bin Mel-spectrogram | L2 距離 | 對語速變化穩定 |
| LPC | 12 階 LPC 係數 | Euclidean | 對 pitch 變化穩定 |

## 安裝

```bash
# 建立 conda 環境
conda create -n dspfp python=3.10 -y
conda activate dspfp

# 安裝套件
conda install -c conda-forge numpy scipy librosa pyaudio matplotlib ffmpeg -y
pip install fastdtw
```

## 使用方式

### 測試特徵提取
```bash
conda activate dspfp
python test_features.py
```

### 即時語音辨識
```bash
python -m src.main --live --templates .
```

### 測試單一音檔
```bash
python -m src.main --test "開始1.m4a" --templates .
```

### 進階魯棒性測試 (Arena Test)
此工具使用 Leave-One-Out Cross-Validation 策略，針對速度、音高、噪音與音量進行壓力測試：
```bash
python temp/test_file_input.py
```
測試項目包含：
- **Speed**: 0.7x ~ 1.3x
- **Pitch**: -2.5 ~ +2.5 半音
- **Noise**: 100dB (Clean) ~ 10dB (Noisy)
- **Volume**: 0.3x ~ 3.0x

## 模板檔案命名規則

檔案名稱需包含中文指令名稱：

| 中文 | 英文指令 |
|------|----------|
| 開始 | START |
| 暫停 | PAUSE |
| 跳 | JUMP |
| 磁鐵 | MAGNET |
| 反轉 | INVERT |

範例：`開始1.m4a`, `跳2.wav`, `暫停_speaker1.mp3`

## 專案結構

```
Final/
├── src/
│   ├── config.py           # 全局設定參數
│   ├── audio_io.py         # 音訊 I/O 與緩衝區
│   ├── vad.py              # 語音活動偵測
│   ├── main.py             # 主程式入口
│   ├── features/
│   │   ├── mfcc.py         # MFCC 特徵
│   │   ├── stats.py        # 分段統計特徵
│   │   ├── mel_template.py # Mel-spectrogram 模板
│   │   └── lpc.py          # LPC/Formant 特徵
│   └── recognizers/
│       ├── dtw.py          # DTW 距離
│       └── template_matcher.py  # 模板比對器
├── test_features.py        # 測試腳本
├── requirements.txt        # 依賴套件
└── README.md
```

## 參數調整

編輯 `src/config.py` 可調整：

- `SAMPLE_RATE` - 取樣率 (預設 16kHz)
- `VAD_MIN_SPEECH_MS` - 最短語音長度 (預設 200ms)
- `VAD_MAX_SPEECH_MS` - 最長語音長度 (預設 1500ms)
- `THRESHOLD_*` - 各方法的辨識門檻

## 支援格式

- `.wav` - 直接支援
- `.mp3` - 需要 ffmpeg
- `.m4a` - 需要 ffmpeg
