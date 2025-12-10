"""Live microphone test with detailed metrics for parameter tuning."""

import sys
import os
import time
import argparse
import numpy as np

# Ensure the project root is in the Python path for module imports
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_current_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.audio_io import AudioStream, find_suitable_device
from src.vad import VAD, VADState
from src.recognizers import MultiMethodMatcher
from src import config


def collect_noise_samples(audio_stream, duration_ms=2000, num_samples=5):
    """
    Collect noise samples from background audio.

    Args:
        audio_stream: AudioStream instance
        duration_ms: Total duration to collect
        num_samples: Number of noise samples to extract

    Returns:
        List of noise audio segments
    """
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
        # Always use the segment, even if it's quiet
        if len(segment) > 0:
            noise_samples.append(segment)

    return noise_samples


def test_live_recognition():
    """Test real-time recognition with microphone."""
    print("=" * 80)
    print("Bio-Voice Commander - Live Microphone Test (Parameter Tuning Mode)")
    print("=" * 80)

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Live microphone test for Bio-Voice Commander.")
    parser.add_argument(
        "--device-index",
        type=int,
        help="Specify the input audio device index to use. Skips automatic detection."
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=3,
        help="Show top N closest templates for each method (default: 3)"
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
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
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
                tpl_names = m.template_names.get(cmd, [])
                print(f"    - {cmd}: {len(templates)} samples ({', '.join(tpl_names)})")

    total_templates = sum(len(t) for m in matcher.matchers.values()
                          for t in m.templates.values())
    if total_templates == 0:
        print("\n[ERROR] No templates found!")
        print("Please ensure audio files with Chinese command names are in the directory.")
        return

    # Print current thresholds
    print("\n" + "-" * 80)
    print("Current Thresholds (from config.py):")
    print("-" * 80)
    for method, m in matcher.matchers.items():
        print(f"  {method:12s}: {m.threshold:.2f}")

    # Find suitable audio device or use specified
    print("\n" + "=" * 80)
    print("Finding suitable audio device...")
    device_info = find_suitable_device(config.SAMPLE_RATE, verbose=True, preferred_device_index=args.device_index)

    if device_info is None:
        print("[ERROR] Cannot access any audio input device!")
        print("\nThis is likely a Windows permissions issue or exclusive mode issue.")
        print("\nQuick fix:")
        print("  1. Go to Settings > Privacy & Security > Microphone")
        print("  2. Enable 'Let apps access your microphone'")
        print("  3. Enable 'Let desktop apps access your microphone'")
        print("  4. In Sound Settings -> Recording tab -> Device Properties -> Advanced Tab, uncheck 'Allow applications to take exclusive control of this device'.")
        print("\nFor detailed troubleshooting, see: temp/AUDIO_TROUBLESHOOTING.md")
        print("Or run: python temp/audio_diagnostic.py")
        return

    device_index, device_rate = device_info
    print(f"Using audio device index: {device_index}")
    if device_rate != config.SAMPLE_RATE:
        print(f"Device native rate: {device_rate} Hz (will resample to {config.SAMPLE_RATE} Hz)")

    # Start audio stream
    print("Starting audio stream...")
    audio_stream = AudioStream(
        device_index=device_index,
        input_rate=device_rate,
        target_rate=config.SAMPLE_RATE,
    )
    audio_stream.start()

    # Calibration phase - collect background RMS AND noise samples
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

        # Add noise samples to matcher
        for i, noise_audio in enumerate(noise_samples):
            matcher.add_noise_template(noise_audio)
            print(f"  Added noise template #{i+1} (len={len(noise_audio)})")

        print(f"Total noise templates: {matcher.get_noise_template_count()}")
    else:
        print("Noise template collection disabled")

    # Initialize VAD
    vad = VAD(background_rms=bg_rms)

    print("\n" + "=" * 80)
    print(f"Listening for commands... (High-speed mode - {args.method.upper()})")
    print("Say: 開始, 暫停, 跳")
    print("Press Ctrl+C to stop")
    print("=" * 80)
    print()

    try:
        # Statistics
        stats = {
            'total_detections': 0,
            'successful_matches': 0,
            'noise_detections': 0,
            'processing_times': [],
            'vad_latencies': []
        }

        vad_start_time = None
        last_state = VADState.SILENCE

        while True:
            # Use smaller timeout for better responsiveness
            chunk = audio_stream.get_chunk(timeout=0.01)
            if len(chunk) == 0:
                continue

            state, segment = vad.process_chunk(chunk)

            # Track when speech starts
            if state == VADState.RECORDING and last_state == VADState.SILENCE:
                vad_start_time = time.time()
                # Show recording indicator on same line
                print("\r[錄音中...]     ", end='', flush=True)

            last_state = state

            if state == VADState.PROCESSING and segment is not None:
                vad_end_time = time.time()
                vad_latency = (vad_end_time - vad_start_time) * 1000 if vad_start_time else 0
                stats['vad_latencies'].append(vad_latency)
                stats['total_detections'] += 1

                # Process with selected method
                total_start = time.time()
                if args.method == 'mfcc_dtw':
                    # Use only MFCC+DTW method
                    results = matcher.recognize(segment, mode='all', adaptive=False)
                    command = results['all_results']['mfcc_dtw']['command']
                elif args.method == 'ensemble':
                    # Use standard ensemble (fixed weights)
                    results = matcher.recognize(segment, mode='ensemble', adaptive=False)
                    command = results['command']
                else:
                    # Use adaptive ensemble (SNR-based)
                    results = matcher.recognize(segment, mode='ensemble', adaptive=True)
                    command = results['command']
                total_proc_time = (time.time() - total_start) * 1000
                stats['processing_times'].append(total_proc_time)

                # Update stats
                if command == 'NOISE':
                    stats['noise_detections'] += 1
                elif command != 'NONE':
                    stats['successful_matches'] += 1

                # Print result on same line with \r
                if command == 'NOISE':
                    display = f"[噪音] #{stats['total_detections']} | 噪音偵測 | 處理時間:{total_proc_time:.0f}ms"
                elif command == 'NONE':
                    display = f"[無匹配] #{stats['total_detections']} | 無法識別 | 處理時間:{total_proc_time:.0f}ms"
                else:
                    display = f"[指令:{command}] #{stats['total_detections']} | 成功識別 | 處理時間:{total_proc_time:.0f}ms"

                # Print with padding to clear previous line
                print(f"\r{display:<80}", end='', flush=True)

                # Reset VAD
                vad.reset()
                vad_start_time = None

    except KeyboardInterrupt:
        print("\n\nStopping...")
    finally:
        audio_stream.stop()

    # Print simple statistics
    print("\n" + "=" * 80)
    print("Session Statistics")
    print("=" * 80)

    print(f"\n總偵測次數: {stats['total_detections']}")
    print(f"成功識別指令: {stats['successful_matches']}")
    print(f"噪音拒絕: {stats['noise_detections']}")
    print(f"無匹配: {stats['total_detections'] - stats['successful_matches'] - stats['noise_detections']}")

    if stats['total_detections'] > 0:
        match_rate = stats['successful_matches'] / stats['total_detections'] * 100
        noise_rate = stats['noise_detections'] / stats['total_detections'] * 100
        print(f"\n指令識別率: {match_rate:.1f}%")
        print(f"噪音拒絕率: {noise_rate:.1f}%")

    if stats['processing_times']:
        avg_time = sum(stats['processing_times']) / len(stats['processing_times'])
        print(f"\n平均處理時間: {avg_time:.1f}ms")
        print(f"最快: {min(stats['processing_times']):.1f}ms")
        print(f"最慢: {max(stats['processing_times']):.1f}ms")

    if stats['vad_latencies']:
        avg_lat = sum(stats['vad_latencies']) / len(stats['vad_latencies'])
        print(f"\n平均VAD延遲: {avg_lat:.0f}ms")
        print(f"最小: {min(stats['vad_latencies']):.0f}ms")
        print(f"最大: {max(stats['vad_latencies']):.0f}ms")

    print("=" * 80)


if __name__ == '__main__':
    test_live_recognition()
