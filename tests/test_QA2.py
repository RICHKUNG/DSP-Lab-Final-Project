"""QA test that only asks for feedback on detected commands, not noise."""

import sys
import os
import time
import argparse
import numpy as np
from datetime import datetime
from collections import defaultdict

# Ensure the project root is in the Python path for module imports
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_current_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from tests.template_utils import locate_cmd_templates
from src.audio.io import AudioStream, find_suitable_device
from src.audio.vad import VAD, VADState
from src.audio.recognizers import MultiMethodMatcher
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


def collect_noise_samples(audio_stream, duration_ms=2000, num_samples=5):
    """Collect noise samples from background audio."""
    samples_needed = int(config.SAMPLE_RATE * duration_ms / 1000)
    collected = []

    print(f"Collecting {num_samples} noise samples over {duration_ms}ms...")

    while len(collected) < samples_needed:
        chunk = audio_stream.get_chunk(timeout=0.5)
        if len(chunk) > 0:
            collected.extend(chunk)

    audio = np.array(collected[:samples_needed], dtype=np.int16)

    # Split into segments
    segment_len = len(audio) // num_samples
    noise_samples = []

    for i in range(num_samples):
        start = i * segment_len
        end = start + segment_len
        segment = audio[start:end]
        if len(segment) > 0:
            noise_samples.append(segment)

    return noise_samples


def get_user_label():
    """Get ground truth label from user."""
    while True:
        try:
            user_input = input("\n>>> 請輸入正確標籤 [S=開始, J=跳, P=暫停, N=噪音, Q=結束]: ").strip()
            if user_input.upper() == 'Q':
                return None  # Signal to quit
            if user_input in LABEL_MAP:
                return LABEL_MAP[user_input]
            print("無效輸入，請輸入 S, J, P, N 或 Q")
        except EOFError:
            return None


