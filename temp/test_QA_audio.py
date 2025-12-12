"""
QA test with VoiceController (same as app.py) for confusion matrix evaluation.

This script:
1. Uses VoiceController (same audio processing as app.py)
2. Records live microphone input
3. User provides ground truth labels
4. Generates confusion matrix visualization
"""

import sys
import os
import time
import argparse
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from collections import defaultdict
from pathlib import Path

# Ensure the project root is in the Python path
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_current_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.audio.controller import VoiceController
from src.event_bus import EventBus, EventType
from src import config


# Label mapping for user input
LABEL_MAP = {
    'S': 'START',
    's': 'START',
    'J': 'JUMP',
    'j': 'JUMP',
    'F': 'FLIP',
    'f': 'FLIP',
    'P': 'PAUSE',
    'p': 'PAUSE',
    'N': 'NOISE',
    'n': 'NOISE',
}

LABEL_DISPLAY = {
    'START': 'S(開始)',
    'JUMP': 'J(跳)',
    'FLIP': 'F(翻)',
    'PAUSE': 'P(暫停)',
    'NOISE': 'N(噪音)',
    'NONE': 'NONE',
}


def get_user_label():
    """Get ground truth label from user."""
    while True:
        try:
            user_input = input("\n>>> Enter correct label [S=開始, J=跳, F=翻, P=暫停, N=噪音, Q=結束]: ").strip()
            if user_input.upper() == 'Q':
                return None  # Signal to quit
            if user_input in LABEL_MAP:
                return LABEL_MAP[user_input]
            print("Invalid input. Please enter S, J, F, P, N, or Q.")
        except EOFError:
            return None


def plot_confusion_matrix(confusion_dict, labels, output_path, title="Confusion Matrix"):
    """
    Plot confusion matrix as heatmap.

    Args:
        confusion_dict: Dictionary with (actual, predicted) -> count
        labels: List of label names
        output_path: Path to save the figure
        title: Plot title
    """
    # Build confusion matrix
    n = len(labels)
    cm = np.zeros((n, n), dtype=int)

    label_to_idx = {label: i for i, label in enumerate(labels)}

    for (actual, predicted), count in confusion_dict.items():
        if actual in label_to_idx and predicted in label_to_idx:
            cm[label_to_idx[actual], label_to_idx[predicted]] = count

    # Plot
    plt.figure(figsize=(10, 8))
    sns.heatmap(
        cm,
        annot=True,
        fmt='d',
        cmap='Blues',
        xticklabels=labels,
        yticklabels=labels,
        cbar_kws={'label': 'Count'}
    )
    plt.xlabel('Predicted', fontsize=12)
    plt.ylabel('Actual', fontsize=12)
    plt.title(title, fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"[Report] Confusion matrix saved to: {output_path}")
    plt.close()


