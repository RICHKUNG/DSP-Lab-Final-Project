"""Arena test for distorting templates and matching against the remaining set."""

print("Starting Arena Test...")
import sys
import os
import time
import numpy as np
import glob
import librosa
import json
from datetime import datetime
from typing import Dict, List, Tuple

# Ensure src is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from src.audio_io import load_audio_file
    from src.recognizers import MultiMethodMatcher
    from src import

# Ensure the project root is in the Python path for module imports
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_current_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
 config
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

def get_config_snapshot():
    """Capture current configuration parameters."""
    return {
        'audio': {
            'sample_rate': config.SAMPLE_RATE,
            'n_fft': config.N_FFT,
            'hop_length': config.HOP_LENGTH,
            'n_mfcc': config.N_MFCC,
            'n_mels': config.N_MELS,
        },
        'vad': {
            'energy_threshold_mult_low': config.VAD_ENERGY_THRESHOLD_MULT_LOW,
            'energy_threshold_mult_high': config.VAD_ENERGY_THRESHOLD_MULT_HIGH,
            'min_speech_ms': config.VAD_MIN_SPEECH_MS,
            'max_speech_ms': config.VAD_MAX_SPEECH_MS,
        },
        'thresholds': {
            'mfcc_dtw': config.THRESHOLD_MFCC_DTW,
            'mel': config.THRESHOLD_MEL,
            'lpc': config.THRESHOLD_LPC,
            'stats': config.THRESHOLD_STATS,
        },
        'lpc': {
            'order': config.LPC_ORDER,
            'frame_ms': config.LPC_FRAME_MS,
            'hop_ms': config.LPC_HOP_MS,
        }
    }

