"""View and compare historical arena test results."""
import sys
import os
import json
import glob
from datetime import

# Ensure the project root is in the Python path for module imports
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_current_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
 datetime

def load_all_results(record_dir):
    """Load all arena result JSON files."""
    json_files = sorted(glob.glob(os.path.join(record_dir, "arena_*.json")))
    results = []

    for filepath in json_files:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                data['filepath'] = filepath
                results.append(data)
        except Exception as e:
            print(f"Warning: Could not load {filepath}: {e}")

    return results

def print_summary_table(results):
    """Print summary table of all results."""
    print("=" * 120)
    print("HISTORICAL ARENA RESULTS SUMMARY")
    print("=" * 120)
    print(f"{'#':<4} {'Timestamp':<20} {'MFCC':<8} {'Mel':<8} {'LPC':<8} {'Ensemble':<8} {'Config Changes':<30}")
    print("-" * 120)

    for i, result in enumerate(results, 1):
        timestamp = result['timestamp']
        scores = result['overall_scores']

        mfcc_acc = scores['mfcc_dtw']['average_accuracy'] * 100
        mel_acc = scores['mel']['average_accuracy'] * 100
        lpc_acc = scores['lpc']['average_accuracy'] * 100
        ens_acc = scores['ensemble']['average_accuracy'] * 100

        # Check for config changes from previous
        changes = ""
        if i > 1:
            prev_config = results[i-2]['config']
            curr_config = result['config']
            changes = get_config_diff(prev_config, curr_config)

        print(f"{i:<4} {timestamp:<20} {mfcc_acc:>6.1f}% {mel_acc:>6.1f}% {lpc_acc:>6.1f}% {ens_acc:>6.1f}% {changes:<30}")

def get_config_diff(prev, curr):
    """Get human-readable config differences."""
    diffs = []

    # Check thresholds
    if prev['thresholds'] != curr['thresholds']:
        for key in prev['thresholds']:
            if prev['thresholds'][key] != curr['thresholds'][key]:
                diffs.append(f"{key}_th:{prev['thresholds'][key]}->{curr['thresholds'][key]}")

    # Check hop_length
    if prev['audio']['hop_length'] != curr['audio']['hop_length']:
        diffs.append(f"hop:{prev['audio']['hop_length']}->{curr['audio']['hop_length']}")

    # Check LPC
    if prev['lpc'] != curr['lpc']:
        if prev['lpc']['order'] != curr['lpc']['order']:
            diffs.append(f"lpc_ord:{prev['lpc']['order']}->{curr['lpc']['order']}")

    return ", ".join(diffs[:2]) if diffs else "-"

def print_detailed_comparison(results, indices):
    """Print detailed comparison of specific results."""
    if len(indices) < 2:
        print("Need at least 2 indices to compare")
        return

    print("\n" + "=" * 120)
    print("DETAILED COMPARISON")
    print("=" * 120)

    # Get selected results
    selected = [results[i-1] for i in indices if 0 < i <= len(results)]

    if len(selected) < 2:
        print("Invalid indices")
        return

    # Print timestamps
    print(f"\nComparing runs:")
    for i, res in enumerate(selected, 1):
        print(f"  [{i}] {res['timestamp']}")

    # Compare each suite
    for suite_name in ['Speed', 'Pitch', 'Noise', 'Volume']:
        print(f"\n{suite_name} Robustness:")
        print(f"{'Value':<12}", end="")
        for i in range(len(selected)):
            print(f" Run{i+1:>5}", end="")
        print()
        print("-" * (12 + 7 * len(selected)))

        suite_data = selected[0]['suites'][suite_name]
        test_values = suite_data['test_values']

        for val in test_values:
            val_str = str(val)
            if suite_name == 'Speed':
                label = f"{val}x"
            elif suite_name == 'Pitch':
                label = f"{val:+}st"
            elif suite_name == 'Noise':
                label = f"{val}dB"
            elif suite_name == 'Volume':
                label = f"{val}x"
            else:
                label = str(val)

            print(f"{label:<12}", end="")

            for res in selected:
                acc = res['suites'][suite_name]['methods']['ensemble'][val_str]['accuracy']
                print(f" {acc*100:>5.0f}%", end="")
            print()

    # Configuration comparison
    print("\n" + "=" * 120)
    print("CONFIGURATION DIFFERENCES")
    print("=" * 120)

    configs = [res['config'] for res in selected]

    # Compare thresholds
    print("\nThresholds:")
    for key in configs[0]['thresholds']:
        vals = [c['thresholds'][key] for c in configs]
        if len(set(vals)) > 1:  # Has differences
            print(f"  {key:>12}: ", end="")
            for v in vals:
                print(f"{v:>8.1f} ", end="")
            print()

    # Compare audio params
    print("\nAudio Parameters:")
    for key in ['hop_length', 'n_fft', 'n_mfcc']:
        vals = [c['audio'][key] for c in configs]
        if len(set(vals)) > 1:
            print(f"  {key:>12}: ", end="")
            for v in vals:
                print(f"{v:>8} ", end="")
            print()

    # Compare LPC params
    print("\nLPC Parameters:")
    for key in configs[0]['lpc']:
        vals = [c['lpc'][key] for c in configs]
        if len(set(vals)) > 1:
            print(f"  {key:>12}: ", end="")
            for v in vals:
                print(f"{v:>8} ", end="")
            print()

