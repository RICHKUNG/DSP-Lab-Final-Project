# temp/ 目錄說明

此目錄包含開發、測試和分析工具。

## 📊 測試與評估工具

### 主要測試腳本
- **`test_file_input.py`** - Arena測試（完整評估系統）
  - 測試速度、音高、噪音、音量穩健性
  - 自動保存結果到 `record/arena_*.json`
  - 使用方式: `python temp/test_file_input.py`

- **`quick_speed_test.py`** - 快速延遲測試
  - 測試5個樣本的平均延遲
  - 用於驗證優化效果
  - 使用方式: `python temp/quick_speed_test.py`

### 結果分析工具
- **`view_history.py`** - 互動式歷史比較工具
  - 比較不同測試結果
  - 查看配置變化影響
  - 使用方式: `python temp/view_history.py`

- **`show_latest.py`** - 快速查看最新結果
  - 顯示最新Arena測試摘要
  - 使用方式: `python temp/show_latest.py`

- **`analyze_failures.py`** - 失敗分析
  - 識別哪些方法和條件表現最差
  - 提供改進建議
  - 使用方式: `python temp/analyze_failures.py`

- **`find_bad_templates.py`** - 問題模板識別
  - 找出需要重新錄製的模板
  - 使用方式: `python temp/find_bad_templates.py`

### 效能分析工具
- **`profile_latency.py`** - 延遲分析
  - 詳細顯示各組件耗時
  - 識別效能瓶頸
  - 使用方式: `python temp/profile_latency.py`

## 🛠️ 開發工具

- **`check_audio_devices.py`** - 檢查音訊設備
  - 列出可用的輸入設備
  - 使用方式: `python temp/check_audio_devices.py`

- **`check_templates.py`** - 檢查模板統計（未完成）

- **`record_garbage.py`** - 錄製背景噪音
  - 用於創建噪音拒絕模板
  - 使用方式: `python temp/record_garbage.py`

- **`test_features.py`** - 測試特徵提取
  - 驗證特徵提取功能

## 📁 archive/ 子目錄

已過時或重複的腳本存放處：
- `test_audi.py` - 拼寫錯誤的過時測試
- `test_audio.py` - 被其他工具取代
- `test_device_only.py` - 被 check_audio_devices.py 取代
- `test_native_rate.py` - 過時的採樣率測試
- `check_sd_devices.py` - 重複的設備檢查
- `audio_diagnostic.py` - 被 check_audio_devices.py 取代

## 📖 使用建議

### 日常開發流程
1. 修改代碼後，運行 `quick_speed_test.py` 驗證延遲
2. 完整測試使用 `test_file_input.py`
3. 比較結果使用 `view_history.py`
4. 分析問題使用 `analyze_failures.py`

### 效能優化流程
1. 使用 `profile_latency.py` 找出瓶頸
2. 優化代碼
3. 使用 `quick_speed_test.py` 驗證改進
4. 使用 `test_file_input.py` 確保準確率不降

### 準確率改進流程
1. 使用 `analyze_failures.py` 找出問題
2. 使用 `find_bad_templates.py` 識別需改進的模板
3. 重新錄製或調整參數
4. 使用 `test_file_input.py` 驗證改進
