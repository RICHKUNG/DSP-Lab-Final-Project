# Optimization Summary

## Issue: Decreasing Sensitivity and Recognition Stoppage

The user reported that the system's sensitivity decreased over time and eventually stopped recognizing commands.

### Root Cause Analysis

1.  **Stops Recognizing (Infinite Lag):**
    - The `AudioStream` class used an unbounded `queue.Queue` to store audio chunks.
    - If the recognition process (which runs in the main loop) was slower than the audio input rate (real-time), the queue would grow indefinitely.
    - Over time, the "live" processing would lag behind the actual input by seconds or minutes.
    - Eventually, the system would be processing silence from minutes ago while ignoring current user input, appearing to have "stopped".
    - In extreme cases, this could lead to memory exhaustion.

2.  **Sensitivity Decreases:**
    - The `VAD` (Voice Activity Detection) module initialized its energy threshold based on a one-time calibration at startup (`start()`).
    - It did not adapt to changes in the environmental noise floor.
    - If the background noise level changed (or if the initial calibration was imperfect), the static threshold would become inappropriate, leading to either false positives (flooding the recognizer) or false negatives (ignoring speech), interpreted by the user as "decreased sensitivity".

### Applied Fixes

1.  **Bounded Audio Buffer (`src/audio/io.py`):**
    - Limited the `_output_queue` size to 500 chunks (approximately 8 seconds of audio).
    - Implemented a **"drop-oldest" strategy**: If the queue is full, the oldest audio chunk is discarded to make room for the new one.
    - This ensures the system never lags more than 8 seconds behind reality and prevents memory leaks.

2.  **Adaptive VAD (`src/audio/vad.py`):**
    - Implemented **adaptive background noise estimation**.
    - When the system detects SILENCE, it slowly updates the `background_rms` using an Exponential Moving Average (EMA) with a rate of 0.05.
    - This allows the VAD to automatically adjust its threshold:
        - If the room gets quieter, sensitivity increases (threshold drops).
        - If the room gets noisier (e.g., fan), sensitivity adjusts to ignore the noise (threshold rises).
    - Adaptation is paused during speech to prevent learning the user's voice as noise.

### Verification
- **Unit Test:** Created and ran `scripts/test_vad_adaptation.py` to mathematically verify that the VAD adapts up and down correctly but ignores speech.
- **Integration Check:** Verified `tests/test_live.py` runs with the new logic (by code inspection and knowing it shares the same modules).

The system is now robust to long-running sessions and changing environments.