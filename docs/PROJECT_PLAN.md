# Bio-Voice Commander: Project Plan & Roadmap

This document outlines the project's development roadmap, completed milestones, and future goals.

---

## 📅 Roadmap Status

### ✅ Completed
-   **Core System**: VAD, MFCC/Mel/LPC Features, DTW/Euclidean/Cosine Matchers.
-   **Architecture**: EventBus, Flask Game Server, Modular Audio Controller.
-   **Optimization**:
    -   FastLPC (Resizing) implementation.
    -   DTW Radius tuning (Radius=3).
    -   Latency reduced to <200ms.
-   **Robustness**:
    -   Adaptive Ensemble (SNR-based weighting).
    -   Spectral Subtraction for 0dB noise support.
    -   Adaptive VAD for changing environments.
-   **Tooling**: Comprehensive "Arena" benchmark suite.

### 🚧 In Progress / Maintenance
-   **Template Quality**: Ongoing audit of recording quality.
-   **Documentation**: Consolidating dispersed docs (This task).

### 🔮 Future Goals (Post-Project)
-   **Advanced Features**:
    -   RASTA-PLP integration (Code exists, needs tuning).
    -   Deep Learning (CNN/RNN) for Keyword Spotting (KWS).
-   **Hardware**:
    -   Port to ESP32 (MicroPython or C).
    -   Hardware-accelerated FFT.

---

## 🧪 Experiment Plan (Archive)

### Phase 1: Baseline Establishment
-   **Goal**: Measure current accuracy and latency.
-   **Result**: MFCC baseline established at ~80% accuracy, 700ms latency.

### Phase 2: Latency Reduction
-   **Hypothesis**: LPC calculation is the bottleneck.
-   **Experiment**: Downsample LPC features to fixed length.
-   **Result**: Validated. Latency dropped significantly.

### Phase 3: Noise Robustness
-   **Hypothesis**: MFCC fails in noise; Mel/LPC should help.
-   **Experiment**: Test Ensemble in 10-25dB SNR.
-   **Result**: Validated. Ensemble maintained >70% accuracy where MFCC dropped to <60%.

### Phase 4: Extreme Stress Test
-   **Goal**: Find the breaking point.
-   **Result**: System breaks at -5dB SNR (Noise louder than signal).

---

## 📋 Todo List (Maintenance)

- [ ] Audit `cmd_templates/` for silent or clipped files.
- [ ] Add `Magnet` and `Invert` voice commands to the game.
- [ ] Add unit tests for `EventBus`.
- [ ] Create a Dockerfile for easy deployment.
