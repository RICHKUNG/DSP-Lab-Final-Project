"""Arena test for distorting templates and matching against the remaining set."""

print("Starting Arena Test...")
import sys
import os
import time
import numpy as np
import glob
import librosa
from typing import Dict, List, Tuple

# Ensure src is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from src.audio_io import load_audio_file
    from src.recognizers import MultiMethodMatcher
    from src import config
    print("Imports successful.")
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

# Rates to test
TEST_SUITES = {
    'Speed': [0.7, 0.9, 1.0, 1.1, 1.3],
    'Pitch': [-2.5, -1.0, 0.0, 1.0, 2.5], # Semitones
    'Noise': [100, 25, 20, 15, 10],      # SNR (dB) - 100 means effectively clean
    'Volume': [0.3, 0.6, 1.0, 1.5, 3.0]
}

def apply_augmentation(audio: np.ndarray, type: str, value: float) -> np.ndarray:
    """Apply specific augmentation to audio."""
    # Convert to float32 for processing
    y_float = audio.astype(np.float32) / 32768.0
    
    if type == 'Speed':
        if value == 1.0: return audio
        y_aug = librosa.effects.time_stretch(y_float, rate=value)
        
    elif type == 'Pitch':
        if value == 0.0: return audio
        y_aug = librosa.effects.pitch_shift(y_float, sr=config.SAMPLE_RATE, n_steps=value)
        
    elif type == 'Noise':
        if value >= 100: return audio
        # SNR = 10 * log10(P_signal / P_noise)
        # P_noise = P_signal / 10^(SNR/10)
        p_signal = np.mean(y_float ** 2)
        if p_signal == 0: return audio
        
        p_noise = p_signal / (10 ** (value / 10.0))
        noise = np.random.normal(0, np.sqrt(p_noise), len(y_float))
        y_aug = y_float + noise
        
    elif type == 'Volume':
        if value == 1.0: return audio
        y_aug = y_float * value
        
    else:
        return audio

    # Clip and convert back to int16
    y_aug = np.clip(y_aug, -1.0, 1.0)
    return (y_aug * 32767).astype(np.int16)

def get_label_from_filename(filename: str) -> str:
    """Extract command label from filename."""
    fname = os.path.basename(filename)
    for cn, en in config.COMMAND_MAPPING.items():
        if cn in fname:
            return en
    return "UNKNOWN"

class ArenaResult:
    def __init__(self):
        self.total = 0
        self.correct = 0
        self.wrong_command = 0 # Predicted wrong command
        self.no_match = 0      # Predicted NONE (rejection)
        self.noise = 0         # Predicted NOISE

    def update(self, expected: str, predicted: str):
        self.total += 1
        if predicted == expected:
            self.correct += 1
        elif predicted == 'NONE':
            self.no_match += 1
        elif predicted == 'NOISE':
            self.noise += 1
        else:
            self.wrong_command += 1

    def accuracy(self) -> float:
        return self.correct / self.total if self.total > 0 else 0.0

    def __repr__(self):
        return f"Acc: {self.accuracy()*100:5.1f}% (C:{self.correct} W:{self.wrong_command} N:{self.no_match})"

