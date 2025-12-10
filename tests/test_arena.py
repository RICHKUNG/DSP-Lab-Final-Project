"""Arena test for distorting templates and matching against the remaining set.

Improvements (2025-12-10):
- ✅ Better error handling with detailed logging
- ✅ Memory efficiency: preload all templates once
- ✅ Statistical metrics: added standard deviation
- ✅ Progress tracking: percentage display
- ✅ Improved constants (no magic numbers)
"""

print("Starting Arena Test...")
import sys
import os
import time
import numpy as np
import glob
import librosa
import json
import logging
import argparse
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

# Ensure src is in path

# Ensure the project root is in the Python path for module imports
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_current_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Local imports after path is configured
from tests.template_utils import locate_cmd_templates

try:
    from src.audio_io import load_audio_file
    from src.recognizers import MultiMethodMatcher
    from src import config
    print("Imports successful.")
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Constants (no magic numbers)
FLOAT_COMPARE_EPSILON = 1e-6
AUDIO_MIN_AMPLITUDE = -1.0
AUDIO_MAX_AMPLITUDE = 1.0
AUDIO_INT16_SCALE = 32767.0
HIGH_SNR_THRESHOLD = 100  # dB - effectively clean audio
NOISE_DROP_THRESHOLD = 0.4  # 40% accuracy drop is concerning

# Test suites
TEST_SUITES = {
    'Speed': [0.7, 0.9, 1.0, 1.1, 1.3],
    'Pitch': [-2.5, -1.0, 0.0, 1.0, 2.5],  # Semitones
    'Noise': [100, 25, 20, 15, 10],  # SNR (dB) - 100 means effectively clean
    'Volume': [0.3, 0.6, 1.0, 1.5, 3.0]
}


def is_close(a: float, b: float, epsilon: float = FLOAT_COMPARE_EPSILON) -> bool:
    """Safe floating point comparison."""
    return abs(a - b) < epsilon


def apply_augmentation(audio: np.ndarray, aug_type: str, value: float) -> np.ndarray:
    """Apply specific augmentation to audio.

    Args:
        audio: Input audio as int16 numpy array
        aug_type: Type of augmentation (Speed, Pitch, Noise, Volume)
        value: Augmentation parameter value

    Returns:
        Augmented audio as int16 numpy array

    Raises:
        ValueError: If audio contains invalid values
    """
    # Validate input
    if len(audio) == 0:
        raise ValueError("Empty audio array")

    # Convert to float32 for processing
    y_float = audio.astype(np.float32) / AUDIO_INT16_SCALE

    # Check for invalid values
    if np.any(np.isnan(y_float)) or np.any(np.isinf(y_float)):
        raise ValueError("Audio contains NaN or Inf values")

    try:
        if aug_type == 'Speed':
            if is_close(value, 1.0):
                return audio
            y_aug = librosa.effects.time_stretch(y_float, rate=value)

        elif aug_type == 'Pitch':
            if is_close(value, 0.0):
                return audio
            y_aug = librosa.effects.pitch_shift(y_float, sr=config.SAMPLE_RATE, n_steps=value)

        elif aug_type == 'Noise':
            if value >= HIGH_SNR_THRESHOLD:
                return audio
            p_signal = np.mean(y_float ** 2)
            if p_signal < FLOAT_COMPARE_EPSILON:
                logger.warning("Signal power too low for noise addition")
                return audio

            p_noise = p_signal / (10 ** (value / 10.0))
            noise = np.random.normal(0, np.sqrt(p_noise), len(y_float))
            y_aug = y_float + noise

        elif aug_type == 'Volume':
            if is_close(value, 1.0):
                return audio
            y_aug = y_float * value

        else:
            logger.warning(f"Unknown augmentation type: {aug_type}")
            return audio

        # Clip to valid range and convert back to int16
        y_aug = np.clip(y_aug, AUDIO_MIN_AMPLITUDE, AUDIO_MAX_AMPLITUDE)
        return (y_aug * AUDIO_INT16_SCALE).astype(np.int16)

    except Exception as e:
        logger.error(f"Augmentation failed ({aug_type}={value}): {e}")
        return audio  # Return original on error


