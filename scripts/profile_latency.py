"""Profile detailed latency breakdown."""
import sys
import os
import time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.audio_io import load_audio_file
from src.recognizers import MultiMethodMatcher
from src.vad import preprocess_audio
from src.features import extract_mfcc, extract_mel_template, extract_lpc_features
from src import

# Ensure the project root is in the Python path for module imports
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_current_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
 config

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
template_dir = os.path.join(base_dir, "cmd_templates")

# Load matcher
print("Loading templates...")
matcher = MultiMethodMatcher()
matcher.load_templates_from_dir(base_dir)

# Load test audio
test_file = os.path.join(template_dir, "開始1.wav")
audio = load_audio_file(test_file)

print(f"Test file: 開始1.wav")
print(f"Audio length: {len(audio)/config.SAMPLE_RATE:.2f}s")
print()

# Warmup
for _ in range(3):
    matcher.recognize(audio)

n_runs = 20

# Profile individual components
print("=" * 60)
print("LATENCY BREAKDOWN (mean of {} runs)".format(n_runs))
print("=" * 60)

# 1. VAD preprocessing
times = []
for _ in range(n_runs):
    start = time.perf_counter()
    processed = preprocess_audio(audio)
    times.append((time.perf_counter() - start) * 1000)
print(f"VAD preprocessing:     {np.mean(times):>6.1f}ms")

processed = preprocess_audio(audio)

# 2. MFCC extraction
times = []
for _ in range(n_runs):
    start = time.perf_counter()
    _ = extract_mfcc(processed)
    times.append((time.perf_counter() - start) * 1000)
mfcc_time = np.mean(times)
print(f"MFCC extraction:       {mfcc_time:>6.1f}ms")

# 3. Mel extraction
times = []
for _ in range(n_runs):
    start = time.perf_counter()
    _ = extract_mel_template(processed)
    times.append((time.perf_counter() - start) * 1000)
mel_time = np.mean(times)
print(f"Mel extraction:        {mel_time:>6.1f}ms")

# 4. LPC extraction
times = []
for _ in range(n_runs):
    start = time.perf_counter()
    _ = extract_lpc_features(processed)
    times.append((time.perf_counter() - start) * 1000)
lpc_time = np.mean(times)
print(f"LPC extraction:        {lpc_time:>6.1f}ms")

# 5. Individual matcher recognition
mfcc_feats = extract_mfcc(processed)
mel_feats = extract_mel_template(processed)

# MFCC matching
times = []
for _ in range(n_runs):
    start = time.perf_counter()
    _ = matcher.matchers['mfcc_dtw'].recognize(audio, features=mfcc_feats)
    times.append((time.perf_counter() - start) * 1000)
mfcc_match_time = np.mean(times)
print(f"MFCC matching (DTW):   {mfcc_match_time:>6.1f}ms")

# Mel matching
times = []
for _ in range(n_runs):
    start = time.perf_counter()
    _ = matcher.matchers['mel'].recognize(audio, features=mel_feats)
    times.append((time.perf_counter() - start) * 1000)
mel_match_time = np.mean(times)
print(f"Mel matching:          {mel_match_time:>6.1f}ms")

# LPC matching (FastLPCMatcher)
times = []
for _ in range(n_runs):
    start = time.perf_counter()
    _ = matcher.matchers['lpc'].recognize(audio)
    times.append((time.perf_counter() - start) * 1000)
lpc_match_time = np.mean(times)
print(f"LPC matching (Fast):   {lpc_match_time:>6.1f}ms")

print()
print("Total estimated:       {:>6.1f}ms".format(
    mfcc_time + mel_time + lpc_time + mfcc_match_time + mel_match_time + lpc_match_time
))

# 6. Full recognition
times = []
for _ in range(n_runs):
    start = time.perf_counter()
    _ = matcher.recognize(audio)
    times.append((time.perf_counter() - start) * 1000)
full_time = np.mean(times)
print(f"Full recognition:      {full_time:>6.1f}ms")

print()
print("=" * 60)
print("BOTTLENECK ANALYSIS")
print("=" * 60)

components = [
    ("MFCC extraction", mfcc_time),
    ("Mel extraction", mel_time),
    ("LPC extraction", lpc_time),
    ("MFCC matching", mfcc_match_time),
    ("Mel matching", mel_match_time),
    ("LPC matching", lpc_match_time),
]

components.sort(key=lambda x: x[1], reverse=True)

total = sum(c[1] for c in components)
for name, t in components:
    pct = (t / total) * 100
    bar = "=" * int(pct / 2)
    print(f"{name:20s} {t:>6.1f}ms {pct:>5.1f}% {bar}")

print()
print("=" * 60)
print("OPTIMIZATION OPPORTUNITIES")
print("=" * 60)

# Calculate potential speedups
print("\nIf we skip Mel method entirely:")
without_mel = full_time - mel_time - mel_match_time
print(f"  Estimated latency: {without_mel:.1f}ms (speedup: {full_time/without_mel:.2f}x)")
print(f"  Risk: Lose noise robustness")

print("\nIf we reduce MFCC DTW radius (5->3):")
estimated_radius3 = full_time - (mfcc_match_time * 0.3)  # ~30% faster
print(f"  Estimated latency: {estimated_radius3:.1f}ms (speedup: {full_time/estimated_radius3:.2f}x)")
print(f"  Risk: Minimal accuracy loss")

print("\nIf we use adaptive mode (skip Mel/LPC when MFCC confident):")
adaptive_time = mfcc_time + mfcc_match_time + 5  # small overhead
print(f"  Fast path latency: {adaptive_time:.1f}ms (speedup: {full_time/adaptive_time:.2f}x)")
print(f"  Full path latency: {full_time:.1f}ms (fallback)")
print(f"  Risk: Depends on confidence threshold tuning")