def generate_report(stats, matcher, output_path):
    """Generate markdown report."""

    methods = list(matcher.matchers.keys())

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# Voice Recognition QA Test Report (QA2 - Commands Only)\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        # Overall summary
        f.write("## Overall Summary\n\n")
        f.write(f"- **Total samples:** {stats['total']}\n")
        f.write(f"- **Auto-rejected noise:** {stats['auto_noise']}\n")
        f.write(f"- **Command samples (verified):** {stats['verified_commands']}\n")
        f.write(f"- **Noise templates used:** {matcher.get_noise_template_count()}\n\n")

        # Thresholds
        f.write("## Current Thresholds\n\n")
        f.write("| Method | Threshold |\n")
        f.write("|--------|----------:|\n")
        for method in methods:
            threshold = matcher.matchers[method].threshold
            f.write(f"| {method} | {threshold:.2f} |\n")
        f.write("\n")

        # Per-method results
        f.write("## Per-Method Results (on verified commands)\n\n")

        for method in methods:
            method_stats = stats['per_method'][method]
            valid_total = stats['verified_commands']

            if valid_total > 0:
                accuracy = method_stats['correct'] / valid_total * 100
            else:
                accuracy = 0

            f.write(f"### {method}\n\n")
            f.write(f"- **Command Accuracy:** {accuracy:.1f}% ({method_stats['correct']}/{valid_total})\n")
            f.write(f"- **False Negatives (Command detected as NONE/NOISE):** {method_stats['false_negative']}\n")
            f.write(f"- **Misclassifications:** {method_stats['misclassified']}\n\n")

            # Confusion matrix (only for verified commands)
            f.write("#### Confusion Matrix\n\n")
            labels = ['START', 'JUMP', 'PAUSE', 'NONE', 'NOISE']
            cm = method_stats['confusion']

            f.write("| Actual \\ Predicted |")
            for pred in labels:
                f.write(f" {pred} |")
            f.write("\n")

            f.write("|" + "-" * 20 + "|")
            for _ in labels:
                f.write("------:|")
            f.write("\n")

            for actual in ['START', 'JUMP', 'PAUSE']:
                f.write(f"| **{actual}** |")
                for pred in labels:
                    count = cm.get((actual, pred), 0)
                    f.write(f" {count} |")
                f.write("\n")
            f.write("\n")

            # Distance statistics
            f.write("#### Distance Statistics\n\n")
            dists = method_stats['distances']
            noise_dists = method_stats.get('noise_distances', [])

            if dists:
                f.write(f"**Command Distances:**\n")
                f.write(f"- Min: {min(dists):.3f}\n")
                f.write(f"- Max: {max(dists):.3f}\n")
                f.write(f"- Avg: {sum(dists)/len(dists):.3f}\n\n")

            if noise_dists:
                f.write(f"**Noise Template Distances:**\n")
                f.write(f"- Min: {min(noise_dists):.3f}\n")
                f.write(f"- Max: {max(noise_dists):.3f}\n")
                f.write(f"- Avg: {sum(noise_dists)/len(noise_dists):.3f}\n\n")

            # Per-label distance stats
            f.write("##### Distance by Ground Truth Label\n\n")
            f.write("| Label | Count | Min | Max | Avg |\n")
            f.write("|-------|------:|----:|----:|----:|\n")
            for label in ['START', 'JUMP', 'PAUSE']:
                label_dists = method_stats['distances_by_label'].get(label, [])
                if label_dists:
                    f.write(f"| {label} | {len(label_dists)} | {min(label_dists):.3f} | {max(label_dists):.3f} | {sum(label_dists)/len(label_dists):.3f} |\n")
                else:
                    f.write(f"| {label} | 0 | - | - | - |\n")
            f.write("\n")

        # Ensemble results
        f.write("## Ensemble Decision Results\n\n")
        valid_total = stats['verified_commands']
        if valid_total > 0:
            ensemble_acc = stats['ensemble']['correct'] / valid_total * 100
        else:
            ensemble_acc = 0

        f.write(f"- **Command Accuracy:** {ensemble_acc:.1f}% ({stats['ensemble']['correct']}/{valid_total})\n")
        f.write(f"- **False Negatives:** {stats['ensemble']['false_negative']}\n")
        f.write(f"- **Misclassifications:** {stats['ensemble']['misclassified']}\n\n")

        # Confusion matrix for ensemble
        f.write("### Ensemble Confusion Matrix\n\n")
        labels = ['START', 'JUMP', 'PAUSE', 'NONE', 'NOISE']
        cm = stats['ensemble']['confusion']

        f.write("| Actual \\ Predicted |")
        for pred in labels:
            f.write(f" {pred} |")
        f.write("\n")

        f.write("|" + "-" * 20 + "|")
        for _ in labels:
            f.write("------:|")
        f.write("\n")

        for actual in ['START', 'JUMP', 'PAUSE']:
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
        f.write("| # | Type | Ground Truth | Ensemble | mfcc_dtw | stats | mel | lpc |\n")
        f.write("|--:|:-----|:-------------|:---------|:---------|:------|:----|:----|\n")

        for i, record in enumerate(stats['records'], 1):
            rec_type = record['type']
            gt = record['ground_truth']
            ensemble = record['ensemble']

            ensemble_mark = "O" if ensemble == gt else "X"

            row = f"| {i} | {rec_type} | {gt} | {ensemble} {ensemble_mark} |"
            for method in methods:
                pred = record['predictions'][method]
                mark = "O" if pred == gt else "X"
                row += f" {pred} {mark} |"
            f.write(row + "\n")

        f.write("\n---\n")
        f.write("*O = Correct, X = Incorrect*\n")
        f.write("*AUTO = Automatically rejected as noise, not verified by user*\n")


