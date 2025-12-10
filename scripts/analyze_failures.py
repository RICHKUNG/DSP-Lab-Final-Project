"""Analyze which templates are failing and why."""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
record_dir = os.path.join(base_dir, "record")

# Load latest result
import glob

# Ensure the project root is in the Python path for module imports
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_current_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

json_files = sorted(glob.glob(os.path.join(record_dir, "arena_*.json")))
if not json_files:
    print("No results found!")
    sys.exit(1)

latest_file = json_files[-1]
with open(latest_file, 'r', encoding='utf-8') as f:
    result = json.load(f)

print("=" * 80)
print(f"FAILURE ANALYSIS: {result['timestamp']}")
print("=" * 80)

# Analyze per-method accuracy
print("\nMethod Performance:")
print("-" * 80)
for method in ['mfcc_dtw', 'mel', 'lpc', 'ensemble']:
    avg_acc = result['overall_scores'][method]['average_accuracy']
    print(f"{method:>12}: {avg_acc*100:>6.1f}%")

# Analyze by condition
print("\n" + "=" * 80)
print("WEAKEST CONDITIONS (Ensemble)")
print("=" * 80)

conditions = []
for suite_name, suite_data in result['suites'].items():
    for val, data in suite_data['methods']['ensemble'].items():
        acc = data['accuracy']
        label = f"{suite_name}_{val}"
        conditions.append((label, acc, data['correct'], data['total']))

conditions.sort(key=lambda x: x[1])

print(f"\n{'Condition':<20} {'Accuracy':>10} {'Correct/Total':>15}")
print("-" * 80)
for label, acc, correct, total in conditions[:10]:
    print(f"{label:<20} {acc*100:>9.1f}% {correct:>7}/{total:<7}")

# Compare method strengths
print("\n" + "=" * 80)
print("METHOD COMPARISON BY SUITE")
print("=" * 80)

for suite_name in ['Speed', 'Pitch', 'Noise', 'Volume']:
    suite_data = result['suites'][suite_name]

    # Calculate average accuracy per method
    print(f"\n{suite_name}:")
    for method in ['mfcc_dtw', 'mel', 'lpc', 'ensemble']:
        accs = []
        for val, data in suite_data['methods'][method].items():
            accs.append(data['accuracy'])
        avg = sum(accs) / len(accs) if accs else 0
        print(f"  {method:>12}: {avg*100:>6.1f}%")

# Identify specific problem areas
print("\n" + "=" * 80)
print("RECOMMENDATIONS")
print("=" * 80)

# Check Mel accuracy
mel_scores = result['overall_scores']['mel']
mel_avg = mel_scores['average_accuracy']

if mel_avg < 0.6:
    print(f"\n1. Mel method is underperforming ({mel_avg*100:.1f}%)")
    print("   Suggestions:")
    print("   - Lower THRESHOLD_MEL from 0.45 to 0.50 (stricter)")
    print("   - Or increase weight in ensemble")

# Check LPC accuracy
lpc_scores = result['overall_scores']['lpc']
lpc_avg = lpc_scores['average_accuracy']

if lpc_avg < 0.6:
    print(f"\n2. LPC method is underperforming ({lpc_avg*100:.1f}%)")
    print("   Suggestions:")
    print("   - Adjust THRESHOLD_LPC (currently 80.0)")
    print("   - May need template-specific tuning")

# Check noise performance
noise_suite = result['suites']['Noise']['methods']['ensemble']
clean_acc = noise_suite['100']['accuracy']
noisy_acc = noise_suite['10']['accuracy']
drop = clean_acc - noisy_acc

if drop > 0.2:
    print(f"\n3. Noise robustness needs improvement")
    print(f"   Clean: {clean_acc*100:.1f}% → 10dB: {noisy_acc*100:.1f}% (drop {drop*100:.1f}%)")
    print("   Suggestions:")
    print("   - Increase Mel weight in ensemble (better noise resistance)")
    print("   - Add more noise templates for rejection")

# Check if ensemble is better than best single method
mfcc_avg = result['overall_scores']['mfcc_dtw']['average_accuracy']
ensemble_avg = result['overall_scores']['ensemble']['average_accuracy']

if ensemble_avg <= mfcc_avg:
    print(f"\n4. Ensemble is not improving over MFCC alone")
    print(f"   MFCC: {mfcc_avg*100:.1f}% vs Ensemble: {ensemble_avg*100:.1f}%")
    print("   Suggestions:")
    print("   - Mel and LPC may be hurting more than helping")
    print("   - Consider increasing Mel/LPC thresholds to be more selective")
    print("   - Or use adaptive mode (MFCC-only when confident)")

print("\n" + "=" * 80)
