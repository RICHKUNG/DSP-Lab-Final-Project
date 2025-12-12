# Bio-Voice Commander: Testing & Benchmarking Guide

This guide details the tools and procedures for validating system performance.

---

## 1. The Arena System
The "Arena" is our comprehensive benchmarking suite. It tests the system against a battery of recorded audio files modified with various distortions.

### Running a Benchmark
```bash
python temp/test_file_input.py
```
This runs the **Leave-One-Out** cross-validation test.
- **Input**: All WAV files in `cmd_templates/`
- **Distortions Applied**:
    -   **Speed**: 0.7x, 0.9x, 1.1x, 1.3x
    -   **Pitch**: -2.5st, -1.0st, +1.0st, +2.5st
    -   **Noise**: 100dB (Clean), 25dB, 20dB, 15dB, 10dB (White Noise)
    -   **Volume**: 0.3x, 3.0x
- **Output**: JSON report in `record/arena_YYYYMMDD_HHMMSS.json`

### Viewing Results
Use the history viewer to compare runs:
```bash
python temp/view_history.py
```
Commands inside the viewer:
- `compare <ID1> <ID2>`: Diff two runs.
- `detail <ID>`: Show full stats for a run.

---

## 2. Testing Tools

### Development Tools
| Script | Purpose |
|--------|---------|
| `temp/quick_speed_test.py` | Measures average latency (ms) for the current config. |
| `temp/profile_latency.py` | Detailed breakdown of processing time (MFCC vs DTW vs VAD). |
| `temp/analyze_failures.py` | Summarizes which files/conditions fail most often in recent logs. |
| `temp/find_bad_templates.py` | Identifies templates that are consistently misrecognized (Self-Match test). |
| `temp/record_garbage.py` | Utility to record background noise for "Noise" templates. |
| `temp/check_audio_devices.py` | Lists available microphones and their supported sample rates. |

### End-to-End Tests
| Script | Purpose |
|--------|---------|
| `tests/test_live.py` | Live microphone test. Shows recognized command and confidence. |
| `tests/test_arena.py` | (Legacy) CLI wrapper for the arena system. |
| `tests/test_calibration_mode.py` | Tests the voice calibration workflow. |

---

## 3. Benchmarking Workflow

### Routine Check (After minor code changes)
1.  Run `quick_speed_test.py` to ensure no latency regression.
2.  Run `test_live.py` and speak a few commands to ensure basic functionality.

### Optimization Validation (After algorithm changes)
1.  Run `test_file_input.py` (The Arena).
2.  Open `view_history.py`.
3.  Compare the new run with the previous "Best" run.
4.  Check:
    -   Did **Accuracy** drop? (Check specific conditions like Noise 10dB).
    -   Did **Latency** improve?
    -   Did **Clean Accuracy** stay 100%?

### Debugging Accuracy Issues
1.  Run `analyze_failures.py`.
2.  If a specific command is failing (e.g., "START"):
    -   Run `find_bad_templates.py`.
    -   If "Start1.wav" has low self-match score, delete or re-record it.
3.  If a specific condition is failing (e.g., Noise 10dB):
    -   Consider adjusting weights in `AdaptiveEnsemble`.
    -   Check if `SpectralSubtraction` is enabled.

---

## 4. JSON Report Format
The Arena output JSON contains:
-   **Config**: All `src/config.py` settings at runtime.
-   **Overall Scores**: Aggregate accuracy per method.
-   **Suites**: Detailed breakdown by condition (Noise, Speed, etc.).

Example:
```json
"overall_scores": {
    "adaptive_ensemble": {
        "average_accuracy": 0.979
    }
}
```
