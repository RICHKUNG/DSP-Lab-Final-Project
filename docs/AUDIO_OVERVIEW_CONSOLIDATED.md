# Bio-Voice Commander 音訊系統總覽（初學者友善版）

整理現有的音訊相關說明與實驗結果，快速掌握系統原理、方法比較、關鍵數據與操作建議。對應原始資料：`docs/ACCURACY_ANALYSIS.md`, `docs/EXPERIMENT_NOISE_ROBUSTNESS.md`, `docs/COMPARISON_MFCC_VS_ENSEMBLE.md`, `docs/EXPERIMENT_ADAPTIVE_ENSEMBLE.md`, `docs/EXTREME_TEST_REPORT_AFTER_FIX.md`, `docs/BUG_FIX_REPORT_SNR.md`, `docs/EXPERIMENT_ROADMAP.md`, `docs/EXPERIMENT_SUMMARY.md`, `docs/FINAL_EXPERIMENT_REPORT.md`, `docs/exp_fast_*.md`, `docs/exp_log.md`, `docs/AUDIO_TROUBLESHOOTING.md`。

---

## 系統概觀（流程與安全網）
- **音源輸入**：PyAudio 讀取麥克風。`AudioStream` 以**有界佇列**儲存（約 8 秒），滿載時丟棄最舊資料，避免長時間延遲與記憶體暴衝（參考 `OPTIMIZATION_SUMMARY_FINAL.md`）。
- **VAD（語音活動偵測）**：啟動時校正背景噪聲，之後持續以 EMA 自動調整底噪門檻，減少「忽然變吵/變安靜」導致的靈敏度飄移。
- **特徵抽取與比對**：同一段音訊共用 MFCC、Mel、LPC 特徵，分別送入各 matcher；核心比對法為 DTW 或固定長度距離。
- **決策**：可選單一路徑（MFCC only）、固定加權 Ensemble、或依 SNR 自動切換權重的 Adaptive Ensemble。

---

## 方法原理與優缺點

### MFCC + DTW（核心基準）
- **做法**：13 維 MFCC + Delta/Delta-Delta，使用 Sakoe-Chiba 限制的 DTW；最佳半徑 `DTW_RADIUS=3`（測得 186ms，準確率 85.7%，見 `EXPERIMENT_NOISE_ROBUSTNESS.md`）。
- **優點**：在乾淨與一般環境準確、速度快（~169ms，見 `COMPARISON_MFCC_VS_ENSEMBLE.md`）。
- **缺點**：對高噪聲較敏感（10dB 噪聲 ~64%）。

### Mel 範本（噪聲穩定）
- **做法**：Mel-Spectrogram 取樣後以餘弦距離比對。
- **優點**：對噪聲/速度/音高變化穩定（10dB 不掉分；`insight.md`、`EXPERIMENT_NOISE_ROBUSTNESS.md`）。
- **缺點**：乾淨環境下準確率略低於 MFCC，單獨使用速度略慢於 MFCC。

### LPC / LPCC（頻譜包絡）
- **做法**：以 LPC 12 階特徵。為降延遲，`FastLPCMatcher` 將序列重採樣為固定長度並改用歐式距離，取代原本的 LPC+DTW。
- **效果**：總延遲由 ~700ms → **229ms**（`exp_fast_1.md`）；保留噪聲拒斥力。
- **缺點**：極高噪聲下（10dB）仍可能下降，需倚賴 Ensemble 互補。

### 固定加權 Ensemble
- **做法**：多方法投票，典型權重：MFCC 4.0 / Mel 2.5 / LPC 1.0。
- **效果**：比 MFCC only 噪聲穩健（10dB 71% vs 64%，`COMPARISON_MFCC_VS_ENSEMBLE.md`），延遲約多 15–30ms。
- **建議**：一般實務的預設模式，兼顧速度與噪聲。

### Adaptive Ensemble + SNR 感知
- **做法**：估算 SNR 後切換權重（乾淨偏向 MFCC、吵雜偏向 Mel）。最終版搭配**頻譜減法**預處理與 SNR 修正，實測 10dB 可達 93%，0dB 仍有 86%（`FINAL_EXPERIMENT_REPORT.md`, `EXTREME_TEST_REPORT_AFTER_FIX.md`）。
- **注意**：先前的 `estimate_snr` 曾因只看到語音片段而嚴重低估 SNR，已修正為由 VAD 背景能量注入（`BUG_FIX_REPORT_SNR.md`）。若自行呼叫 recognizer，記得提供 `known_snr` 以避免重現舊問題。

### Spectral Subtraction（選配）
- **角色**：在極端噪聲前先行降噪，提升 Adaptive Ensemble 在 0dB、-5dB 場景的穩定度。
- **成本**：增加些許計算；若僅在辦公室/家用可不開。

---

## 實驗里程碑與關鍵數據

