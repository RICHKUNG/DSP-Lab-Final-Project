"""
Mixed Conditions Arena Test
Tests the system against realistic combinations of distortions.
"""

import sys
import os
import time
import numpy as np
import glob
import librosa
import json
import logging
from typing import Dict, List, Tuple

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
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

AUDIO_INT16_SCALE = 32767.0

# =============================================================================
# Scenarios Definition
# =============================================================================

SCENARIOS = {
    'Indoor Quiet': {
        'description': 'Baseline: Ideal conditions',
        'speed': 1.0, 'pitch': 0.0, 'snr': 100, 'vol': 1.0
    },
    'Fast & Noisy': {
        'description': 'Rushing in a cafe (Speed 1.3x, SNR 15dB)',
        'speed': 1.3, 'pitch': 0.0, 'snr': 15, 'vol': 1.0
    },
    'Distant Speaker': {
        'description': 'Far from mic (Vol 0.3x, SNR 25dB)',
        'speed': 1.0, 'pitch': 0.0, 'snr': 25, 'vol': 0.3
    },
    'Excited User': {
        'description': 'Shouting fast (Speed 1.2x, Pitch +2st, Vol 2.0x)',
        'speed': 1.2, 'pitch': 2.0, 'snr': 100, 'vol': 2.0
    },
    'Tired User': {
        'description': 'Mumbling slow (Speed 0.8x, Pitch -2st, Vol 0.6x)',
        'speed': 0.8, 'pitch': -2.0, 'snr': 100, 'vol': 0.6
    },
    'Factory Floor': {
        'description': 'Loud background, user shouting (SNR 5dB, Vol 3.0x)',
        'speed': 1.0, 'pitch': 0.0, 'snr': 5, 'vol': 3.0
    },
    'Outdoor Windy': {
        'description': 'Wind noise + Distant (SNR 10dB, Vol 0.5x)',
        'speed': 1.0, 'pitch': 0.0, 'snr': 10, 'vol': 0.5
    },
    'Stress Test': {
        'description': 'Everything wrong (Fast, High Pitch, Noisy, Quiet)',
        'speed': 1.3, 'pitch': 2.5, 'snr': 10, 'vol': 0.4
    }
}

# =============================================================================
# Augmentation Logic
# =============================================================================

def apply_mixed_augmentation(audio: np.ndarray, params: dict) -> np.ndarray:
    """Apply multiple augmentations in sequence: Pitch -> Speed -> Volume -> Noise"""
    if len(audio) == 0: return audio
    
    # Normalize to float
    y = audio.astype(np.float32) / AUDIO_INT16_SCALE
    
    try:
        # 1. Pitch Shift (Computationally expensive)
        if params['pitch'] != 0.0:
            y = librosa.effects.pitch_shift(y, sr=config.SAMPLE_RATE, n_steps=params['pitch'])
            
        # 2. Time Stretch (Changes length)
        if params['speed'] != 1.0:
            y = librosa.effects.time_stretch(y, rate=params['speed'])
            
        # 3. Volume (Simple gain)
        if params['vol'] != 1.0:
            y = y * params['vol']
            
        # 4. Add Noise (SNR calculation)
        if params['snr'] < 90:
            p_signal = np.mean(y ** 2)
            if p_signal > 1e-9:
                p_noise = p_signal / (10 ** (params['snr'] / 10.0))
                noise = np.random.normal(0, np.sqrt(p_noise), len(y))
                y = y + noise
                
        # Clip and convert back
        y = np.clip(y, -1.0, 1.0)
        return (y * AUDIO_INT16_SCALE).astype(np.int16)
        
    except Exception as e:
        print(f"Augmentation error: {e}")
        return audio

# =============================================================================
# Test Runners
# =============================================================================

def get_label_from_filename(filename: str) -> str:
    fname = os.path.basename(filename)
    for cn, en in config.COMMAND_MAPPING.items():
        if cn in fname:
            return en
    return "UNKNOWN"

def run_mixed_test():
    print("=" * 70)
    print(f"MIXED CONDITIONS TEST")
    print(f"Method: Adaptive Ensemble")
    print("=" * 70)

    # 1. Load Templates
    template_dir = locate_cmd_templates()
    all_files = sorted(glob.glob(os.path.join(template_dir, "*.*")))
    valid_files = [f for f in all_files if get_label_from_filename(f) != "UNKNOWN" and 'noise' not in os.path.basename(f).lower()]
    
    if not valid_files:
        print("No templates found.")
        return

    print(f"Loaded {len(valid_files)} templates.")
    
    # Preload
    templates_data = {}
    for f in valid_files:
        templates_data[f] = (load_audio_file(f), get_label_from_filename(f))

    # Stats containers
    scenario_stats = {name: {'correct': 0, 'total': 0, 'times': []} for name in SCENARIOS}
    
    # 2. Run Test Loop
    for idx, test_file in enumerate(valid_files):
        original_audio, expected_label = templates_data[test_file]
        print(f"\nProcessing {idx+1}/{len(valid_files)}: {os.path.basename(test_file)} ({expected_label})")
        
        # Build Matcher (LOO)
        matcher = MultiMethodMatcher(methods=['mfcc_dtw', 'mel', 'lpc'])
        for train_file, (train_audio, train_label) in templates_data.items():
            if train_file != test_file:
                matcher.add_template(train_label, train_audio, os.path.basename(train_file))
        
        # Run Scenarios
        for s_name, params in SCENARIOS.items():
            # Augment
            aug_audio = apply_mixed_augmentation(original_audio, params)
            
            # Recognize
            t0 = time.time()
            result = matcher.recognize(aug_audio, adaptive=True)
            dt_ms = (time.time() - t0) * 1000
            
            # Record
            pred = result['command']
            is_correct = (pred == expected_label)
            
            stats = scenario_stats[s_name]
            stats['total'] += 1
            if is_correct: stats['correct'] += 1
            stats['times'].append(dt_ms)
            
            mark = "OK" if is_correct else f"FAIL -> {pred}"
            # print(f"  [{s_name:15}] {mark} ({dt_ms:.0f}ms)")

    # 3. Report
    print("\n" + "=" * 80)
    print(f"{ 'SCENARIO':<20} | {'ACCURACY':<10} | {'AVG TIME':<10} | {'DESCRIPTION'}")
    print("-" * 80)
    
    for s_name, stats in scenario_stats.items():
        acc = (stats['correct'] / stats['total']) * 100 if stats['total'] > 0 else 0
        avg_t = np.mean(stats['times']) if stats['times'] else 0
        desc = SCENARIOS[s_name]['description']
        
        print(f"{s_name:<20} | {acc:6.1f}%    | {avg_t:4.0f}ms     | {desc}")
        
    print("-" * 80)

if __name__ == '__main__':
    run_mixed_test()
