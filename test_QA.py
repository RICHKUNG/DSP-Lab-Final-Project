"""QA test with user feedback for accuracy measurement."""

import sys
import os
import time
import argparse
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.audio_io import AudioStream, find_suitable_device
from src.vad import VAD, VADState
from src.recognizers import MultiMethodMatcher
from src import config


# Label mapping
LABEL_MAP = {
    'S': 'START',
    's': 'START',
    'J': 'JUMP',
    'j': 'JUMP',
    'P': 'PAUSE',
    'p': 'PAUSE',
    'N': 'NOISE',
    'n': 'NOISE',
}

LABEL_DISPLAY = {
    'START': 'S(開始)',
    'JUMP': 'J(跳)',
    'PAUSE': 'P(暫停)',
    'NOISE': 'N(噪音)',
    'NONE': 'NONE',
}


def get_user_label():
    """Get ground truth label from user."""
    while True:
        try:
            user_input = input("\n>>> Enter correct label [S=開始, J=跳, P=暫停, N=噪音, Q=結束]: ").strip()
            if user_input.upper() == 'Q':
                return None  # Signal to quit
            if user_input in LABEL_MAP:
                return LABEL_MAP[user_input]
            print("Invalid input. Please enter S, J, P, N, or Q.")
        except EOFError:
            return None