### 1) 延遲優化（2025-12-09）
- **動作**：FastLPC + MFCC DTW 半徑縮小。
- **結果**：總延遲 **700ms → 229ms**（無準確率損失）；後續將 DTW 半徑 5→2 → 約 **217ms**（`exp_fast_1.md`, `exp_fast_2.md`）。

### 2) 噪聲穩健度探索（2025-12-10）
- **配置**：`DTW_RADIUS=3`, `THRESHOLD_MFCC_DTW=140.0`。
- **成效**：整體準確率 80.0% → **85.7%**；乾淨 93%；10dB 57%（主要瓶頸：模板品質，見 `EXPERIMENT_NOISE_ROBUSTNESS.md`）。

### 3) MFCC vs Ensemble（2025-12-10）
- **速度**：MFCC ~169ms；Ensemble ~200ms（+15–20%）。
- **噪聲 10dB**：MFCC 64%；Ensemble **71%**。
- **建議**：安靜/低功耗用 MFCC；噪聲場域用 Ensemble（`COMPARISON_MFCC_VS_ENSEMBLE.md`）。

### 4) Adaptive Ensemble / 極限測試（2025-12-10 ~ 12-12）
- **改進**：頻譜減法 + SNR 感知權重；修正 SNR 低估。
- **極限結果**（`FINAL_EXPERIMENT_REPORT.md`, `EXTREME_TEST_REPORT_AFTER_FIX.md`）：
  - 噪聲：10dB **93%**，0dB **86%**，-5dB 71%
  - 速度：0.5–1.0x 100%，1.7x 93%
  - 音高：±5st 86–100%
  - 延遲：約 145–200ms（情境/設定而異；含降噪時可能到 ~270ms，見 `EXPERIMENT_ROADMAP.md`）
- **結論**：需要「吵環境高可靠」時開啟 Adaptive；一般場景用固定 Ensemble 更簡單。

---

## 實務操作與測試
- **快速跑完整基準**：`python temp/test_file_input.py`（Arena Leave-One-Out）。
- **指定方法比較**：`python test_arena.py --method mfcc_dtw|ensemble|adaptive_ensemble`。
- **歷史結果比對**：`python temp/view_history.py`（`compare N M` / `detail N`）。
- **線上端到端試跑**：`python tests/test_live.py`。
- **麥克風問題**：依序檢查 `docs/AUDIO_TROUBLESHOOTING.md`（權限、獨占模式、設備選擇、驅動）。

---

## 配置建議（依環境）
- **安靜/低功耗（筆電、樹莓派）**：`mfcc_dtw`，`DTW_RADIUS=3`，門檻 `THRESHOLD_MFCC_DTW=140.0`。
- **一般/中度噪聲**：固定加權 Ensemble（MFCC 4.0 / Mel 2.5 / LPC 1.0）；同樣 `DTW_RADIUS=3`。
- **高度噪聲或變動場景**：Adaptive Ensemble + 頻譜減法；確認 SNR 注入正確（`known_snr` 來自 VAD 背景能量），權重大致為：
  - 乾淨（>30dB）：MFCC 重
  - 中噪（15–30dB）：MFCC ≈ Mel
  - 高噪（<15dB）：Mel 重

---

## 模板品質與資料面改善
- **找到壞模板**：`python temp/find_bad_templates.py`；重錄 <70% 的檔案，特別是常見問題檔（如早期的無編號模板）。
- **錄製建議**：多說幾次、保持固定距離與音量；每個指令 8–10 份模板較穩。
- **門檻微調**：若單一指令易誤判，可個別調整門檻（例：`START` 拉高門檻避免誤觸）。

---

## 速查表（核心數據）
| 方法 / 場景 | 延遲 | 乾淨 | 10dB 噪聲 | 備註 |
|-------------|------|------|-----------|------|
| MFCC only | ~169ms | 100% | 64% | 低功耗/安靜 |
| 固定 Ensemble | ~200ms | 100% | 71% | 噪聲略佳 |
| Ensemble（DTW_RADIUS=3, 最佳化） | 186ms | 93% | 57% | `EXPERIMENT_NOISE_ROBUSTNESS.md` |
| FastLPC + DTW 半徑縮小 | ~217ms | 100% | 100%（小樣本） | `exp_fast_1/2.md` |
| Adaptive + 頻譜減法 | 145–200ms（部分情境 ~270ms） | 100% | 93% | 0dB 86%，-5dB 71% |

---

## 快速決策建議
1. **要快且安靜**：用 MFCC only。
2. **要穩且簡單**：用固定 Ensemble，`DTW_RADIUS=3`，門檻 140。
3. **要撐住吵環境**：開 Adaptive + 頻譜減法；確保 SNR 修正路徑。
4. **準確率掉到 70% 以下**：先檢查模板品質，再看門檻/權重；不要只調參數。
5. **麥克風抓不到**：照 `AUDIO_TROUBLESHOOTING.md` 的權限與設備步驟排查。

---

*維護者：Bio-Voice Commander 團隊（整理：2025-12-12）。若需更細節，請開啟對應原始檔查詢。*
