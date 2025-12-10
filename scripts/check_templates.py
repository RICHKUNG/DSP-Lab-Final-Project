"""Check which templates/commands are failing most."""
import json
import glob
import os
import sys
# Ensure the project root is in the Python path for module imports
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_current_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
record_dir = os.path.join(base_dir, "record")

# Load latest result
json_files = sorted(glob.glob(os.path.join(record_dir, "arena_*.json")))
latest_file = json_files[-1]

with open(latest_file, 'r', encoding='utf-8') as f:
    result = json.load(f)

print("=" * 60)
print("PER-METHOD DETAILED BREAKDOWN")
print("=" * 60)

# Aggregate across all conditions for each method
for method in ['mfcc_dtw', 'mel', 'lpc']:
    print(f"\n{method.upper()}:")
    print("-" * 60)

    # Collect all predictions
    correct_by_cmd = {}
    total_by_cmd = {}

    for suite_name, suite_data in result['suites'].items():
        for condition, data in suite_data['methods'][method].items():
            # data has 'predictions' list
            for i, pred in enumerate(data['predictions']):
                expected = data['expected'][i]

                if expected not in total_by_cmd:
                    total_by_cmd[expected] = 0
                    correct_by_cmd[expected] = 0

                total_by_cmd[expected] += 1
                if pred == expected:
                    correct_by_cmd[expected] += 1

    # Print stats
    for cmd in sorted(total_by_cmd.keys()):
        acc = correct_by_cmd[cmd] / total_by_cmd[cmd] * 100
        print(f"  {cmd:8s}: {correct_by_cmd[cmd]:2d}/{total_by_cmd[cmd]:2d} = {acc:5.1f}%")

print("\n" + "=" * 60)
print("ENSEMBLE:")
print("-" * 60)
correct_by_cmd = {}
total_by_cmd = {}

for suite_name, suite_data in result['suites'].items():
    for condition, data in suite_data['methods']['ensemble'].items():
        for i, pred in enumerate(data['predictions']):
            expected = data['expected'][i]

            if expected not in total_by_cmd:
                total_by_cmd[expected] = 0
                correct_by_cmd[expected] = 0

            total_by_cmd[expected] += 1
            if pred == expected:
                correct_by_cmd[expected] += 1

for cmd in sorted(total_by_cmd.keys()):
    acc = correct_by_cmd[cmd] / total_by_cmd[cmd] * 100
    print(f"  {cmd:8s}: {correct_by_cmd[cmd]:2d}/{total_by_cmd[cmd]:2d} = {acc:5.1f}%")