def run_arena():
    print("=" * 70)
    print("Bio-Voice Commander - Advanced Arena Test")
    print("   Suites: Speed, Pitch, Noise, Volume")
    print("=" * 70)

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_dir = os.path.join(base_dir, "cmd_templates")
    
    # 1. Gather all template files
    all_files = sorted(glob.glob(os.path.join(template_dir, "*.*")))
    valid_files = []
    
    # Filter out non-audio or unknowns if any (and noise files if we treat them separately)
    # The load_templates logic handles noise/unknowns, but here we want explicit control
    for f in all_files:
        if get_label_from_filename(f) != "UNKNOWN" and 'noise' not in os.path.basename(f).lower():
            valid_files.append(f)

    print(f"Found {len(valid_files)} valid command templates.")

    # Stats: Suite -> Method -> Value -> ArenaResult
    # Structure: stats[suite_name][method_name][test_value] = ArenaResult
    methods = ['mfcc_dtw', 'stats', 'mel', 'lpc', 'ensemble']
    stats = {}
    
    # Time stats: Suite -> Value -> List[float]
    time_stats = {}
    
    for suite in TEST_SUITES:
        stats[suite] = {}
        time_stats[suite] = {}
        for val in TEST_SUITES[suite]:
            time_stats[suite][val] = []
            for m in methods:
                stats[suite][m] = {val: ArenaResult() for val in TEST_SUITES[suite]}

    # 2. Leave-One-Out Loop
    for idx, test_file in enumerate(valid_files):
        test_filename = os.path.basename(test_file)
        expected_label = get_label_from_filename(test_file)
        
        print(f"\n[{idx+1}/{len(valid_files)}] Testing: {test_filename} ({expected_label})")
        
        # Load audio once
        try:
            original_audio = load_audio_file(test_file)
        except Exception as e:
            print(f"  Error loading {test_filename}: {e}")
            continue

        # Prepare Matcher with REMAINING templates
        matcher = MultiMethodMatcher()
        
        # Manually load other templates
        # We need to mimic matcher.load_templates_from_dir but skip test_file
        train_count = 0
        for train_file in valid_files:
            if train_file == test_file:
                continue
            
            lbl = get_label_from_filename(train_file)
            try:
                # We need to re-load audio for training templates
                # (Optimization: could cache this, but dataset is small)
                audio_t = load_audio_file(train_file)
                matcher.add_template(lbl, audio_t, os.path.basename(train_file))
                train_count += 1
            except:
                pass
        
        if train_count == 0:
            print("  [Warning] No training templates available! Skipping.")
            continue

        # 3. Run Test Suites
        for suite_name, test_values in TEST_SUITES.items():
            # print(f"  > Suite: {suite_name}")
            for val in test_values:
                # Augment
                input_audio = apply_augmentation(original_audio, suite_name, val)
                
                # Recognize
                t0 = time.time()
                results = matcher.recognize(input_audio, mode='all')
                dt_ms = (time.time() - t0) * 1000
                
                # Print real-time check (only for standard conditions to avoid clutter, or all?)
                # User asked for "Every time", so we print every time but compact.
                # Format: [Speed 1.0x] Predicted: JUMP (23ms)
                ensemble_pred = results['command']
                match_mark = "✓" if ensemble_pred == expected_label else "✗"
                label_val = f"{val:g}"
                print(f"    [{suite_name} {label_val:>4}] {ensemble_pred:8s} {match_mark} ({dt_ms:.0f}ms)")
                
                # Record Stats
                time_stats[suite_name][val].append(dt_ms)
                
                stats[suite_name]['ensemble'][val].update(expected_label, ensemble_pred)
                
                # Record Individuals
                for method in methods:
                    if method == 'ensemble': continue
                    pred = results['all_results'][method]['command']
                    stats[suite_name][method][val].update(expected_label, pred)

    # 4. Report
    print("\n" + "=" * 80)
    print("ARENA RESULTS SUMMARY")
    print("=" * 80)
    
    overall_scores = {m: 0.0 for m in methods}
    total_scenarios = 0

    for suite_name, test_values in TEST_SUITES.items():
        print(f"\n>> {suite_name.upper()} ROBUSTNESS")
        
        # Header
        header = f"{{'Method':<12}} |";
        for val in test_values:
            label = f"{val:g}"
            if suite_name == 'Speed': label += 'x'
            elif suite_name == 'Pitch': label = f"{val:+}st"
            elif suite_name == 'Noise': label += 'dB'
            elif suite_name == 'Volume': label += 'x'
            header += f" {label:>7} |"
        print(header)
        print("-" * len(header))

        for method in methods:
            row = f"{method:<12} |"
            suite_acc_sum = 0.0
            for val in test_values:
                res = stats[suite_name][method][val]
                acc = res.accuracy()
                suite_acc_sum += acc
                row += f" {acc*100:6.0f}% |"
            print(row)
            
            # Add to overall
            overall_scores[method] += suite_acc_sum
            
        # Time Stats
        print(f"{{'Avg Time':<12}} |", end="")
        for val in test_values:
             times = time_stats[suite_name][val]
             avg_t = sum(times)/len(times) if times else 0
             print(f" {avg_t:4.0f}ms  |", end="")
        print()

    print("\n" + "=" * 80)
    print("PROPOSED IMPROVEMENTS")
    print("=" * 80)
    
    # Analyze Overall
    best_method = max(overall_scores, key=overall_scores.get)
    best_avg = overall_scores[best_method] / total_scenarios
    print(f"Best Overall Method: {best_method} (Avg Acc: {best_avg*100:.1f}%)")
    
    proposals = []
    
    # Noise check
    noise_drops = {}
    for method in methods:
        clean = stats['Noise'][method][100].accuracy()
        noisy = stats['Noise'][method][10].accuracy()
        noise_drops[method] = clean - noisy
    
    worst_noise_method = max(noise_drops, key=noise_drops.get)
    if noise_drops[worst_noise_method] > 0.4:
         proposals.append(f"- {worst_noise_method} fails in noise (drop {noise_drops[worst_noise_method]*100:.0f}%). Decrease its weight in noisy conditions.")

    # Volume check
    vol_stats = stats['Volume']['ensemble']
    low_vol = vol_stats[0.3].accuracy()
    if low_vol < 0.6:
        proposals.append(f"- Low volume performance is poor ({low_vol*100:.0f}%). Implement normalization/AGC.")

    # Pitch check
    pitch_stats = stats['Pitch']['ensemble']
    pitch_var = pitch_stats[-2.5].accuracy()
    if pitch_var < 0.7:
        proposals.append("- Pitch shifting degrades performance. Consider adding pitch-augmented templates.")

    for p in proposals:
        print(p)
    
    if not proposals:
        print("System appears robust across all tested dimensions!")

if __name__ == '__main__':
    run_arena()