def save_arena_results(stats, overall_scores, total_scenarios, timestamp_str):
    """Save arena results to JSON file."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    record_dir = os.path.join(base_dir, "record")
    os.makedirs(record_dir, exist_ok=True)

    # Prepare results data
    results = {
        'timestamp': timestamp_str,
        'config': get_config_snapshot(),
        'methods': ['mfcc_dtw', 'mel', 'lpc', 'ensemble'],
        'suites': {},
        'overall_scores': {}
    }

    # Extract suite results
    for suite_name, test_values in TEST_SUITES.items():
        results['suites'][suite_name] = {
            'test_values': test_values,
            'methods': {}
        }

        for method in ['mfcc_dtw', 'mel', 'lpc', 'ensemble']:
            results['suites'][suite_name]['methods'][method] = {}
            for val in test_values:
                res = stats[suite_name][method][val]
                results['suites'][suite_name]['methods'][method][str(val)] = {
                    'accuracy': res.accuracy(),
                    'correct': res.correct,
                    'total': res.total,
                    'wrong_command': res.wrong_command,
                    'no_match': res.no_match,
                    'noise': res.noise
                }

    # Overall scores
    for method in ['mfcc_dtw', 'mel', 'lpc', 'ensemble']:
        avg = overall_scores[method] / total_scenarios if total_scenarios > 0 else 0
        results['overall_scores'][method] = {
            'total_score': overall_scores[method],
            'average_accuracy': avg
        }

    # Save to JSON
    filename = f"arena_{timestamp_str.replace(':', '').replace(' ', '_').replace('-', '')}.json"
    filepath = os.path.join(record_dir, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    return filepath

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

def run_arena():
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    print("=" * 70)
    print("Bio-Voice Commander - Advanced Arena Test")
    print("   Suites: Speed, Pitch, Noise, Volume")
    print(f"   Time: {timestamp}")
    print("=" * 70)

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_dir = os.path.join(base_dir, "cmd_templates")
    
    # 1. Gather all template files
    all_files = sorted(glob.glob(os.path.join(template_dir, "*.*")))
    valid_files = []
    
    for f in all_files:
        if get_label_from_filename(f) != "UNKNOWN" and 'noise' not in os.path.basename(f).lower():
            valid_files.append(f)

    print(f"Found {len(valid_files)} valid command templates.")

    # Stats: Suite -> Method -> Value -> ArenaResult
    # Structure: stats[suite_name][method_name][test_value] = ArenaResult
    methods = ['mfcc_dtw', 'mel', 'lpc', 'ensemble']
    stats = {}
    
    # Time stats: Suite -> Value -> List[float]
    time_stats = {}

    for suite in TEST_SUITES:
        stats[suite] = {}
        time_stats[suite] = {}
        for m in methods:
            stats[suite][m] = {val: ArenaResult() for val in TEST_SUITES[suite]}
        for val in TEST_SUITES[suite]:
             time_stats[suite][val] = []

    # 2. Leave-One-Out Loop
    for idx, test_file in enumerate(valid_files):
        test_filename = os.path.basename(test_file)
        expected_label = get_label_from_filename(test_file)
        
        print(f"\n[{idx+1}/{len(valid_files)}] Testing: {test_filename} ({expected_label})")
        
        try:
            original_audio = load_audio_file(test_file)
        except Exception as e:
            print(f"  Error loading {test_filename}: {e}")
            continue

        matcher = MultiMethodMatcher()
        
        train_count = 0
        for train_file in valid_files:
            if train_file == test_file:
                continue
            
            lbl = get_label_from_filename(train_file)
            try:
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
            for val in test_values:
                # Augment
                input_audio = apply_augmentation(original_audio, suite_name, val)
                
                # Recognize
                t0 = time.time()
                results = matcher.recognize(input_audio, mode='all')
                dt_ms = (time.time() - t0) * 1000
                time_stats[suite_name][val].append(dt_ms)
                
                # Record Ensemble
                ensemble_pred = results['command']
                stats[suite_name]['ensemble'][val].update(expected_label, ensemble_pred)
                
                # Record Individuals
                for method in methods:
                    if method == 'ensemble': continue
                    pred = results['all_results'][method]['command']
                    stats[suite_name][method][val].update(expected_label, pred)
                
                match_mark = "OK" if ensemble_pred == expected_label else "FAIL"
                print(f"    [{suite_name} {val:g}] {ensemble_pred:8s} {match_mark} ({dt_ms:.0f}ms)")

    # 4. Report
    print("\n" + "=" * 80)
    print("ARENA RESULTS SUMMARY")
    print("=" * 80)
    
    overall_scores = {m: 0.0 for m in methods}
    total_scenarios = 0

    for suite_name, test_values in TEST_SUITES.items():
        print(f"\n>> {suite_name.upper()} ROBUSTNESS")
        
        # Header
        header = f"{'Method':<12} |"
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
            
            overall_scores[method] += suite_acc_sum
        
        # Time Stats
        print(f"{'Avg Time':<12} |", end="")
        for val in test_values:
             times = time_stats[suite_name][val]
             avg_t = sum(times)/len(times) if times else 0
             print(f" {avg_t:4.0f}ms  |", end="")
        print()
        
        total_scenarios += len(test_values)

    print("\n" + "=" * 80)
    print("PROPOSED IMPROVEMENTS")
    print("=" * 80)
    
    print(f"Total Scenarios: {total_scenarios}")
    
    if total_scenarios > 0:
        best_method = max(overall_scores, key=overall_scores.get)
        best_avg = overall_scores[best_method] / total_scenarios
        print(f"Best Overall Method: {best_method} (Avg Acc: {best_avg*100:.1f}%)")
    else:
        print("No scenarios run!")
        return
    
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

    for p in proposals:
        print(p)

    # Save results
    print("\n" + "=" * 70)
    print("SAVING RESULTS")
    print("=" * 70)
    filepath = save_arena_results(stats, overall_scores, total_scenarios, timestamp)
    print(f"Results saved to: {filepath}")
    print("Use 'python temp/view_history.py' to view and compare historical results")

if __name__ == '__main__':
    run_arena()