def get_label_from_filename(filename: str) -> str:
    """Extract command label from filename."""
    fname = os.path.basename(filename)
    for cn, en in config.COMMAND_MAPPING.items():
        if cn in fname:
            return en
    return "UNKNOWN"


def get_config_snapshot():
    """Capture current configuration parameters with timestamp."""
    return {
        'timestamp': datetime.now().isoformat(),
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
            'dtw_radius': config.DTW_RADIUS,
        },
        'lpc': {
            'order': config.LPC_ORDER,
            'frame_ms': config.LPC_FRAME_MS,
            'hop_ms': config.LPC_HOP_MS,
        }
    }


def save_arena_results(stats, overall_scores, total_scenarios, timestamp_str, time_stats, run_mode):
    """Save arena results to JSON file with enhanced statistics."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    record_dir = os.path.join(base_dir, "record")
    os.makedirs(record_dir, exist_ok=True)

    # Prepare results data
    results = {
        'timestamp': timestamp_str,
        'mode': run_mode,
        'config': get_config_snapshot(),
        'methods': ['mfcc_dtw', 'mel', 'lpc', 'ensemble'],
        'suites': {},
        'overall_scores': {}
    }

    # Extract suite results with enhanced statistics
    for suite_name, test_values in TEST_SUITES.items():
        results['suites'][suite_name] = {
            'test_values': test_values,
            'methods': {}
        }

        for method in ['mfcc_dtw', 'mel', 'lpc', 'ensemble']:
            # Skip if method not in stats
            if method not in stats[suite_name]:
                continue
                
            results['suites'][suite_name]['methods'][method] = {}
            for val in test_values:
                res = stats[suite_name][method][val]

                # Calculate timing statistics
                times = time_stats[suite_name][val]
                timing_stats = {}
                if times:
                    timing_stats = {
                        'mean_ms': float(np.mean(times)),
                        'std_ms': float(np.std(times)),
                        'min_ms': float(np.min(times)),
                        'max_ms': float(np.max(times))
                    }

                results['suites'][suite_name]['methods'][method][str(val)] = {
                    'accuracy': res.accuracy(),
                    'correct': res.correct,
                    'total': res.total,
                    'wrong_command': res.wrong_command,
                    'no_match': res.no_match,
                    'noise': res.noise,
                    'timing': timing_stats if (method == 'ensemble' or run_mode == 'mfcc') else {}
                }

    # Overall scores with statistics
    for method in ['mfcc_dtw', 'mel', 'lpc', 'ensemble']:
        if method in overall_scores:
            avg = overall_scores[method] / total_scenarios if total_scenarios > 0 else 0
            results['overall_scores'][method] = {
                'total_score': overall_scores[method],
                'average_accuracy': avg
            }

    # Save to JSON
    filename = f"arena_{run_mode}_{timestamp_str.replace(':', '').replace(' ', '_').replace('-', '')}.json"
    filepath = os.path.join(record_dir, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    return filepath


class ArenaResult:
    """Statistics container for arena test results."""

    def __init__(self):
        self.total = 0
        self.correct = 0
        self.wrong_command = 0  # Predicted wrong command
        self.no_match = 0  # Predicted NONE (rejection)
        self.noise = 0  # Predicted NOISE

    def update(self, expected: str, predicted: str):
        """Update statistics with new prediction."""
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
        """Calculate accuracy percentage."""
        return self.correct / self.total if self.total > 0 else 0.0


def preload_templates(valid_files: List[str]) -> Dict[str, Tuple[np.ndarray, str]]:
    """Preload all templates once for memory efficiency.

    Args:
        valid_files: List of file paths to load

    Returns:
        Dictionary mapping file path to (audio, label) tuple
    """
    print("\nPreloading all templates...")
    templates = {}
    failed = []

    for idx, filepath in enumerate(valid_files):
        try:
            audio = load_audio_file(filepath)
            label = get_label_from_filename(filepath)
            templates[filepath] = (audio, label)
            print(f"\r  Loaded {idx+1}/{len(valid_files)} templates", end='', flush=True)
        except Exception as e:
            filename = os.path.basename(filepath)
            logger.error(f"Failed to load {filename}: {e}")
            failed.append(filename)

    print()  # New line after progress

    if failed:
        logger.warning(f"Failed to load {len(failed)} templates: {failed}")

    print(f"Successfully preloaded {len(templates)}/{len(valid_files)} templates")
    return templates


def run_arena(mode: str = 'all'):
    """Main arena test function with improvements."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Determine active methods
    if mode == 'mfcc':
        active_methods = ['mfcc_dtw']
        report_methods = ['mfcc_dtw']
        use_adaptive = False
    elif mode == 'ensemble':
        active_methods = ['mfcc_dtw', 'mel', 'lpc']
        report_methods = ['mfcc_dtw', 'mel', 'lpc', 'ensemble']
        use_adaptive = False
    elif mode == 'adaptive_ensemble':
        active_methods = ['mfcc_dtw', 'mel', 'lpc']
        report_methods = ['mfcc_dtw', 'mel', 'lpc', 'ensemble']
        use_adaptive = True
    else:
        active_methods = ['mfcc_dtw', 'mel', 'lpc']
        report_methods = ['mfcc_dtw', 'mel', 'lpc', 'ensemble']
        use_adaptive = False

    print("=" * 70)
    print("Bio-Voice Commander - Advanced Arena Test")
    print("   Suites: Speed, Pitch, Noise, Volume")
    print(f"   Mode: {mode.upper()}")
    print(f"   Time: {timestamp}")
    print("=" * 70)

    template_dir = locate_cmd_templates()

    # 1. Gather all template files
    all_files = sorted(glob.glob(os.path.join(template_dir, "*.*")))
    valid_files = []

    for f in all_files:
        if get_label_from_filename(f) != "UNKNOWN" and 'noise' not in os.path.basename(f).lower():
            valid_files.append(f)

    print(f"Found {len(valid_files)} valid command templates.")

    if len(valid_files) == 0:
        logger.error("No valid templates found!")
        return

    # 2. Preload all templates (MEMORY EFFICIENCY IMPROVEMENT)
    all_templates = preload_templates(valid_files)

    if len(all_templates) == 0:
        logger.error("Failed to load any templates!")
        return

    # Initialize statistics
    stats = {}
    time_stats = {}

    for suite in TEST_SUITES:
        stats[suite] = {}
        time_stats[suite] = {}
        for m in report_methods:
            stats[suite][m] = {val: ArenaResult() for val in TEST_SUITES[suite]}
        for val in TEST_SUITES[suite]:
            time_stats[suite][val] = []

    # 3. Leave-One-Out Loop
    print("\nStarting Leave-One-Out testing...")
    total_tests = len(valid_files)

    for idx, test_file in enumerate(valid_files):
        test_filename = os.path.basename(test_file)

        # Check if template was successfully loaded
        if test_file not in all_templates:
            logger.warning(f"Skipping {test_filename} (failed to preload)")
            continue

        original_audio, expected_label = all_templates[test_file]

        # Progress indicator
        progress_pct = (idx + 1) / total_tests * 100
        print(f"\n[{idx+1}/{total_tests} - {progress_pct:.1f}%] Testing: {test_filename} ({expected_label})")

        # Create matcher with all templates except test file
        matcher = MultiMethodMatcher(methods=active_methods)

        train_count = 0
        for train_file, (train_audio, train_label) in all_templates.items():
            if train_file == test_file:
                continue
            try:
                matcher.add_template(train_label, train_audio, os.path.basename(train_file))
                train_count += 1
            except Exception as e:
                logger.error(f"Failed to add template {os.path.basename(train_file)}: {e}")

        if train_count == 0:
            logger.warning(f"No training templates available for {test_filename}! Skipping.")
            continue

        # 4. Run Test Suites
        for suite_name, test_values in TEST_SUITES.items():
            for val in test_values:
                try:
                    # Augment
                    input_audio = apply_augmentation(original_audio, suite_name, val)

                    # Recognize
                    t0 = time.time()
                    results = matcher.recognize(input_audio, mode='all', adaptive=use_adaptive)
                    dt_ms = (time.time() - t0) * 1000
                    time_stats[suite_name][val].append(dt_ms)

                    if mode == 'mfcc':
                        # Explicit MFCC extraction
                        pred_cmd = results['all_results']['mfcc_dtw']['command']
                        stats[suite_name]['mfcc_dtw'][val].update(expected_label, pred_cmd)
                        match_mark = "OK" if pred_cmd == expected_label else "FAIL"
                        print(f"    [{suite_name} {val:g}] {pred_cmd:8s} {match_mark} ({dt_ms:.0f}ms)")
                    else:
                        # Record Ensemble
                        ensemble_pred = results['command']
                        stats[suite_name]['ensemble'][val].update(expected_label, ensemble_pred)

                        # Record Individuals
                        for method in ['mfcc_dtw', 'mel', 'lpc']:
                            if method in results['all_results']:
                                pred = results['all_results'][method]['command']
                                stats[suite_name][method][val].update(expected_label, pred)

                        match_mark = "OK" if ensemble_pred == expected_label else "FAIL"
                        print(f"    [{suite_name} {val:g}] {ensemble_pred:8s} {match_mark} ({dt_ms:.0f}ms)")

                except Exception as e:
                    logger.error(f"Test failed ({suite_name}={val}): {e}")
                    continue

    # 5. Report with enhanced statistics
    print("\n" + "=" * 80)
    print("ARENA RESULTS SUMMARY")
    print("=" * 80)

    overall_scores = {m: 0.0 for m in report_methods}
    total_scenarios = 0

    for suite_name, test_values in TEST_SUITES.items():
        print(f"\n>> {suite_name.upper()} ROBUSTNESS")

        # Header
        header = f"{'Method':<12} |";
        for val in test_values:
            label = f"{val:g}"
            if suite_name == 'Speed':
                label += 'x'
            elif suite_name == 'Pitch':
                label = f"{val:+}st"
            elif suite_name == 'Noise':
                label += 'dB'
            elif suite_name == 'Volume':
                label += 'x'
            header += f" {label:>7} |";
        print(header)
        print("-" * len(header))

        for method in report_methods:
            row = f"{method:<12} |";
            suite_acc_sum = 0.0
            for val in test_values:
                res = stats[suite_name][method][val]
                acc = res.accuracy()
                suite_acc_sum += acc
                row += f" {acc*100:6.0f}% |";
            print(row)

            overall_scores[method] += suite_acc_sum

        # Enhanced Time Stats
        print(f"{'Avg Time':<12} |", end="")
        for val in test_values:
            times = time_stats[suite_name][val]
            if times:
                avg_t = np.mean(times)
                std_t = np.std(times)
                print(f" {avg_t:4.0f}±{std_t:3.0f} |", end="")
            else:
                print(f" {'N/A':>8} |", end="")
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
        logger.error("No scenarios were successfully run!")
        return

    # Analyze noise robustness (only if we have noise stats)
    if 'Noise' in stats and mode != 'mfcc':
        proposals = []
        noise_drops = {}

        for method in report_methods:
            try:
                clean = stats['Noise'][method][HIGH_SNR_THRESHOLD].accuracy()
                noisy = stats['Noise'][method][10].accuracy()
                noise_drops[method] = clean - noisy
            except KeyError:
                logger.warning(f"Missing noise statistics for {method}")

        if noise_drops:
            worst_noise_method = max(noise_drops, key=noise_drops.get)
            if noise_drops[worst_noise_method] > NOISE_DROP_THRESHOLD:
                proposals.append(
                    f"- {worst_noise_method} fails in noise "
                    f"(drop {noise_drops[worst_noise_method]*100:.0f}%). "
                    f"Decrease its weight in noisy conditions."
                )

        for p in proposals:
            print(p)

    # Save results
    print("\n" + "=" * 70)
    print("SAVING RESULTS")
    print("=" * 70)
    filepath = save_arena_results(stats, overall_scores, total_scenarios, timestamp, time_stats, mode)
    print(f"Results saved to: {filepath}")
    print("Use 'python temp/view_history.py' to view and compare historical results")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run Arena Test')
    parser.add_argument('--mode', type=str, default='all', choices=['mfcc', 'ensemble', 'all', 'adaptive_ensemble'],
                        help='Test mode: mfcc (fast), ensemble (robust), adaptive_ensemble (smart), or all (full stats)')
    args = parser.parse_args()
    
    run_arena(mode=args.mode)