def generate_report(stats, output_dir, method_name):
    """
    Generate markdown report and confusion matrix plot.

    Args:
        stats: Statistics dictionary
        output_dir: Directory to save outputs
        method_name: Recognition method name
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Markdown report
    report_path = os.path.join(output_dir, f'test_audio_{method_name}_{timestamp}.md')

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# Voice Recognition QA Test Report (VoiceController)\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Method:** {method_name}\n\n")

        # Overall summary
        f.write("## Overall Summary\n\n")
        f.write(f"- **Total samples:** {stats['total']}\n")
        f.write(f"- **Noise samples (ground truth):** {stats['noise_count']}\n")
        f.write(f"- **Valid command samples:** {stats['total'] - stats['noise_count']}\n\n")

        # Results
        valid_total = stats['total'] - stats['noise_count']
        if valid_total > 0:
            accuracy = stats['correct'] / valid_total * 100
        else:
            accuracy = 0

        # Noise rejection accuracy
        if stats['noise_count'] > 0:
            noise_rejected = stats['noise_correctly_rejected']
            noise_acc = noise_rejected / stats['noise_count'] * 100
        else:
            noise_acc = 0

        f.write("## Results\n\n")
        f.write(f"- **Command Accuracy:** {accuracy:.1f}% ({stats['correct']}/{valid_total})\n")
        f.write(f"- **Noise Rejection Accuracy:** {noise_acc:.1f}% ({stats['noise_correctly_rejected']}/{stats['noise_count']})\n")
        f.write(f"- **False Positives (NOISE detected as command):** {stats['false_positive']}\n")
        f.write(f"- **False Negatives (Command detected as NONE/NOISE):** {stats['false_negative']}\n")
        f.write(f"- **Misclassifications:** {stats['misclassified']}\n\n")

        # Confusion matrix (text)
        f.write("## Confusion Matrix\n\n")
        labels = ['START', 'JUMP', 'FLIP', 'PAUSE', 'NONE', 'NOISE']
        cm = stats['confusion']

        f.write("| Actual \\ Predicted |")
        for pred in labels:
            f.write(f" {pred} |")
        f.write("\n")

        f.write("|" + "-" * 20 + "|")
        for _ in labels:
            f.write("------:|")
        f.write("\n")

        for actual in ['START', 'JUMP', 'FLIP', 'PAUSE', 'NOISE']:
            f.write(f"| **{actual}** |")
            for pred in labels:
                count = cm.get((actual, pred), 0)
                f.write(f" {count} |")
            f.write("\n")
        f.write("\n")

        # Timing statistics
        f.write("## Timing Statistics\n\n")
        if stats['latencies']:
            avg_lat = sum(stats['latencies']) / len(stats['latencies'])
            f.write(f"- **Processing Latency (Avg):** {avg_lat:.1f}ms\n")
            f.write(f"- **Processing Latency (Min):** {min(stats['latencies']):.1f}ms\n")
            f.write(f"- **Processing Latency (Max):** {max(stats['latencies']):.1f}ms\n\n")

        if stats['snr_values']:
            avg_snr = sum(stats['snr_values']) / len(stats['snr_values'])
            f.write(f"- **SNR (Avg):** {avg_snr:.1f}dB\n")
            f.write(f"- **SNR (Min):** {min(stats['snr_values']):.1f}dB\n")
            f.write(f"- **SNR (Max):** {max(stats['snr_values']):.1f}dB\n\n")

        # Detailed log
        f.write("## Detailed Test Log\n\n")
        f.write("| # | Ground Truth | Predicted | Confidence | Latency (ms) | SNR (dB) | Result |\n")
        f.write("|--:|:-------------|:----------|----------:|-------------:|---------:|:------:|\n")

        for i, record in enumerate(stats['records'], 1):
            gt = record['ground_truth']
            pred = record['predicted']
            conf = record['confidence']
            lat = record['latency']
            snr = record['snr']

            # For NOISE ground truth: NONE or NOISE prediction is correct
            if gt == 'NOISE':
                result_mark = "✓" if pred in ('NONE', 'NOISE') else "✗"
            else:
                result_mark = "✓" if pred == gt else "✗"

            f.write(f"| {i} | {gt} | {pred} | {conf:.2f} | {lat:.1f} | {snr:.1f} | {result_mark} |\n")

        f.write("\n---\n")
        f.write("*✓ = Correct, ✗ = Incorrect*\n")
        f.write("*NOISE samples: NONE or NOISE prediction is considered correct*\n")

    print(f"[Report] Markdown report saved to: {report_path}")

    # Confusion matrix plot
    plot_labels = ['START', 'JUMP', 'FLIP', 'PAUSE', 'NOISE']
    cm_path = os.path.join(output_dir, f'confusion_matrix_{method_name}_{timestamp}.png')
    plot_confusion_matrix(
        stats['confusion'],
        plot_labels,
        cm_path,
        title=f"Confusion Matrix - {method_name.upper()}"
    )


def test_qa_audio():
    """QA test using VoiceController (same as app.py)."""
    print("=" * 80)
    print("Bio-Voice Commander - QA Test with VoiceController")
    print("=" * 80)

    # Parse arguments
    parser = argparse.ArgumentParser(
        description="QA test for voice recognition using VoiceController (same as app.py)"
    )
    parser.add_argument(
        "--method",
        type=str,
        choices=['mfcc_dtw', 'ensemble', 'adaptive_ensemble'],
        default='mfcc_dtw',
        help="Recognition method (default: mfcc_dtw)"
    )
    parser.add_argument(
        "--template-dir",
        type=str,
        default=None,
        help="Template directory (default: cmd_templates)"
    )
    args = parser.parse_args()

    # Initialize EventBus
    event_bus = EventBus()
    event_bus.start()

    # Store recognized commands
    recognized_commands = []
    command_lock = __import__('threading').Lock()

    def on_voice_command(event):
        """Callback for voice commands."""
        with command_lock:
            recognized_commands.append(event.data)

    def on_voice_noise(event):
        """Callback for noise events."""
        with command_lock:
            recognized_commands.append({
                'command': 'NOISE',
                'action': 'NOISE',
                'confidence': 0.0,
                'latency_ms': 0.0,
                'snr': event.data.get('snr', 0.0)
            })

    # Subscribe to events
    event_bus.subscribe(EventType.VOICE_COMMAND, on_voice_command)
    event_bus.subscribe(EventType.VOICE_NOISE, on_voice_noise)

    # Initialize VoiceController
    print(f"\n[Main] Initializing VoiceController (method={args.method})")
    voice_controller = VoiceController(
        template_dir=args.template_dir,
        event_bus=event_bus,
        method=args.method
    )

    try:
        voice_controller.start()
    except Exception as e:
        print(f"[ERROR] Failed to start VoiceController: {e}")
        event_bus.stop()
        return

    print("\n" + "=" * 80)
    print(f"QA Test Mode - Say commands and provide correct labels ({args.method.upper()})")
    print("Commands: 開始(S), 跳(J), 翻(F), 暫停(P), 噪音(N)")
    print("Press Ctrl+C or enter Q to finish and generate report")
    print("=" * 80)
    print()

    # Initialize statistics
    stats = {
        'total': 0,
        'noise_count': 0,
        'correct': 0,
        'false_positive': 0,
        'false_negative': 0,
        'misclassified': 0,
        'noise_correctly_rejected': 0,
        'confusion': defaultdict(int),
        'records': [],
        'latencies': [],
        'snr_values': [],
    }

    quit_flag = False
    last_command_count = 0
    waiting_for_input = False

    try:
        while not quit_flag:
            time.sleep(0.1)

            # Check for new commands (only if not waiting for user input)
            with command_lock:
                current_count = len(recognized_commands)

            if current_count > last_command_count and not waiting_for_input:
                # New command detected
                with command_lock:
                    cmd_data = recognized_commands[last_command_count]
                    last_command_count = current_count

                predicted = cmd_data['command']
                confidence = cmd_data.get('confidence', 0.0)
                latency = cmd_data.get('latency_ms', 0.0)
                snr = cmd_data.get('snr', 0.0)

                stats['total'] += 1

                print(f"\r" + "=" * 80)
                print(f"[Sample #{stats['total']}]")
                print("-" * 80)
                print(f"Predicted: {predicted}")
                print(f"Confidence: {confidence:.2f}")
                print(f"Latency: {latency:.1f}ms")
                print(f"SNR: {snr:.1f}dB")

                # Temporarily stop voice controller while waiting for input
                waiting_for_input = True
                voice_controller.stop()

                # Get user label
                ground_truth = get_user_label()

                if ground_truth is None:
                    quit_flag = True
                    stats['total'] -= 1  # Don't count this sample
                    break

                # Resume voice controller after getting input
                try:
                    voice_controller.start()
                    waiting_for_input = False
                except Exception as e:
                    print(f"[ERROR] Failed to restart VoiceController: {e}")
                    quit_flag = True
                    break

                # Record
                record = {
                    'ground_truth': ground_truth,
                    'predicted': predicted,
                    'confidence': confidence,
                    'latency': latency,
                    'snr': snr,
                }
                stats['records'].append(record)
                stats['latencies'].append(latency)
                stats['snr_values'].append(snr)

                # Update statistics
                if ground_truth == 'NOISE':
                    stats['noise_count'] += 1
                    stats['confusion'][('NOISE', predicted)] += 1

                    if predicted in ('NONE', 'NOISE'):
                        stats['noise_correctly_rejected'] += 1
                    else:
                        stats['false_positive'] += 1
                else:
                    # Valid command
                    stats['confusion'][(ground_truth, predicted)] += 1

                    if predicted == ground_truth:
                        stats['correct'] += 1
                    elif predicted in ('NONE', 'NOISE'):
                        stats['false_negative'] += 1
                    else:
                        stats['misclassified'] += 1

                # Show running accuracy
                valid = stats['total'] - stats['noise_count']
                if valid > 0:
                    acc = stats['correct'] / valid * 100
                    print(f"\n[Running] Command accuracy: {acc:.1f}% ({stats['correct']}/{valid})")
                if stats['noise_count'] > 0:
                    noise_rej = stats['noise_correctly_rejected'] / stats['noise_count'] * 100
                    print(f"[Running] Noise rejection: {noise_rej:.1f}% ({stats['noise_correctly_rejected']}/{stats['noise_count']})")

                print("=" * 80)
                print()

    except KeyboardInterrupt:
        print("\n\nStopping...")
    finally:
        voice_controller.stop()
        event_bus.stop()

    # Generate report
    if stats['total'] > 0:
        # Ensure record directory exists
        record_dir = os.path.join(_project_root, 'temp', 'record')
        os.makedirs(record_dir, exist_ok=True)

        print(f"\n[Report] Generating report to: {record_dir}")
        generate_report(stats, record_dir, args.method)

        # Print summary
        print("\n" + "=" * 80)
        print("Final Summary")
        print("=" * 80)
        print(f"Total samples: {stats['total']}")
        print(f"Noise samples: {stats['noise_count']}")
        valid = stats['total'] - stats['noise_count']

        if valid > 0:
            acc = stats['correct'] / valid * 100
            print(f"\nCommand Accuracy: {acc:.1f}% ({stats['correct']}/{valid})")

        if stats['noise_count'] > 0:
            noise_acc = stats['noise_correctly_rejected'] / stats['noise_count'] * 100
            print(f"Noise Rejection Accuracy: {noise_acc:.1f}% ({stats['noise_correctly_rejected']}/{stats['noise_count']})")

        print("=" * 80)
    else:
        print("\nNo samples collected. Report not generated.")


if __name__ == '__main__':
    test_qa_audio()
