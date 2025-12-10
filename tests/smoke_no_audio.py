"""
Lightweight smoke test that exercises the matcher without touching audio hardware.

Run with:
    python tests/smoke_no_audio.py
"""

import os
import sys
import numpy as np

# Ensure project root on path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.recognizers import MultiMethodMatcher


def run():
    sr = 16000
    duration_sec = 0.5
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    # Simple synthetic tone to serve as a "template" and a slightly shifted query
    template_audio = 0.2 * np.sin(2 * np.pi * 440 * t)
    query_audio = 0.2 * np.sin(2 * np.pi * 442 * t)

    matcher = MultiMethodMatcher(methods=["mfcc_dtw", "mel", "lpc"])
    matcher.add_template("START", template_audio, "synthetic_template.wav")
    matcher.add_noise_template(np.zeros_like(template_audio))

    result = matcher.recognize(query_audio, adaptive=True, mode="best")
    print("Smoke test result:", result)


if __name__ == "__main__":
    run()
