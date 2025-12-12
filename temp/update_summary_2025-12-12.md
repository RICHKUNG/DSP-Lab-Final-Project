# 更新摘要 - 2025-12-12

## 📋 更新內容

### 1. 語音指令系統更新
- **移除指令**: `MAGNET`, `INVERT`
- **新增指令**: `FLIP` (翻轉)
- **最終指令集**: `START`, `PAUSE`, `JUMP`, `FLIP` (共 4 個)

### 2. 音檔載入邏輯優化
**檔案**: `src/audio/io.py`

- 支援中英文指令開頭的音檔模板（不區分大小寫）
- 新的檔名識別邏輯：
  ```python
  # 範例支援的檔名格式：
  - 開始.wav, 開始1.wav, 開始_用戶1.wav
  - START_XX.wav, start_01.wav, Start.wav
  - JUMP_user1.wav, jump.wav
  - FLIP_sample.wav, flip_01.wav
  - PAUSE.wav, pause_test.wav, 暫停.wav
  ```

### 3. FLIP 功能實作
**檔案**: `src/game/templates/index.html`

- **功能描述**: 將玩家方塊翻轉到基線的另一側
  - 從上方翻到下方，或從下方翻到上方
  - 翻轉後玩家緊貼基線移動（上緣或下緣）
  - 重置跳躍計數與垂直速度

- **觸發方式**:
  - 語音指令: "翻" 或 "FLIP"
  - 鍵盤: `↓` (下箭頭)

- **實作細節**:
  ```javascript
  flip() {
      this.isOnTop = !this.isOnTop;
      const newGroundY = this.isOnTop ? centerY - this.size : centerY;
      this.y = newGroundY;
      this.dy = 0;
      this.jumpCount = 0;
  }
  ```

### 4. ECG 主題美術設計
**檔案**: `src/game/templates/index.html`

#### 玩家方塊 (Player Block)
- **尺寸**: 24x24 像素（原 20x20）
- **顏色**: 紅色漸層 (#ff4d4d → #ff1a1a → #cc0000)
- **動畫效果**:
  - 脈衝光暈: 呼吸式動畫效果
  - 心電圖波形: 方塊中央繪製心電圖 QRS 波形圖案
  - 高光效果: 頂部白色高光條
- **光暈**: `shadowBlur: 15, rgba(255, 60, 60, 0.3-0.5)`

#### 障礙物 (Obstacles)
- **造型**: 三角尖刺（從基線向上/下延伸）
- **顏色**: 綠色漸層 (#0f0 → #0d0 → #0a0)
- **動畫效果**:
  - 脈衝光暈: 隨機相位偏移的呼吸動畫
  - 邊緣高光: 白綠色描邊
- **光暈**: `shadowBlur: 12, rgba(0, 255, 0, 0.4-0.7)`

#### 視覺風格
- **主題**: 心電圖監視器風格
- **配色**:
  - 背景: 深色黑綠漸層
  - 基線: 綠色 (#0f0)
  - 玩家: 紅色（心跳）
  - 障礙物: 綠色（ECG 尖峰）

### 5. 配置文件更新
**檔案**: `src/config.py`

```python
# 指令列表
COMMANDS = ['START', 'PAUSE', 'JUMP', 'FLIP']

# 中英文指令映射
COMMAND_MAPPING = {
    '開始': 'START',
    'start': 'START',
    '暫停': 'PAUSE',
    'pause': 'PAUSE',
    '跳': 'JUMP',
    'jump': 'JUMP',
    '翻': 'FLIP',
    'flip': 'FLIP',
}
```

**檔案**: `src/audio/controller.py`

```python
COMMAND_TO_ACTION = {
    'START': 'START',
    'PAUSE': 'PAUSE',
    'JUMP': 'JUMP',
    'FLIP': 'FLIP',
}
```

### 6. README 更新
**檔案**: `README.md`

- 更新專案目標（4 個指令 + ECG 主題美術）
- 新增遊戲控制表格（包含 FLIP 指令）
- 新增 ECG 主題視覺設計說明
- 新增語音模板管理章節（中英文檔名規則）
- 更新指令對應表

## 🎮 使用說明

### 語音指令
1. **開始** - "開始" 或 "START"
2. **跳躍** - "跳" 或 "JUMP"
3. **翻轉** - "翻" 或 "FLIP"
4. **暫停** - "暫停" 或 "PAUSE"

### 鍵盤控制
- `Enter`: 開始遊戲
- `↑`: 跳躍
- `↓`: 翻轉到另一側
- `Space`: 暫停/繼續

## 📁 修改的檔案清單

1. `src/config.py` - 更新指令配置
2. `src/audio/controller.py` - 更新指令映射
3. `src/audio/io.py` - 優化音檔載入邏輯
4. `src/game/templates/index.html` - 實作 FLIP 功能 + ECG 美術設計
5. `README.md` - 更新文檔

## ✅ 測試建議

1. **語音識別測試**:
   ```bash
   python tests/test_live.py
   ```
   測試所有 4 個指令的識別率

2. **遊戲功能測試**:
   ```bash
   python app.py
   ```
   - 測試 FLIP 功能是否正確翻轉
   - 測試 ECG 主題美術是否正常顯示
   - 測試鍵盤快捷鍵（↓ 翻轉）

3. **音檔模板測試**:
   - 測試中文檔名（開始.wav, 跳.wav, 翻.wav, 暫停.wav）
   - 測試英文檔名（START_XX.wav, JUMP_XX.wav, FLIP_XX.wav, PAUSE_XX.wav）
   - 測試大小寫混合檔名

## 🔮 未來優化建議

1. **FLIP 動畫效果**: 可以加入翻轉過渡動畫
2. **音檔模板**: 為 FLIP 指令錄製更多語音樣本
3. **視覺效果**: 可以加入粒子效果或軌跡特效
4. **難度調整**: 根據 FLIP 功能調整障礙物生成邏輯
