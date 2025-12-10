# Documentation Directory

This directory contains comprehensive documentation for the Bio-Voice Commander project.

## 📚 Main Documents

### Performance & Optimization
- **[OPTIMIZATION_SUMMARY.md](OPTIMIZATION_SUMMARY.md)** - Complete optimization history (700ms → 186ms)
- **[EXPERIMENT_NOISE_ROBUSTNESS.md](EXPERIMENT_NOISE_ROBUSTNESS.md)** ⭐ **NEW** - Latest experiment results (2025-12-10)
  - DTW_RADIUS optimization (2→3): +5.7% accuracy, -14% latency
  - Threshold validation
  - Noise robustness analysis
- **[exp_fast_1.md](exp_fast_1.md)** - FastLPCMatcher experiment (2x speedup)
- **[exp_fast_2.md](exp_fast_2.md)** - DTW Radius experiment (1.5x speedup)
- **[exp_log.md](exp_log.md)** - Other optimization experiments

### Testing & Analysis
- **[BENCHMARK_GUIDE.md](BENCHMARK_GUIDE.md)** - Testing system guide (arena, QA, analysis tools)
- **[ACCURACY_ANALYSIS.md](ACCURACY_ANALYSIS.md)** - Accuracy analysis and improvement suggestions

## 🗂️ Archive

Historical experiment plans and deprecated documents are stored in `archive/`:
- `experiment_plan_20251210.md` - Noise robustness experiment plan

## 📊 Latest Performance (2025-12-10)

**Configuration**:
```python
DTW_RADIUS = 3              # Optimized from 2
THRESHOLD_MFCC_DTW = 140.0  # Validated
```

**Results**:
| Metric | Value | Change from Baseline |
|--------|-------|---------------------|
| Overall Accuracy | **85.7%** | +5.7% ✅ |
| Clean Accuracy | **93%** | +6.3% ✅ |
| Processing Time | **186ms** | -14% ✅ |
| Noise 20dB | 79% | +12.3% ✅ |
| Noise 10dB | 57% | -3% ⚠️ |

## 🔬 Experiment Methodology

All experiments follow a systematic approach:
1. **Baseline Measurement** - Record current performance
2. **Hypothesis Formation** - Identify optimization target
3. **Controlled Testing** - Change one variable at a time
4. **Arena Validation** - Test with Leave-One-Out methodology
5. **Documentation** - Archive results in JSON format
6. **Analysis** - Compare via `temp/view_history.py`

## 🎯 Future Work

Based on [EXPERIMENT_NOISE_ROBUSTNESS.md](EXPERIMENT_NOISE_ROBUSTNESS.md):

**High Priority**:
- Template quality audit (use `temp/find_bad_templates.py`)
- Re-record poor templates (especially 開始.wav)

**Medium Priority**:
- Test RASTA-PLP features (more noise-robust)
- Spectral subtraction preprocessing

**Low Priority**:
- Ensemble weight tuning for noisy conditions
- Confidence-based fallback mechanisms

## 📝 Document Index

```
docs/
├── README.md                          # This file
├── OPTIMIZATION_SUMMARY.md            # Complete optimization history
├── EXPERIMENT_NOISE_ROBUSTNESS.md     # Latest experiments (2025-12-10) ⭐
├── ACCURACY_ANALYSIS.md               # Accuracy improvement guide
├── BENCHMARK_GUIDE.md                 # Testing system documentation
├── exp_fast_1.md                      # FastLPC experiment
├── exp_fast_2.md                      # DTW Radius experiment
├── exp_log.md                         # Misc experiments
└── archive/                           # Historical documents
    └── experiment_plan_20251210.md    # Experiment planning doc
```

---

*Last Updated: 2025-12-10*
*Maintainer: Bio-Voice Commander Development Team*
