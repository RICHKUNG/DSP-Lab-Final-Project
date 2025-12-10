# Advanced Experiment Plan - 2025-12-10

**Current Status Analysis**

## 📊 當前系統表現

### 優勢
- ✅ 整體準確率優秀：94.3-94.6%
- ✅ 延遲低：165-220ms
- ✅ 速度/音高/音量穩健性極佳：97-100%

### 瓶頸 🎯
1. **噪音 10dB 準確率**: 64-71% (目標 >80%)
2. **特定模板弱點**: 開始3.wav, 開始4.wav 在多種條件下失敗
3. **Ensemble 速度成本**: +33% 延遲，但僅在噪音下有優勢

---

## 🔬 實驗方案

### 選項 A: Advanced Features (推薦) ⭐

**目標**: 突破 10dB 噪音瓶頸

#### A1. Spectral Subtraction (噪音消除)
**原理**: 預估噪音頻譜並從信號中減去
**預期效果**: 10dB 準確率 64% → 75-80%
**實施難度**: 中等
**測試方法**:
```python
# 新增 apply_spectral_subtraction() 函數
# 在特徵提取前先做噪音消除
```

#### A2. RASTA-PLP Features
**原理**: 比 MFCC 更抗噪音的特徵
**預期效果**: 10dB 準確率可能 +5-10%
**實施難度**: 較高（需新增 feature extractor）

#### A3. Noise-Adaptive Ensemble Weights
**原理**: 根據噪音程度動態調整方法權重
**預期效果**:
- 安靜環境：快速（mfcc_dtw 權重高）
- 噪音環境：準確（mel 權重高，因其在噪音下穩定）
**實施難度**: 低
**測試方法**:
```python
# MultiMethodMatcher.recognize() 加入 SNR 估計
# 根據 SNR 調整投票權重
```

---

### 選項 B: Arena 加難

**目標**: 更嚴格的評估標準

#### B1. 極端條件測試
```python
TEST_SUITES = {
    'Speed': [0.5, 0.7, 0.9, 1.0, 1.1, 1.3, 1.5],  # 更極端
    'Pitch': [-4, -2, 0, 2, 4],  # 更大範圍
    'Noise': [100, 20, 15, 10, 5, 0],  # 新增 5dB, 0dB
    'Volume': [0.1, 0.3, 1.0, 3.0, 5.0],  # 更極端
}
```

#### B2. 混合條件測試（真實場景）
```python
# 同時測試多種干擾
'Mixed_Conditions': [
    ('speed=0.9, noise=15dB'),
    ('pitch=+2, volume=0.3'),
    ('speed=1.2, noise=10dB, volume=2.0'),
]
```

#### B3. 多種噪音類型
- 白噪音（目前使用）
- 粉紅噪音（更接近環境噪音）
- 人聲噪音（多人說話）
- 環境噪音（錄音檔）

---

### 選項 C: 參數精調

**目標**: 從 94.6% 推向 95-96%

#### C1. MFCC 參數優化
測試組合：
```python
N_MFCC: [10, 13, 16, 20]
N_FFT: [512, 1024, 2048]
HOP_LENGTH: [256, 512, 1024]
```
**預期**: 可能 +0.5-1% 準確率

#### C2. Threshold Grid Search
```python
# 系統化測試
THRESHOLD_MFCC_DTW: [120, 130, 140, 150, 160]
THRESHOLD_MEL: [0.35, 0.40, 0.45, 0.50]
THRESHOLD_LPC: [80, 90, 100, 110, 120]
```

#### C3. DTW Radius 再驗證
```python
# 已測試 2, 3, 5, 7
# 補測試 4, 6 確認 radius=3 是否真的最優
```

---

## 🎯 我的建議

### Phase 1: Advanced Features (優先) ⭐⭐⭐

**實驗 1A: Noise-Adaptive Ensemble** (快速實施)
- **Why**: 低實施成本，可能立即見效
- **How**:
  1. 在 MultiMethodMatcher 加入 SNR 估計
  2. 噪音環境增加 mel 權重（已知其在噪音下穩定 79%）
  3. 安靜環境增加 mfcc_dtw 權重（速度優勢）
- **Success Metric**: 10dB 準確率 >75%，平均延遲 <200ms

**實驗 1B: Spectral Subtraction** (中期目標)
- **Why**: 直接攻克噪音問題的根源
- **How**: 在 apply_augmentation() 加入噪音估計與消除
- **Success Metric**: 10dB 準確率 >80%

### Phase 2: Arena 加難 (驗證)

**實驗 2A: 極端噪音測試**
- 新增 5dB, 0dB 測試
- 確認系統的極限在哪裡

**實驗 2B: 混合條件**
- 測試真實場景（速度+噪音+音量同時變化）

### Phase 3: 參數精調 (最後優化)

只在 Phase 1-2 完成後進行

---

## 📋 實驗執行計劃

### 立即開始: 實驗 1A - Noise-Adaptive Ensemble

**步驟**:
1. 實施 SNR 估計函數（基於能量比）
2. 修改 MultiMethodMatcher.recognize() 加入權重調整
3. Arena 測試比較
4. 分析結果

**預計時間**: 30-45 分鐘

**如果成功** → 繼續實驗 1B (Spectral Subtraction)
**如果失敗** → 切換到實驗 2A (極端測試確認瓶頸)

---

## 🤔 你的選擇？

請選擇實驗方向：

**A. Advanced Features** (我推薦)
- A1: Noise-Adaptive Ensemble (快速)
- A2: Spectral Subtraction (中期)
- A3: RASTA-PLP (長期)

**B. Arena 加難**
- B1: 極端條件 (5dB, 0dB 噪音)
- B2: 混合條件測試
- B3: 多種噪音類型

**C. 參數精調**
- C1: MFCC 參數網格搜索
- C2: Threshold 精調
- C3: DTW Radius 補測

**D. 自由探索**
- 你有其他想法？

---

**我的建議**: 從 **A1 (Noise-Adaptive Ensemble)** 開始
- 實施快速（~30分鐘）
- 有理論支持（mel 在噪音下穩定）
- 可立即驗證效果
- 成功率高

要開始實驗 A1 嗎？或是你有其他想法？