def print_noise_robustness(results):
    """Print noise robustness comparison across all runs."""
    print("\n" + "=" * 100)
    print("NOISE ROBUSTNESS TRENDS")
    print("=" * 100)

    print(f"\n{'Run':<4} {'Timestamp':<20} {'Clean (100dB)':<14} {'Noisy (10dB)':<14} {'Drop':<8}")
    print("-" * 100)

    for i, result in enumerate(results, 1):
        timestamp = result['timestamp']
        noise_suite = result['suites']['Noise']['methods']['ensemble']

        clean_acc = noise_suite['100']['accuracy'] * 100
        noisy_acc = noise_suite['10']['accuracy'] * 100
        drop = clean_acc - noisy_acc

        print(f"{i:<4} {timestamp:<20} {clean_acc:>12.1f}% {noisy_acc:>12.1f}% {drop:>6.1f}%")

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    record_dir = os.path.join(base_dir, "record")

    if not os.path.exists(record_dir):
        print(f"No record directory found at {record_dir}")
        return

    results = load_all_results(record_dir)

    if not results:
        print("No arena results found in record/")
        print("Run 'python temp/test_file_input.py' to generate results")
        return

    print(f"Found {len(results)} historical results\n")

    # Print summary
    print_summary_table(results)

    # Print noise robustness
    print_noise_robustness(results)

    # Interactive comparison
    print("\n" + "=" * 100)
    print("COMMANDS")
    print("=" * 100)
    print("  compare <n1> <n2> [n3] ...  - Compare specific runs")
    print("  detail <n>                  - Show detailed results for run #n")
    print("  q                           - Quit")
    print()

    while True:
        try:
            cmd = input("> ").strip()

            if cmd == 'q':
                break

            elif cmd.startswith('compare'):
                parts = cmd.split()
                if len(parts) < 3:
                    print("Usage: compare <n1> <n2> [n3] ...")
                    continue

                indices = [int(x) for x in parts[1:]]
                print_detailed_comparison(results, indices)

            elif cmd.startswith('detail'):
                parts = cmd.split()
                if len(parts) != 2:
                    print("Usage: detail <n>")
                    continue

                idx = int(parts[1])
                if 0 < idx <= len(results):
                    result = results[idx-1]
                    print(f"\n{json.dumps(result, indent=2, ensure_ascii=False)}")
                else:
                    print(f"Invalid index. Must be 1-{len(results)}")

            else:
                print("Unknown command. Type 'q' to quit.")

        except (ValueError, IndexError) as e:
            print(f"Error: {e}")
        except KeyboardInterrupt:
            print("\nExiting...")
            break

if __name__ == '__main__':
    main()
