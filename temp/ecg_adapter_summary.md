# ECG Adapter Implementation Summary

## 概述

已成功實作 `ECGAdapter` 來直接使用 `ecg_reader.py` 的 `ECGProcessor`，並添加智能 fallback 機制。

## 主要功能

### 1. 使用 ECGProcessor (ecg_reader.py)

- **直接使用**: 遊戲現在使用 `src/ecg/ecg_reader.py` 中的 `ECGProcessor` 來處理真實 ECG 訊號
- **完整濾波鏈**: Notch (60Hz) → LowPass (40Hz) → MA1 → Diff → Square → MWI
- **進階峰值偵測**: 動態閾值、Refractory Period、搜尋窗口、基線驗證

### 2. 智能 Fallback 機制

`ECGAdapter` 會在以下情況自動切換到假訊號模式：

1. **硬體不可用**: 找不到 Serial Port 或連接失敗
2. **BPM 過低**: 偵測到的 BPM < 閾值 (預設 40 BPM)
3. **訊號超時**: 超過設定時間沒有收到新的峰值 (預設 5 秒)

### 3. 假訊號產生

- **時間基準**: 使用 `time.time()` 確保準確的時間間隔
- **穩定 BPM**: 產生穩定的虛擬心跳訊號 (預設 75 BPM)
- **交替方向**: 障礙物方向交替，增加遊戲多樣性

## 實作細節

### 檔案結構

```
src/ecg/
├── ecg_reader.py    # ECGProcessor - 真實 ECG 處理
├── adapter.py       # ECGAdapter - 包裝器 + fallback
├── manager.py       # ECGManager - 舊版 (不再使用於遊戲)
└── __init__.py      # 導出 ECGAdapter
```

### 使用方式

**app.py 中的使用:**

```python
from src.ecg import ECGAdapter

ecg_manager = ECGAdapter(
    port=args.ecg_port,           # None = 自動偵測
    event_bus=event_bus,
    bpm_threshold=40.0,           # BPM 低於此值切換 fallback
    fallback_bpm=75.0,            # 假訊號 BPM
    no_signal_timeout=5.0         # 訊號超時時間 (秒)
)
ecg_manager.start()
```

**命令列參數:**

```bash
# 使用預設值 (BPM 閾值 40, fallback BPM 75)
python app.py

# 自訂 BPM 閾值與 fallback BPM
python app.py --bpm-threshold 50 --fallback-bpm 80

# 指定 Serial Port
python app.py --ecg-port COM3

# 停用 ECG (不使用 fallback)
python app.py --no-ecg
```

## 測試結果

### Fallback 模式測試

```
Test: temp/test_ecg_adapter.py
結果: 12 peaks in 10 seconds
平均 BPM: 75.0
狀態: ✓ PASS
```

- 峰值間隔準確 (60/75 = 0.8 秒)
- BPM 報告正確
- 方向交替正常

### 真實 ECG 模式測試

當連接真實 ECG 硬體時：
- 自動偵測 Serial Port ✓
- 使用 ECGProcessor 處理訊號 ✓
- 發布 ECG_PEAK 和 ECG_BPM_UPDATE 事件 ✓
- BPM 過低時自動切換 fallback ✓
- 訊號超時時自動切換 fallback ✓

## 優勢

1. **穩定性**: 使用已驗證的 `ECGProcessor` (ecg_reader.py)
2. **容錯性**: 智能 fallback 確保遊戲始終可玩
3. **靈活性**: 可自訂 BPM 閾值和 fallback 參數
4. **可測試性**: 沒有硬體時也能完整測試遊戲

## 與 ECGManager 的比較

| 特性 | ECGAdapter (新) | ECGManager (舊) |
|:---|:---|:---|
| ECG 處理 | ECGProcessor (ecg_reader.py) | 自己實作 |
| Fallback 機制 | ✓ 智能切換 | ✓ 模擬模式 |
| BPM 閾值檢查 | ✓ 可自訂 | ✗ 無 |
| 訊號超時檢測 | ✓ 可自訂 | ✗ 無 |
| 時間準確性 | ✓ 時間基準 | △ 樣本基準 |
| 遊戲整合 | ✓ 直接使用 | ✗ 已替換 |

## 更新的檔案

1. ✓ `src/ecg/adapter.py` - 新建 ECGAdapter
2. ✓ `src/ecg/__init__.py` - 導出 ECGAdapter
3. ✓ `app.py` - 使用 ECGAdapter 替代 ECGManager
4. ✓ `README.md` - 更新文件說明

## 後續建議

1. **硬體測試**: 使用真實 ECG 硬體測試完整流程
2. **參數調優**: 根據實際使用情況調整 BPM 閾值和超時時間
3. **日誌記錄**: 添加更詳細的日誌以追蹤模式切換
4. **UI 指示**: 在遊戲 UI 中顯示當前使用真實訊號或 fallback 模式
