"""Arena test for Voting Ensemble strategy."""

import sys
import os
import glob
import logging
import argparse
import numpy as np
from datetime import datetime

_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_current_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from tests.template_utils import locate_cmd_templates
from src.audio.io import load_audio_file
from src.audio.recognizers import MultiMethodMatcher
from src import config
from tests.test_arena import apply_augmentation, get_label_from_filename, preload_templates, ArenaResult, TEST_SUITES

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

def run_voting_arena():
    print("=" * 70)
    print("Bio-Voice Commander - Voting Ensemble Test")
    print("   Mode: WEIGHTED VOTING (Hard Vote)")
    print("=" * 70)

    template_dir = locate_cmd_templates()
    all_files = sorted(glob.glob(os.path.join(template_dir, "*.*")))
    valid_files = [f for f in all_files if get_label_from_filename(f) != "UNKNOWN" and 'noise' not in os.path.basename(f).lower()]
    
    all_templates = preload_templates(valid_files)
    
    stats = {}
    for suite in TEST_SUITES:
        stats[suite] = {val: ArenaResult() for val in TEST_SUITES[suite]}

    print("\nStarting Leave-One-Out testing...")
    
    for idx, test_file in enumerate(valid_files):
        original_audio, expected_label = all_templates[test_file]
        print(f"Testing {idx+1}/{len(valid_files)}: {os.path.basename(test_file)}")
        
        matcher = MultiMethodMatcher(methods=['mfcc_dtw', 'mel', 'lpc'])
        for train_file, (train_audio, train_label) in all_templates.items():
            if train_file != test_file:
                matcher.add_template(train_label, train_audio, os.path.basename(train_file))

        for suite_name, test_values in TEST_SUITES.items():
            for val in test_values:
                try:
                    aug_audio = apply_augmentation(original_audio, suite_name, val)
                    
                    # USE NEW VOTING METHOD
                    result = matcher.recognize_voting(aug_audio, adaptive=True)
                    
                    pred = result['command']
                    stats[suite_name][val].update(expected_label, pred)
                except Exception as e:
                    logger.error(f"Error: {e}")

    # Report
    print("\n" + "=" * 60)
    print("VOTING ENSEMBLE RESULTS")
    print("=" * 60)
    
    for suite_name, test_values in TEST_SUITES.items():
        print(f"\n>> {suite_name.upper()}")
        header = "Val | " + " | ".join([f"{v:5g}" for v in test_values])
        print(header)
        print("-" * len(header))
        
        row = "Acc | "
        for val in test_values:
            acc = stats[suite_name][val].accuracy() * 100
            row += f"{acc:4.0f}% | "
        print(row)

if __name__ == '__main__':
    run_voting_arena()
