# Bio-Voice Commander & ECG Pulse Runner - Project Context

## 1. Project Overview
**Bio-Voice Commander** is a Digital Signal Processing (DSP) final project that integrates voice control and ECG (Electrocardiogram) signals to control an interactive game.

*   **Core Logic:** The system uses a **Speaker-Independent** voice recognition engine to detect commands (`START`, `PAUSE`, `JUMP`, `MAGNET`, `INVERT`) and an ECG signal processor to generate game obstacles based on heart rate.
*   **Key Goal:** Robustness. The system is designed to work under challenging conditions (0dB noise, speed variations, pitch shifts).
*   **Status:** Production Ready (97.9% accuracy in adaptive ensemble mode).

## 2. System Architecture
The system follows a modular, event-driven architecture centered around a **Central Event Bus**.

### 2.1. Event Bus (`src/event_bus.py`)
*   Acts as the central nervous system.
*   Decouples the `Audio`, `ECG`, and `Game` modules.
*   **Key Events:** `VOICE_COMMAND`, `ECG_PEAK`, `GAME_START`.

### 2.2. Audio Module (`src/audio/`)
*   **VAD (Voice Activity Detection):** Detects speech segments to trigger recognition.
*   **Recognition Engine (`src/audio/recognizers.py`):**
    *   **Adaptive Ensemble:** Combines multiple algorithms (`MFCC+DTW`, `Mel+Cosine`, `LPC+Euclidean`, `RASTA-PLP`).
    *   **Dynamic Weighting:** Adjusts algorithm weights based on real-time SNR (Signal-to-Noise Ratio).
    *   **Templates:** Uses pre-recorded command templates stored in `cmd_templates/`.

### 2.3. ECG Module (`src/ecg/`)
*   Reads serial data from an Arduino-based ECG sensor.
*   Performs real-time filtering and R-peak detection.
*   Falls back to a **Simulator** if no hardware is detected.

### 2.4. Game Server (`src/game/`)
*   **Tech Stack:** Flask + Flask-SocketIO.
*   Serves the web-based game client.
*   Translates EventBus events into SocketIO messages for the frontend.

## 3. Key Files & Directories

| File/Directory | Description |
| :--- | :--- |
| `app.py` | **Entry Point**. Initializes all modules and starts the server. |
| `src/config.py` | **Configuration**. Global settings for audio (sample rate, thresholds), VAD, and game logic. |
| `src/event_bus.py` | **Event System**. Thread-safe singleton for inter-module communication. |
| `src/audio/recognizers.py` | **Core Logic**. Implementation of the Adaptive Ensemble recognizer. |
| `cmd_templates/` | **Data**. Reference audio files for voice commands. |
| `tests/` | **Validation**. Comprehensive test suite (Live, Arena, Unit tests). |
| `docs/` | **Documentation**. Detailed experiment logs (`exp_log.md`) and roadmaps. |

## 4. Setup & Usage

### 4.1. Installation
The project requires Python 3.10.

```bash
# Recommended: Create a conda environment
conda create -n dspfp python=3.10 -y
conda activate dspfp

# Install dependencies
pip install -r requirements.txt
```

### 4.2. Running the System
```bash
# Start the full system (Audio + ECG + Game)
python app.py
```
*   The game will automatically open in your default browser at `http://localhost:5000`.

### 4.3. Testing & Benchmarking
*   **Live Test (Microphone):** `python tests/test_live.py`
*   **Performance Benchmark (Arena):** `python tests/test_arena.py --mode adaptive_ensemble`
*   **File Test:** `python app.py --test path/to/audio.wav`

## 5. Development Guidelines
*   **Conventions:** Follow existing Python style (PEP 8).
*   **Event-Driven:** Do not couple modules directly. Always use the `EventBus` for cross-module actions.
*   **Performance:** The audio processing loop is time-critical. Avoid blocking operations in the audio thread.
*   **Validation:** Before committing changes to the audio engine, run `tests/test_arena.py` to ensure accuracy hasn't regressed.
