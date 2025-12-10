"""Quickly show the latest arena test result."""
import sys
import os
import json
import glob
# Ensure the project root is in the Python path for module imports
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_current_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    record_dir = os.path.join(base_dir, "record")

    json_files = sorted(glob.glob(os.path.join(record_dir, "arena_*.json")))

    if not json_files:
        print("No arena results found.")
        print("Run: python temp/test_file_input.py")
        return

    latest_file = json_files[-1]

    with open(latest_file, 'r', encoding='utf-8') as f:
        result = json.load(f)

    print("=" * 80)
    print(f"LATEST ARENA TEST RESULT")
    print("=" * 80)
    print(f"File:      {os.path.basename(latest_file)}")
    print(f"Timestamp: {result['timestamp']}")
    print()

    # Overall scores
    print("Overall Average Accuracy:")
    print("-" * 80)
    for method in ['mfcc_dtw', 'mel', 'lpc', 'ensemble']:
        avg = result['overall_scores'][method]['average_accuracy']
        print(f"  {method:>12}: {avg*100:>6.1f}%")
    print()

    # Noise robustness
    print("Noise Robustness (Ensemble):")
    print("-" * 80)
    noise_suite = result['suites']['Noise']['methods']['ensemble']
    for snr in ['100', '20', '15', '10', '5']:
        if snr in noise_suite:
            acc = noise_suite[snr]['accuracy']
            correct = noise_suite[snr]['correct']
            total = noise_suite[snr]['total']
            label = "Clean" if snr == '100' else f"{snr}dB"
            print(f"  {label:>8}: {acc*100:>6.1f}% ({correct}/{total})")
    print()

    # Speed robustness
    print("Speed Robustness (Ensemble):")
    print("-" * 80)
    speed_suite = result['suites']['Speed']['methods']['ensemble']
    for rate in ['0.7', '0.9', '1.0', '1.1', '1.3']:
        if rate in speed_suite:
            acc = speed_suite[rate]['accuracy']
            print(f"  {rate:>5}x: {acc*100:>6.1f}%")
    print()

    # Key config
    print("Configuration:")
    print("-" * 80)
    cfg = result['config']
    print(f"  HOP_LENGTH:        {cfg['audio']['hop_length']}")
    print(f"  THRESHOLD_MFCC:    {cfg['thresholds']['mfcc_dtw']}")
    print(f"  THRESHOLD_MEL:     {cfg['thresholds']['mel']}")
    print(f"  THRESHOLD_LPC:     {cfg['thresholds']['lpc']}")
    print(f"  LPC_ORDER:         {cfg['lpc']['order']}")
    print()

    print("=" * 80)
    print("Use 'python temp/view_history.py' to compare with previous results")
    print("=" * 80)

if __name__ == '__main__':
    main()
