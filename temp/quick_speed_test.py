"""Quick speed test after DTW radius optimization."""
import sys
import os
import time
import numpy as np
import glob

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.audio_io import load_audio_file
from src.recognizers import MultiMethodMatcher
from src import config

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
template_dir = os.path.join(base_dir, "cmd_templates")

print(f"Current DTW_RADIUS: {config.DTW_RADIUS}")
print()

# Load matcher
print("Loading templates...")
matcher = MultiMethodMatcher()
matcher.load_templates_from_dir(base_dir)

# Get test files
test_files = sorted(glob.glob(os.path.join(template_dir, "*.wav")))[:5]

# Warmup
test_audio = load_audio_file(test_files[0])
for _ in range(2):
    matcher.recognize(test_audio)

# Quick test
print("\nQuick speed test:")
latencies = []

for test_file in test_files:
    audio = load_audio_file(test_file)

    start = time.perf_counter()
    result = matcher.recognize(audio, mode='best')
    elapsed = (time.perf_counter() - start) * 1000
    latencies.append(elapsed)

    fname = os.path.basename(test_file)
    print(f"  {fname:20s} {elapsed:>6.1f}ms -> {result['command']}")

print()
print(f"Mean latency: {np.mean(latencies):.1f}ms")
print(f"Target: <250ms (after radius=3 optimization)")
