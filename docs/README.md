# 文檔目錄

此目錄包含專案的詳細文檔、實驗記錄和分析報告。

## 📚 主要文檔

### 指南類
- **`BENCHMARK_GUIDE.md`** - 測試基準系統使用指南
  - 如何運行Arena測試
  - 如何查看和比較歷史結果
  - 結果檔案格式說明

### 分析報告
- **`ACCURACY_ANALYSIS.md`** - 準確率分析報告
  - 當前系統準確率分析 (80%)
  - 為何Mel/LPC方法表現較差
  - 提升準確率的真正方法
  - 問題模板識別
  - 改進建議 (模板品質、特徵工程、深度學習)

- **`OPTIMIZATION_SUMMARY.md`** - 速度優化總結
  - 從700ms優化到217ms的完整歷程
  - FastLPCMatcher優化 (Phase 1)
  - DTW Radius優化 (Phase 2)
  - 最終配置和權衡分析

## 🔬 實驗記錄

- **`exp_fast_1.md`** - FastLPCMatcher實驗
  - 問題: LPC DTW太慢 (480ms)
  - 解法: 固定尺寸 + 歐式距離
  - 結果: 700ms → 330ms (2.1x加速)
  - 準確率: 維持100%

- **`exp_fast_2.md`** - DTW Radius優化實驗
  - 問題: MFCC DTW是新瓶頸 (330ms, 佔88%)
  - 解法: DTW_RADIUS從5降至2
  - 結果: 330ms → 217ms (1.5x加速)
  - 準確率: 80.3% → 80.0% (可接受)

- **`exp_log.md`** - 其他實驗記錄

## 📋 規劃文檔

- **`PLAN.md`** - 專案規劃和待辦事項

## 📊 關鍵成果摘要

### 速度優化
| 階段 | 延遲 | 加速比 | 準確率 |
|------|------|--------|--------|
| 原始 | 700ms | 1.0x | 80.3% |
| Phase 1 (FastLPC) | 330ms | 2.1x | 80.3% ✅ |
| Phase 2 (DTW r=2) | **217ms** | **3.2x** | 80.0% ✅ |

### 準確率分析
| 方法 | 準確率 | 角色 |
|------|--------|------|
| MFCC-DTW | 80.0% | 主力 ✅ |
| Mel-Spectrogram | 44-53% | 輔助 ⚠️ |
| LPC (Fast) | 50.7% | 輔助 ⚠️ |
| Ensemble | 80.0% | = MFCC |

**關鍵洞察:**
- 當前配置已達特徵/模板組合的準確率上限
- 需要改善模板品質才能突破80%

## 🔗 相關資源

### 測試工具
- 測試工具位於 `../temp/` 目錄
- 測試結果保存在 `../record/` 目錄

### 程式碼
- 核心代碼在 `../src/` 目錄
- 配置檔案: `../src/config.py`
- 主要模組: `../src/recognizers.py`

## 📖 閱讀順序建議

### 了解系統優化歷程
1. `OPTIMIZATION_SUMMARY.md` - 優化總覽
2. `exp_fast_1.md` - LPC優化細節
3. `exp_fast_2.md` - DTW優化細節

### 了解準確率狀況
1. `ACCURACY_ANALYSIS.md` - 完整分析報告
2. 運行 `../temp/analyze_failures.py` - 查看當前失敗情況
3. 運行 `../temp/find_bad_templates.py` - 找出問題模板

### 使用測試系統
1. `BENCHMARK_GUIDE.md` - 測試系統指南
2. `../temp/README.md` - 測試工具說明
