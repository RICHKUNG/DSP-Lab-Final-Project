"""Live microphone test with detailed metrics for parameter tuning."""

import sys
import os
import time
import argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
    print("Listening for commands... (Real-time mode)")
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
            'per_method_times': {m: [] for m in matcher.matchers.keys()},
            'distances': {m: [] for m in matcher.matchers.keys()},
            'noise_distances': {m: [] for m in matcher.matchers.keys()},
            'vad_latencies': []
        }

        vad_start_time = None
        last_state = VADState.SILENCE

        while True:
            # Use smaller timeout for better responsiveness
            chunk = audio_stream.get_chunk(timeout=0.02)
            if len(chunk) == 0:
                continue

            state, segment = vad.process_chunk(chunk)

            # Track when speech starts
            if state == VADState.RECORDING and last_state == VADState.SILENCE:
                vad_start_time = time.time()
                # Show recording indicator
                print("\r[Recording...]", end='', flush=True)

            last_state = state

            if state == VADState.PROCESSING and segment is not None:
                vad_end_time = time.time()
                vad_latency = (vad_end_time - vad_start_time) * 1000 if vad_start_time else 0
                stats['vad_latencies'].append(vad_latency)

                stats['total_detections'] += 1
                segment_duration = len(segment) / config.SAMPLE_RATE

                # Clear recording indicator and print header
                print(f"\r" + "=" * 80)
                print(f"[Detection #{stats['total_detections']}] Duration: {segment_duration:.2f}s | VAD latency: {vad_latency:.0f}ms")
                print("-" * 80)

                # Process with all methods and measure time for each
                total_start = time.time()
                raw_results = matcher.recognize(segment, mode='all')
                total_proc_time = (time.time() - total_start) * 1000
                stats['processing_times'].append(total_proc_time)

                # Compute ensemble decision manually
                best_command = 'NONE'
                best_confidence = 0.0
                best_method = None
                best_template = ''
                noise_votes = 0

                for method, res in raw_results['all_results'].items():
                    cmd = res['command']
                    dist = res['distance']
                    noise_dist = res.get('noise_distance', float('inf'))
                    threshold = matcher.matchers[method].threshold

                    stats['distances'][method].append(dist)
                    if noise_dist < float('inf'):
                        stats['noise_distances'][method].append(noise_dist)

                    if cmd == 'NOISE':
                        noise_votes += 1
                    elif cmd not in ('NONE', 'NOISE'):
                        conf = 1 - min(dist / threshold, 1)
                        if conf > best_confidence:
                            best_confidence = conf
                            best_command = cmd
                            best_method = method
                            best_template = res['best_template']

                # If majority say NOISE, override
                if noise_votes > len(raw_results['all_results']) // 2:
                    best_command = 'NOISE'

                # Show detailed results for each method
                for method, res in raw_results['all_results'].items():
                    cmd = res['command']
                    dist = res['distance']
                    best_tpl = res['best_template']
                    all_dists = res['all_distances']
                    noise_dist = res.get('noise_distance', float('inf'))
                    threshold = matcher.matchers[method].threshold

                    # Calculate margin (how far from threshold)
                    margin = threshold - dist
                    margin_pct = (margin / threshold) * 100

                    if cmd == 'NOISE':
                        status = "NOISE"
                    elif cmd == 'NONE':
                        status = "NO MATCH"
                    else:
                        status = "MATCH"
                    conf_pct = max(0, (1 - dist / threshold) * 100)

                    print(f"\n[{method}] {status}")
                    print(f"  Best match: {best_tpl} (dist={dist:.3f}, conf={conf_pct:.1f}%)")
                    if noise_dist < float('inf'):
                        print(f"  Noise dist: {noise_dist:.3f} {'<-- CLOSER' if noise_dist < dist else ''}")
                    print(f"  Threshold: {threshold:.2f} | Margin: {margin:.2f} ({margin_pct:+.1f}%)")

                    # Show top N closest templates
                    print(f"  Top {args.top_n} closest templates:")
                    for i, (tpl_cmd, tpl_name, tpl_dist) in enumerate(all_dists[:args.top_n]):
                        tpl_margin = threshold - tpl_dist
                        marker = " <--" if i == 0 else ""
                        print(f"    {i+1}. {tpl_name:15s} ({tpl_cmd:6s}) dist={tpl_dist:7.3f} margin={tpl_margin:+7.2f}{marker}")

                # Show final decision
                print()
                print("-" * 80)
                if best_command == 'NOISE':
                    stats['noise_detections'] += 1
                    print(f">>> DECISION: NOISE (rejected - closer to noise templates)")
                elif best_command != 'NONE':
                    stats['successful_matches'] += 1
                    print(f">>> DECISION: {best_command} (by {best_method}, conf={best_confidence*100:.1f}%, template={best_template})")
                else:
                    print(f">>> DECISION: NO MATCH (all methods below threshold)")
                print(f">>> Total processing time: {total_proc_time:.1f}ms")
                print("=" * 80)
                print()

                # Reset VAD
                vad.reset()
                vad_start_time = None

    except KeyboardInterrupt:
        print("\n\nStopping...")
    finally:
        audio_stream.stop()

    # Print detailed statistics
    print("\n" + "=" * 80)
    print("Session Statistics (for parameter tuning)")
    print("=" * 80)

    print(f"\n[Overall]")
    print(f"  Total detections: {stats['total_detections']}")
    print(f"  Successful matches: {stats['successful_matches']}")
    print(f"  Noise rejections: {stats['noise_detections']}")
    print(f"  No match: {stats['total_detections'] - stats['successful_matches'] - stats['noise_detections']}")
    if stats['total_detections'] > 0:
        match_rate = stats['successful_matches'] / stats['total_detections'] * 100
        noise_rate = stats['noise_detections'] / stats['total_detections'] * 100
        print(f"  Match rate: {match_rate:.1f}%")
        print(f"  Noise rejection rate: {noise_rate:.1f}%")

    if stats['processing_times']:
        print(f"\n[Processing Time]")
        avg_time = sum(stats['processing_times']) / len(stats['processing_times'])
        print(f"  Average: {avg_time:.1f}ms")
        print(f"  Min: {min(stats['processing_times']):.1f}ms")
        print(f"  Max: {max(stats['processing_times']):.1f}ms")

    if stats['vad_latencies']:
        print(f"\n[VAD Latency (speech start to segment ready)]")
        avg_lat = sum(stats['vad_latencies']) / len(stats['vad_latencies'])
        print(f"  Average: {avg_lat:.0f}ms")
        print(f"  Min: {min(stats['vad_latencies']):.0f}ms")
        print(f"  Max: {max(stats['vad_latencies']):.0f}ms")

    # Distance statistics per method (for threshold tuning)
    print(f"\n[Distance Statistics per Method (for threshold tuning)]")
    for method in matcher.matchers.keys():
        dists = stats['distances'].get(method, [])
        noise_dists = stats['noise_distances'].get(method, [])
        if dists:
            threshold = matcher.matchers[method].threshold
            print(f"\n  {method}:")
            print(f"    Current threshold: {threshold:.2f}")
            print(f"    Command distances:")
            print(f"      Min: {min(dists):.3f}")
            print(f"      Max: {max(dists):.3f}")
            print(f"      Avg: {sum(dists)/len(dists):.3f}")
            if noise_dists:
                print(f"    Noise distances:")
                print(f"      Min: {min(noise_dists):.3f}")
                print(f"      Max: {max(noise_dists):.3f}")
                print(f"      Avg: {sum(noise_dists)/len(noise_dists):.3f}")
            # Suggest threshold if needed
            if min(dists) > threshold:
                print(f"    Suggestion: Increase threshold (all dists > current threshold)")
            elif max(dists) < threshold * 0.5:
                print(f"    Suggestion: Could decrease threshold (all dists < 50% of threshold)")

    print("\n" + "=" * 80)


if __name__ == '__main__':
    test_live_recognition()