def generate_report(stats, matcher, output_path):
    """Generate markdown report."""

    methods = list(matcher.matchers.keys())

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# Voice Recognition QA Test Report\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        # Overall summary
        f.write("## Overall Summary\n\n")
        f.write(f"- **Total samples:** {stats['total']}\n")
        f.write(f"- **Noise samples (excluded):** {stats['noise_count']}\n")
        f.write(f"- **Valid samples:** {stats['total'] - stats['noise_count']}\n\n")

        # Thresholds
        f.write("## Current Thresholds\n\n")
        f.write("| Method | Threshold |\n")
        f.write("|--------|----------:|\n")
        for method in methods:
            threshold = matcher.matchers[method].threshold
            f.write(f"| {method} | {threshold:.2f} |\n")
        f.write("\n")

        # Per-method results
        f.write("## Per-Method Results\n\n")

        for method in methods:
            method_stats = stats['per_method'][method]
            valid_total = stats['total'] - stats['noise_count']

            if valid_total > 0:
                accuracy = method_stats['correct'] / valid_total * 100
            else:
                accuracy = 0

            f.write(f"### {method}\n\n")
            f.write(f"- **Accuracy:** {accuracy:.1f}% ({method_stats['correct']}/{valid_total})\n")
            f.write(f"- **False Positives (NOISE detected as command):** {method_stats['false_positive']}\n")
            f.write(f"- **False Negatives (Command detected as NONE):** {method_stats['false_negative']}\n")
            f.write(f"- **Misclassifications:** {method_stats['misclassified']}\n\n")

            # Confusion matrix
            f.write("#### Confusion Matrix\n\n")
            labels = ['START', 'JUMP', 'PAUSE', 'NONE']
            cm = method_stats['confusion']

            f.write("| Actual \\ Predicted |")
            for pred in labels:
                f.write(f" {pred} |")
            f.write("\n")

            f.write("|" + "-" * 20 + "|")
            for _ in labels:
                f.write("------:|")
            f.write("\n")

            for actual in ['START', 'JUMP', 'PAUSE', 'NOISE']:
                f.write(f"| **{actual}** |")
                for pred in labels:
                    count = cm.get((actual, pred), 0)
                    f.write(f" {count} |")
                f.write("\n")
            f.write("\n")

            # Distance statistics
            f.write("#### Distance Statistics\n\n")
            dists = method_stats['distances']
            if dists:
                f.write(f"- **Min:** {min(dists):.3f}\n")
                f.write(f"- **Max:** {max(dists):.3f}\n")
                f.write(f"- **Avg:** {sum(dists)/len(dists):.3f}\n\n")

                # Per-label distance stats
                f.write("##### Distance by Ground Truth Label\n\n")
                f.write("| Label | Count | Min | Max | Avg |\n")
                f.write("|-------|------:|----:|----:|----:|\n")
                for label in ['START', 'JUMP', 'PAUSE', 'NOISE']:
                    label_dists = method_stats['distances_by_label'].get(label, [])
                    if label_dists:
                        f.write(f"| {label} | {len(label_dists)} | {min(label_dists):.3f} | {max(label_dists):.3f} | {sum(label_dists)/len(label_dists):.3f} |\n")
                    else:
                        f.write(f"| {label} | 0 | - | - | - |\n")
                f.write("\n")
            else:
                f.write("No distance data collected.\n\n")

        # Ensemble results
        f.write("## Ensemble Decision Results\n\n")
        valid_total = stats['total'] - stats['noise_count']
        if valid_total > 0:
            ensemble_acc = stats['ensemble']['correct'] / valid_total * 100
        else:
            ensemble_acc = 0

        f.write(f"- **Accuracy:** {ensemble_acc:.1f}% ({stats['ensemble']['correct']}/{valid_total})\n")
        f.write(f"- **False Positives:** {stats['ensemble']['false_positive']}\n")
        f.write(f"- **False Negatives:** {stats['ensemble']['false_negative']}\n")
        f.write(f"- **Misclassifications:** {stats['ensemble']['misclassified']}\n\n")

        # Confusion matrix for ensemble
        f.write("### Ensemble Confusion Matrix\n\n")
        labels = ['START', 'JUMP', 'PAUSE', 'NONE']
        cm = stats['ensemble']['confusion']

        f.write("| Actual \\ Predicted |")
        for pred in labels:
            f.write(f" {pred} |")
        f.write("\n")

        f.write("|" + "-" * 20 + "|")
        for _ in labels:
            f.write("------:|")
        f.write("\n")

        for actual in ['START', 'JUMP', 'PAUSE', 'NOISE']:
            f.write(f"| **{actual}** |")
            for pred in labels:
                count = cm.get((actual, pred), 0)
                f.write(f" {count} |")
            f.write("\n")
        f.write("\n")

        # Timing statistics
        f.write("## Timing Statistics\n\n")
        if stats['processing_times']:
            avg_time = sum(stats['processing_times']) / len(stats['processing_times'])
            f.write(f"- **Processing Time (Avg):** {avg_time:.1f}ms\n")
            f.write(f"- **Processing Time (Min):** {min(stats['processing_times']):.1f}ms\n")
            f.write(f"- **Processing Time (Max):** {max(stats['processing_times']):.1f}ms\n\n")

        if stats['vad_latencies']:
            avg_lat = sum(stats['vad_latencies']) / len(stats['vad_latencies'])
            f.write(f"- **VAD Latency (Avg):** {avg_lat:.0f}ms\n")
            f.write(f"- **VAD Latency (Min):** {min(stats['vad_latencies']):.0f}ms\n")
            f.write(f"- **VAD Latency (Max):** {max(stats['vad_latencies']):.0f}ms\n\n")

        # Detailed log
        f.write("## Detailed Test Log\n\n")
        f.write("| # | Ground Truth | Ensemble | mfcc_dtw | stats | mel | lpc |\n")
        f.write("|--:|:-------------|:---------|:---------|:------|:----|:----|\n")

        for i, record in enumerate(stats['records'], 1):
            gt = record['ground_truth']
            ensemble = record['ensemble']
            ensemble_mark = "O" if ensemble == gt or (gt == 'NOISE' and ensemble == 'NONE') else "X"

            row = f"| {i} | {gt} | {ensemble} {ensemble_mark} |"
            for method in methods:
                pred = record['predictions'][method]
                mark = "O" if pred == gt or (gt == 'NOISE' and pred == 'NONE') else "X"
                row += f" {pred} {mark} |"
            f.write(row + "\n")

        f.write("\n---\n")
        f.write("*O = Correct, X = Incorrect*\n")
        f.write("*NOISE samples: NONE prediction is considered correct*\n")


