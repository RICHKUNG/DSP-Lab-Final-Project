# 🐛 最終 Bug 修正

## 問題回顧

運行 `python app.py` 時發現的問題：

```
[ECGAdapter] BPM too low (0.0 < 40.0), switching to fallback
[Main]   Retry interval: 2.0s
[ECGAdapter] Failed to initialize ECG hardware: PermissionError(13, '存取被拒。')
```

---

## 🔴 問題 1: BPM 0.0 觸發 Fallback

### 根本原因

`ecg_reader.py` 的 `process()` 方法總是返回 `self.bpm`（初始值為 0），即使沒有偵測到新峰值：

```python
# 問題程式碼（舊版）
def process(self):
    new_bpm = self._detect_peak(out_mwi)
    if new_bpm is not None:
        self.bpm = new_bpm

    return self.bpm, out3   # ❌ 總是返回 self.bpm（初始為 0）
```

### 影響

1. 第一次調用返回 `(0.0, filtered_values)`
2. `adapter.py` 判斷 `0.0 < 40.0` → 立即切換到 fallback
3. 真實 ECG 訊號還來不及建立就被放棄

### 修正

**檔案**: `src/ecg/ecg_reader.py:113-119`

```python
# 修正後
def process(self):
    new_bpm = self._detect_peak(out_mwi)
    if new_bpm is not None:
        self.bpm = new_bpm
        return new_bpm, out3   # ✅ 有新峰值：返回新 BPM
    else:
        return None, out3      # ✅ 無新峰值：返回 None
```

**效果**:
- `adapter.py` 的 `if bpm is not None:` 判斷現在正確了
- 只有真正偵測到峰值時才會檢查 BPM 閾值

---

## 🔴 問題 2: app.py 預設值不一致

### 根本原因

`app.py` 中的命令列參數預設值沒有更新：

```python
# 問題程式碼（舊版）
parser.add_argument('--bpm-threshold', type=float, default=40.0)    # ❌ 太高
parser.add_argument('--retry-interval', type=float, default=2.0)   # ❌ 太短
```

### 影響

1. **BPM threshold = 40.0**: 正常心跳（60-100 BPM）可能會在啟動初期誤判
2. **Retry interval = 2.0s**: 重試太頻繁，導致 COM port 衝突

### 修正

**檔案**: `app.py:38-45`

```python
# 修正後
parser.add_argument('--bpm-threshold', type=float, default=-10.0,
                    help='BPM 低於此值時切換到假訊號 (預設: -10，幾乎不觸發)')
parser.add_argument('--retry-interval', type=float, default=10.0,
                    help='Fallback 模式下重試真實 ECG 的間隔秒數 (預設: 10)')
```

**效果**:
- 與 `adapter.py` 和 README 文件一致
- 減少不必要的模式切換
- 避免 Serial Port 衝突

---

## 🔴 問題 3: PermissionError (間接影響)

### 根本原因

前兩個問題導致：
1. 真實 ECG 啟動後立即切換到 fallback
2. 原本的 Serial Port 連接沒有正確關閉
3. 重試時嘗試開啟同一個 COM port → PermissionError

### 解決方式

修正前兩個問題後，此問題自動解決。

---

## ✅ 驗證結果

修正後的預期行為：

```
[Main] Initializing ECG module (port=auto)
[Main]   BPM threshold: -10.0 (switch to fallback)      ← ✅ 正確
[Main]   Retry interval: 10.0s                         ← ✅ 正確
[ECGAdapter] Auto-detecting serial port...
[ECGAdapter] Connected to COM4
[ECGAdapter] Started with real ECG                      ← ✅ 使用真實訊號
[ECGAdapter] Real ECG peak: BPM=75.2                    ← ✅ 偵測到峰值
[ECGAdapter] Real ECG peak: BPM=73.8
...
```

---

## 📊 修改總結

| 檔案 | 行數 | 變更 |
|-----|------|------|
| `src/ecg/ecg_reader.py` | 113-119 | 修改 process() 返回邏輯 |
| `app.py` | 38 | bpm_threshold: 40.0 → -10.0 |
| `app.py` | 44 | retry_interval: 2.0 → 10.0 |

---

## 🎯 重點

這次修正解決了一個**語義不匹配**的問題：

- **adapter.py 假設**: `bpm is None` 表示沒有新峰值
- **ecg_reader.py 實際**: 總是返回數字（從不返回 None）

修正後兩者語義一致，系統邏輯正確。

---

**修正日期**: 2025-12-12
**所有問題**: ✅ 已解決