def test_qa2():
    """QA test that only asks for feedback on detected commands."""
    print("=" * 80)
    print("Bio-Voice Commander - QA Test Mode 2 (Commands Only)")
    print("=" * 80)

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="QA test (commands only) for Bio-Voice Commander.")
    parser.add_argument(
        "--device-index",
        type=int,
        help="Specify the input audio device index to use."
    )
    parser.add_argument(
        "--no-noise-templates",
        action="store_true",
        help="Disable noise template collection"
    )
    parser.add_argument(
        "--noise-samples",
        type=int,
        default=5,
        help="Number of noise samples to collect (default: 5)"
    )
    parser.add_argument(
        "--method",
        type=str,
        choices=['mfcc_dtw', 'ensemble', 'adaptive_ensemble'],
        default='adaptive_ensemble',
        help="Recognition method: 'mfcc_dtw', 'ensemble' (fixed), or 'adaptive_ensemble' (SNR-based)"
    )
    args = parser.parse_args()

    # Load templates
    base_dir = locate_cmd_templates()

    # Configure matcher based on method
    if args.method == 'mfcc_dtw':
        methods = ['mfcc_dtw']
    else:
        # Both ensemble and adaptive_ensemble use all methods
        methods = ['mfcc_dtw', 'mel', 'lpc']
        
    matcher = MultiMethodMatcher(methods=methods)

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

    # Calibration phase
    print("\n" + "-" * 80)
    print("Calibration Phase - Please stay QUIET for 3 seconds")
    print("-" * 80)
    time.sleep(0.3)

    # Measure background RMS
    bg_rms = audio_stream.measure_background(1500)
    print(f"Background RMS: {bg_rms:.1f}")

    # Collect noise samples for rejection
    if not args.no_noise_templates:
        noise_samples = collect_noise_samples(audio_stream, duration_ms=2000, num_samples=args.noise_samples)
        print(f"Collected {len(noise_samples)} noise samples")

        for i, noise_audio in enumerate(noise_samples):
            matcher.add_noise_template(noise_audio)
            print(f"  Added noise template #{i+1} (len={len(noise_audio)})")

        print(f"Total noise templates: {matcher.get_noise_template_count()}")
    else:
        print("Noise template collection disabled")

    # Initialize VAD
    vad = VAD(background_rms=bg_rms)

    print("\n" + "=" * 80)
    print(f"QA Test Mode 2 - Only commands require verification ({args.method.upper()})")
    print("Commands: 開始(S), 跳(J), 暫停(P)")
    print("Noise/NONE detections are auto-recorded without user input")
    print("Press Ctrl+C or enter Q to finish and generate report")
    print("=" * 80)
    print()

    # Initialize statistics
    methods = list(matcher.matchers.keys())
    stats = {
        'total': 0,
        'auto_noise': 0,
        'verified_commands': 0,
        'processing_times': [],
        'vad_latencies': [],
        'records': [],
        'per_method': {
            m: {
                'correct': 0,
                'false_negative': 0,
                'misclassified': 0,
                'confusion': defaultdict(int),
                'distances': [],
                'noise_distances': [],
                'distances_by_label': defaultdict(list),
            } for m in methods
        },
        'ensemble': {
            'correct': 0,
            'false_negative': 0,
            'misclassified': 0,
            'confusion': defaultdict(int),
        }
    }

    vad_start_time = None
    last_state = VADState.SILENCE
    quit_flag = False
    paused = False  # Pause VAD processing while waiting for user input

    try:
        while not quit_flag:
            # Skip chunk processing if paused
            if paused:
                time.sleep(0.1)
                continue

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

                # Process with selected method
                total_start = time.time()
                
                # Determine adaptive mode
                use_adaptive = (args.method == 'adaptive_ensemble')
                
                raw_results = matcher.recognize(segment, mode='all', adaptive=use_adaptive)
                total_proc_time = (time.time() - total_start) * 1000
                stats['processing_times'].append(total_proc_time)

                # Compute decision based on selected method
                if args.method == 'mfcc_dtw':
                    # Use only MFCC+DTW
                    best_command = raw_results['all_results']['mfcc_dtw']['command']
                    best_method = 'mfcc_dtw'
                    best_confidence = 0.0
                else:
                    # Compute ensemble decision (Weighted)
                    # Note: For 'ensemble' and 'adaptive_ensemble', the weighted decision is already in raw_results['command']
                    # The logic below was manually re-implementing simple voting, which is now obsolete.
                    # We should use the result from matcher.recognize directly.
                    
                    best_command = raw_results['command']
                    best_confidence = raw_results.get('confidence', 0.0)
                    best_method = raw_results.get('method', 'ensemble')

                # Collect predictions for all methods (for reporting)
                predictions = {}
                for method, res in raw_results['all_results'].items():
                    predictions[method] = res['command']

                # Show results
                print(f"\nPredictions:")
                for method, res in raw_results['all_results'].items():
                    cmd = res['command']
                    dist = res['distance']
                    best_tpl = res['best_template']
                    noise_dist = res.get('noise_distance', float('inf'))
                    threshold = matcher.matchers[method].threshold
                    conf_pct = max(0, (1 - dist / threshold) * 100)

                    noise_info = ""
                    if noise_dist < float('inf'):
                        noise_info = f", noise_dist={noise_dist:.3f}"
                        if noise_dist < dist:
                            noise_info += " <CLOSER"

                    print(f"  {method:12s}: {cmd:8s} (dist={dist:.3f}, conf={conf_pct:.1f}%{noise_info}, tpl={best_tpl})")

                print(f"\n>>> ENSEMBLE: {best_command}", end="")
                if best_method:
                    print(f" (by {best_method}, conf={best_confidence*100:.1f}%, time={total_proc_time:.0f}ms)")
                else:
                    print(f" (time={total_proc_time:.0f}ms)")

                # Decision: ask user only if command detected
                if best_command in ('NOISE', 'NONE'):
                    # Auto-record as noise without asking
                    ground_truth = 'NOISE'
                    stats['auto_noise'] += 1
                    print(f"\n[AUTO] Recorded as NOISE (no user input needed)")

                    # Record
                    record = {
                        'type': 'AUTO',
                        'ground_truth': ground_truth,
                        'ensemble': best_command,
                        'predictions': predictions,
                    }
                    stats['records'].append(record)

                    print("=" * 80)
                    print()
                else:
                    # Detected a command - pause and ask user
                    paused = True
                    ground_truth = get_user_label()

                    if ground_truth is None:
                        quit_flag = True
                        stats['total'] -= 1
                        stats['vad_latencies'].pop()
                        stats['processing_times'].pop()
                        break

                    # Record
                    record = {
                        'type': 'VERIFIED',
                        'ground_truth': ground_truth,
                        'ensemble': best_command,
                        'predictions': predictions,
                    }
                    stats['records'].append(record)

                    # Update statistics for verified commands
                    if ground_truth != 'NOISE':
                        stats['verified_commands'] += 1

                        for method, pred in predictions.items():
                            res = raw_results['all_results'][method]
                            stats['per_method'][method]['distances'].append(res['distance'])
                            if res.get('noise_distance', float('inf')) < float('inf'):
                                stats['per_method'][method]['noise_distances'].append(res['noise_distance'])
                            stats['per_method'][method]['distances_by_label'][ground_truth].append(res['distance'])
                            stats['per_method'][method]['confusion'][(ground_truth, pred)] += 1

                            if pred == ground_truth:
                                stats['per_method'][method]['correct'] += 1
                            elif pred in ('NONE', 'NOISE'):
                                stats['per_method'][method]['false_negative'] += 1
                            else:
                                stats['per_method'][method]['misclassified'] += 1

                        stats['ensemble']['confusion'][(ground_truth, best_command)] += 1
                        if best_command == ground_truth:
                            stats['ensemble']['correct'] += 1
                        elif best_command in ('NONE', 'NOISE'):
                            stats['ensemble']['false_negative'] += 1
                        else:
                            stats['ensemble']['misclassified'] += 1

                    # Show running accuracy
                    if stats['verified_commands'] > 0:
                        ens_acc = stats['ensemble']['correct'] / stats['verified_commands'] * 100
                        print(f"\n[Running] Command accuracy: {ens_acc:.1f}% ({stats['ensemble']['correct']}/{stats['verified_commands']})")

                    print(f"[Info] Total: {stats['total']}, Auto-noise: {stats['auto_noise']}, Verified: {stats['verified_commands']}")
                    print("=" * 80)
                    print()

                    # Resume
                    paused = False

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
        output_path = os.path.join(record_dir, f'test_qa2_{timestamp}.md')

        print(f"\nGenerating report to: {output_path}")
        generate_report(stats, matcher, output_path)
        print("Report generated successfully!")

        # Print summary
        print("\n" + "=" * 80)
        print("Final Summary")
        print("=" * 80)
        print(f"Total samples: {stats['total']}")
        print(f"Auto-rejected noise: {stats['auto_noise']}")
        print(f"Verified commands: {stats['verified_commands']}")

        if stats['verified_commands'] > 0:
            print(f"\nCommand Accuracy (on {stats['verified_commands']} verified commands):")
            for method in methods:
                acc = stats['per_method'][method]['correct'] / stats['verified_commands'] * 100
                print(f"  {method:12s}: {acc:.1f}%")
            ens_acc = stats['ensemble']['correct'] / stats['verified_commands'] * 100
            print(f"  {'ENSEMBLE':12s}: {ens_acc:.1f}%")
        print("=" * 80)
    else:
        print("\nNo samples collected. Report not generated.")


if __name__ == '__main__':
    test_qa2()