def test_qa():
    """QA test with user feedback."""
    print("=" * 80)
    print("Bio-Voice Commander - QA Test Mode")
    print("=" * 80)

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="QA test for Bio-Voice Commander.")
    parser.add_argument(
        "--device-index",
        type=int,
        help="Specify the input audio device index to use."
    )
    args = parser.parse_args()

    # Load templates
    base_dir = os.path.dirname(os.path.abspath(__file__))
    matcher = MultiMethodMatcher()

    print("\nLoading templates...")
    matcher.load_templates_from_dir(base_dir)

    # Show loaded templates
    print("\nLoaded templates:")
    for method, m in matcher.matchers.items():
        if m.templates:
            print(f"  {method}:")
            for cmd, templates in m.templates.items():
                print(f"    - {cmd}: {len(templates)} samples")

    total_templates = sum(len(t) for m in matcher.matchers.values()
                          for t in m.templates.values())
    if total_templates == 0:
        print("\n[ERROR] No templates found!")
        return

    # Print current thresholds
    print("\n" + "-" * 80)
    print("Current Thresholds:")
    print("-" * 80)
    for method, m in matcher.matchers.items():
        print(f"  {method:12s}: {m.threshold:.2f}")

    # Find suitable audio device
    print("\n" + "=" * 80)
    print("Finding suitable audio device...")
    device_info = find_suitable_device(config.SAMPLE_RATE, verbose=True, preferred_device_index=args.device_index)

    if device_info is None:
        print("[ERROR] Cannot access any audio input device!")
        return

    device_index, device_rate = device_info
    print(f"Using audio device index: {device_index}")

    # Start audio stream
    print("Starting audio stream...")
    audio_stream = AudioStream(
        device_index=device_index,
        input_rate=device_rate,
        target_rate=config.SAMPLE_RATE,
    )
    audio_stream.start()

    print("Calibrating background noise (please stay quiet for 1.5 seconds)...")
    time.sleep(0.3)
    bg_rms = audio_stream.measure_background(1500)
    print(f"Background RMS: {bg_rms:.1f}")

    # Initialize VAD
    vad = VAD(background_rms=bg_rms)

    print("\n" + "=" * 80)
    print("QA Test Mode - Say commands and provide correct labels")
    print("Commands: 開始(S), 跳(J), 暫停(P), 噪音(N)")
    print("Press Ctrl+C or enter Q to finish and generate report")
    print("=" * 80)
    print()

    # Initialize statistics
    methods = list(matcher.matchers.keys())
    stats = {
        'total': 0,
        'noise_count': 0,
        'processing_times': [],
        'vad_latencies': [],
        'records': [],
        'per_method': {
            m: {
                'correct': 0,
                'false_positive': 0,
                'false_negative': 0,
                'misclassified': 0,
                'confusion': defaultdict(int),
                'distances': [],
                'distances_by_label': defaultdict(list),
            } for m in methods
        },
        'ensemble': {
            'correct': 0,
            'false_positive': 0,
            'false_negative': 0,
            'misclassified': 0,
            'confusion': defaultdict(int),
        }
    }

    vad_start_time = None
    last_state = VADState.SILENCE
    quit_flag = False

    try:
        while not quit_flag:
            chunk = audio_stream.get_chunk(timeout=0.02)
            if len(chunk) == 0:
                continue

            state, segment = vad.process_chunk(chunk)

            if state == VADState.RECORDING and last_state == VADState.SILENCE:
                vad_start_time = time.time()
                print("\r[Recording...]", end='', flush=True)

            last_state = state

            if state == VADState.PROCESSING and segment is not None:
                vad_end_time = time.time()
                vad_latency = (vad_end_time - vad_start_time) * 1000 if vad_start_time else 0
                stats['vad_latencies'].append(vad_latency)

                stats['total'] += 1
                segment_duration = len(segment) / config.SAMPLE_RATE

                print(f"\r" + "=" * 80)
                print(f"[Sample #{stats['total']}] Duration: {segment_duration:.2f}s")
                print("-" * 80)

                # Process with all methods
                total_start = time.time()
                raw_results = matcher.recognize(segment, mode='all')
                total_proc_time = (time.time() - total_start) * 1000
                stats['processing_times'].append(total_proc_time)

                # Compute ensemble decision
                best_command = 'NONE'
                best_confidence = 0.0
                best_method = None

                predictions = {}
                for method, res in raw_results['all_results'].items():
                    cmd = res['command']
                    dist = res['distance']
                    threshold = matcher.matchers[method].threshold
                    predictions[method] = cmd

                    if cmd != 'NONE':
                        conf = 1 - min(dist / threshold, 1)
                        if conf > best_confidence:
                            best_confidence = conf
                            best_command = cmd
                            best_method = method

                # Show results
                print(f"\nPredictions:")
                for method, res in raw_results['all_results'].items():
                    cmd = res['command']
                    dist = res['distance']
                    best_tpl = res['best_template']
                    threshold = matcher.matchers[method].threshold
                    conf_pct = max(0, (1 - dist / threshold) * 100)
                    print(f"  {method:12s}: {cmd:8s} (dist={dist:.3f}, conf={conf_pct:.1f}%, tpl={best_tpl})")

                print(f"\n>>> ENSEMBLE: {best_command}", end="")
                if best_method:
                    print(f" (by {best_method}, conf={best_confidence*100:.1f}%)")
                else:
                    print()

                # Get user label
                ground_truth = get_user_label()
                if ground_truth is None:
                    quit_flag = True
                    stats['total'] -= 1  # Don't count this sample
                    stats['vad_latencies'].pop()
                    stats['processing_times'].pop()
                    break

                # Record
                record = {
                    'ground_truth': ground_truth,
                    'ensemble': best_command,
                    'predictions': predictions,
                }
                stats['records'].append(record)

                # Update statistics
                if ground_truth == 'NOISE':
                    stats['noise_count'] += 1
                    # For NOISE, NONE is correct
                    for method, pred in predictions.items():
                        res = raw_results['all_results'][method]
                        stats['per_method'][method]['distances'].append(res['distance'])
                        stats['per_method'][method]['distances_by_label']['NOISE'].append(res['distance'])
                        stats['per_method'][method]['confusion'][('NOISE', pred)] += 1

                        if pred == 'NONE':
                            stats['per_method'][method]['correct'] += 1
                        else:
                            stats['per_method'][method]['false_positive'] += 1

                    stats['ensemble']['confusion'][('NOISE', best_command)] += 1
                    if best_command == 'NONE':
                        stats['ensemble']['correct'] += 1
                    else:
                        stats['ensemble']['false_positive'] += 1
                else:
                    # Valid command
                    for method, pred in predictions.items():
                        res = raw_results['all_results'][method]
                        stats['per_method'][method]['distances'].append(res['distance'])
                        stats['per_method'][method]['distances_by_label'][ground_truth].append(res['distance'])
                        stats['per_method'][method]['confusion'][(ground_truth, pred)] += 1

                        if pred == ground_truth:
                            stats['per_method'][method]['correct'] += 1
                        elif pred == 'NONE':
                            stats['per_method'][method]['false_negative'] += 1
                        else:
                            stats['per_method'][method]['misclassified'] += 1

                    stats['ensemble']['confusion'][(ground_truth, best_command)] += 1
                    if best_command == ground_truth:
                        stats['ensemble']['correct'] += 1
                    elif best_command == 'NONE':
                        stats['ensemble']['false_negative'] += 1
                    else:
                        stats['ensemble']['misclassified'] += 1

                # Show running accuracy
                valid = stats['total'] - stats['noise_count']
                if valid > 0:
                    ens_acc = stats['ensemble']['correct'] / valid * 100
                    print(f"\n[Running] Ensemble accuracy: {ens_acc:.1f}% ({stats['ensemble']['correct']}/{valid})")

                print("=" * 80)
                print()

                # Reset VAD
                vad.reset()
                vad_start_time = None

    except KeyboardInterrupt:
        print("\n\nStopping...")
    finally:
        audio_stream.stop()

    # Generate report
    if stats['total'] > 0:
        # Ensure record directory exists
        record_dir = os.path.join(base_dir, 'record')
        os.makedirs(record_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = os.path.join(record_dir, f'test_{timestamp}.md')

        print(f"\nGenerating report to: {output_path}")
        generate_report(stats, matcher, output_path)
        print("Report generated successfully!")

        # Print summary
        print("\n" + "=" * 80)
        print("Final Summary")
        print("=" * 80)
        print(f"Total samples: {stats['total']}")
        print(f"Noise samples: {stats['noise_count']}")
        valid = stats['total'] - stats['noise_count']
        if valid > 0:
            print(f"\nAccuracy (on {valid} valid samples):")
            for method in methods:
                acc = stats['per_method'][method]['correct'] / valid * 100
                print(f"  {method:12s}: {acc:.1f}%")
            ens_acc = stats['ensemble']['correct'] / valid * 100
            print(f"  {'ENSEMBLE':12s}: {ens_acc:.1f}%")
        print("=" * 80)
    else:
        print("\nNo samples collected. Report not generated.")


if __name__ == '__main__':
    test_qa()
