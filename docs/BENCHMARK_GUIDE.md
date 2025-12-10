# Benchmark 管理系統使用指南

## 概述

新的 benchmark 系統會自動保存每次測試的完整結果（包含參數配置），方便追蹤效能變化和比對不同配置。

---

## 1. 執行 Arena Test

```bash
conda activate dspfp
python temp/test_file_input.py
```

### 測試內容
- **Speed**: 0.7x ~ 1.3x (語速變化)
- **Pitch**: -2.5 ~ +2.5 半音 (音高變化)
- **Noise**: 100dB (Clean) ~ 10dB (高噪音)
- **Volume**: 0.3x ~ 3.0x (音量變化)

### 自動保存
測試完成後會自動保存到：
```
record/arena_YYYYMMDD_HHMMSS.json
```

包含：
- 時間戳記
- 所有配置參數（thresholds, hop_length, LPC order 等）
- 各方法在各測試條件下的準確率
- 詳細錯誤統計 (wrong_command, no_match, noise)

---

## 2. 查看歷史成績

```bash
python temp/view_history.py
```

### 功能

#### A. 總覽表格
自動顯示所有歷史測試的摘要：
```
#    Timestamp            MFCC     Mel      LPC      Ensemble Config Changes
----------------------------------------------------------------------------------------
1    2025-12-09 20:00:00  85.0%    78.0%    82.0%    87.0%    -
2    2025-12-09 21:00:00  85.0%    78.0%    85.0%    90.0%    lpc_th:80->100
3    2025-12-09 22:00:00  85.0%    78.0%    85.0%    92.0%    hop:256->512
```

#### B. 噪音穩健性趨勢
```
Run  Timestamp            Clean (100dB)  Noisy (10dB)  Drop
----------------------------------------------------------------
1    2025-12-09 20:00:00      85.0%         75.0%      10.0%
2    2025-12-09 22:00:00      85.0%         82.0%       3.0%  <- 改善!
```

#### C. 互動式比對

**比對兩次測試：**
```
> compare 1 2
```
會顯示：
- 各測試條件下的準確率變化
- 配置參數的差異
- 哪些改動導致效能提升/下降

**查看詳細資料：**
```
> detail 2
```
顯示該次測試的完整 JSON 資料

---

## 3. 使用情境範例

### 情境 A：調整 threshold
```bash
# 1. 修改 src/config.py
THRESHOLD_LPC = 100.0  # 從 80.0 調高

# 2. 執行測試
python temp/test_file_input.py

# 3. 查看結果
python temp/view_history.py
> compare 5 6  # 比對修改前後
```

### 情境 B：測試新的優化
```bash
# 1. 實作 FastLPCMatcher
# 2. 執行完整測試
python temp/test_file_input.py

# 3. 比對優化前後
python temp/view_history.py
> compare 10 11
```

結果會清楚顯示：
- 速度有無提升
- 準確率有無損失
- 哪些條件下表現變好/變差

---

## 4. 檔案結構

```
Final/
├── record/
│   ├── arena_20251209_200000.json  # 第一次測試
│   ├── arena_20251209_210000.json  # 第二次測試
│   └── arena_20251209_220000.json  # 第三次測試
├── temp/
│   ├── test_file_input.py          # Arena 測試主程式
│   └── view_history.py             # 歷史查看工具
└── src/
    └── config.py                   # 配置參數
```

---

## 5. 最佳實踐

### 在修改前先測試
```bash
# 建立 baseline
python temp/test_file_input.py

# 記下結果編號 (例如 #5)
```

### 每次重大修改後都測試
- 修改 threshold
- 改變 hop_length
- 新增/修改特徵提取方法
- 更換距離度量

### 定期檢視趨勢
```bash
python temp/view_history.py
```
觀察：
- 準確率是否穩定提升
- 噪音穩健性是否改善
- 有無意外的效能倒退

---

## 6. JSON 格式說明

```json
{
  "timestamp": "2025-12-09 22:00:00",
  "config": {
    "audio": {
      "sample_rate": 16000,
      "hop_length": 512,
      ...
    },
    "thresholds": {
      "mfcc_dtw": 140.0,
      "lpc": 100.0,
      ...
    }
  },
  "suites": {
    "Noise": {
      "methods": {
        "ensemble": {
          "100": {"accuracy": 1.0, "correct": 15, "total": 15},
          "10": {"accuracy": 1.0, "correct": 15, "total": 15}
        }
      }
    }
  },
  "overall_scores": {
    "ensemble": {
      "average_accuracy": 0.92
    }
  }
}
```

---

## 7. 故障排除

### 找不到歷史記錄
```bash
ls record/arena_*.json
```
確認檔案是否存在

### JSON 格式錯誤
如果某個測試中途中斷，可能產生不完整的 JSON。
刪除該檔案後重新測試：
```bash
rm record/arena_YYYYMMDD_HHMMSS.json
```

### 編碼問題
如果 Windows 終端機顯示亂碼：
```bash
# 使用 Git Bash 或 PowerShell
powershell
python temp/view_history.py
```

---

## 8. 快速參考

| 指令 | 用途 |
|------|------|
| `python temp/test_file_input.py` | 執行完整測試並保存 |
| `python temp/view_history.py` | 查看歷史成績 |
| `compare N M` | 比對第 N 和第 M 次測試 |
| `detail N` | 查看第 N 次測試詳情 |
| `q` | 離開查看工具 |
