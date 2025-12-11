"""Arena test for distorting templates and matching against the remaining set.
EXTREME EDITION - Testing the limits of the system.
"""

print("Starting Extreme Arena Test...")
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
    from src.audio.io import load_audio_file
    from src.audio.recognizers import MultiMethodMatcher
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

# Constants
FLOAT_COMPARE_EPSILON = 1e-6
AUDIO_MIN_AMPLITUDE = -1.0
AUDIO_MAX_AMPLITUDE = 1.0
AUDIO_INT16_SCALE = 32767.0
HIGH_SNR_THRESHOLD = 100

# EXTREME Test suites
TEST_SUITES = {
    'Speed': [0.5, 0.7, 0.9, 1.0, 1.1, 1.3, 1.5, 1.7],  # Wider range
    'Pitch': [-5.0, -2.5, 0.0, 2.5, 5.0],              # Wider range
    'Noise': [100, 20, 10, 5, 0, -5],                  # Down to -5dB!
    'Volume': [0.1, 0.3, 1.0, 3.0, 5.0, 10.0]          # Extreme volume
}


def is_close(a: float, b: float, epsilon: float = FLOAT_COMPARE_EPSILON) -> bool:
    """Safe floating point comparison."""
    return abs(a - b) < epsilon


def apply_augmentation(audio: np.ndarray, aug_type: str, value: float) -> np.ndarray:
    """Apply specific augmentation to audio."""
    # Validate input
    if len(audio) == 0:
        raise ValueError("Empty audio array")

    # Convert to float32 for processing
    y_float = audio.astype(np.float32) / AUDIO_INT16_SCALE

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
            if p_signal < 1e-9:
                return audio

            # SNR = 10 * log10(Ps/Pn) -> Pn = Ps / 10^(SNR/10)
            p_noise = p_signal / (10 ** (value / 10.0))
            noise = np.random.normal(0, np.sqrt(p_noise), len(y_float))
            y_aug = y_float + noise

        elif aug_type == 'Volume':
            if is_close(value, 1.0):
                return audio
            y_aug = y_float * value

        else:
            return audio

        # Clip to valid range and convert back to int16
        y_aug = np.clip(y_aug, AUDIO_MIN_AMPLITUDE, AUDIO_MAX_AMPLITUDE)
        return (y_aug * AUDIO_INT16_SCALE).astype(np.int16)

    except Exception as e:
        logger.error(f"Augmentation failed ({aug_type}={value}): {e}")
        return audio


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
    def update(self, expected: str, predicted: str):
        self.total += 1
        if predicted == expected:
            self.correct += 1
    def accuracy(self) -> float:
        return self.correct / self.total if self.total > 0 else 0.0


def preload_templates(valid_files: List[str]) -> Dict[str, Tuple[np.ndarray, str]]:
    print("\nPreloading all templates...")
    templates = {}
    for idx, filepath in enumerate(valid_files):
        try:
            audio = load_audio_file(filepath)
            label = get_label_from_filename(filepath)
            templates[filepath] = (audio, label)
        except Exception:
            pass
    print(f"Successfully preloaded {len(templates)}/{len(valid_files)} templates")
    return templates


def run_arena(mode: str = 'adaptive_ensemble'):
    template_dir = locate_cmd_templates()
    all_files = sorted(glob.glob(os.path.join(template_dir, "*.*")))
    valid_files = [f for f in all_files if get_label_from_filename(f) != "UNKNOWN" and 'noise' not in os.path.basename(f).lower()]

    if not valid_files:
        print("Error: No templates found.")
        return

    all_templates = preload_templates(valid_files)
    
    # Setup stats
    stats = {}
    for suite in TEST_SUITES:
        stats[suite] = {val: ArenaResult() for val in TEST_SUITES[suite]}

    print("\nStarting Extreme Testing...")
    
    for idx, test_file in enumerate(valid_files):
        if test_file not in all_templates: continue
        
        original_audio, expected_label = all_templates[test_file]
        print(f"Testing {idx+1}/{len(valid_files)}: {os.path.basename(test_file)} ({expected_label})")
        
        # Build matcher
        matcher = MultiMethodMatcher(methods=['mfcc_dtw', 'mel', 'lpc'])
        for train_file, (train_audio, train_label) in all_templates.items():
            if train_file != test_file:
                matcher.add_template(train_label, train_audio, os.path.basename(train_file))

        # Run suites
        for suite_name, test_values in TEST_SUITES.items():
            for val in test_values:
                # Augment
                aug_audio = apply_augmentation(original_audio, suite_name, val)
                
                # Recognize (Adaptive)
                res = matcher.recognize(aug_audio, mode='best', adaptive=True)
                pred = res['command']
                
                stats[suite_name][val].update(expected_label, pred)

    # Report
    print("\n" + "="*60)
    print("EXTREME ARENA RESULTS (Adaptive Ensemble)")
    print("="*60)
    
    for suite_name, test_values in TEST_SUITES.items():
        print(f"\n>> {suite_name.upper()}")
        header = "Value | " + " | ".join([f"{v:5g}" for v in test_values])
        print(header)
        print("-" * len(header))
        
        row = "Acc   | "
        for val in test_values:
            acc = stats[suite_name][val].accuracy() * 100
            row += f"{acc:4.0f}% | "
        print(row)

if __name__ == '__main__':
    run_arena()
