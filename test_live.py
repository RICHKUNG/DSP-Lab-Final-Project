"""Live microphone test with detailed metrics."""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.audio_io import AudioStream, find_suitable_device
from src.vad import VAD, VADState
from src.recognizers import MultiMethodMatcher
from src import config


def test_live_recognition():
    """Test real-time recognition with microphone."""
    print("=" * 70)
    print("Bio-Voice Commander - Live Microphone Test")
    print("=" * 70)

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
        print("Please ensure audio files with Chinese command names are in the directory.")
        return

    # Find suitable audio device
    print("\n" + "=" * 70)
    print("Finding suitable audio device...")
    device_info = find_suitable_device(config.SAMPLE_RATE, verbose=True)

    if device_info is None:
        print("[ERROR] Cannot access any audio input device!")
        print("\nThis is likely a Windows permissions issue.")
        print("\nQuick fix:")
        print("  1. Go to Settings > Privacy & Security > Microphone")
        print("  2. Enable 'Let apps access your microphone'")
        print("  3. Enable 'Let desktop apps access your microphone'")
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

    print("Calibrating background noise (please stay quiet for 1.5 seconds)...")
    time.sleep(0.3)
    bg_rms = audio_stream.measure_background(1500)
    print(f"Background RMS: {bg_rms:.1f}")

    # Initialize VAD
    vad = VAD(background_rms=bg_rms)

    print("\n" + "=" * 70)
    print("Listening for commands...")
    print("Say: 開始, 暫停, 跳, 磁鐵, or 反轉")
    print("Press Ctrl+C to stop")
    print("=" * 70)

    try:
        # Statistics
        stats = {
            'total_detections': 0,
            'successful_matches': 0,
            'processing_times': [],
            'vad_times': []
        }

        vad_start_time = None

        while True:
            chunk = audio_stream.get_chunk(timeout=0.1)
            if len(chunk) == 0:
                continue

            state, segment = vad.process_chunk(chunk)

            # Track when speech starts
            if state == VADState.RECORDING and vad_start_time is None:
                vad_start_time = time.time()

            if state == VADState.PROCESSING and segment is not None:
                # Calculate VAD time
                vad_time = (time.time() - vad_start_time) * 1000 if vad_start_time else 0
                stats['vad_times'].append(vad_time)

                stats['total_detections'] += 1
                segment_duration = len(segment) / config.SAMPLE_RATE

                print(f"\n[Detection #{stats['total_detections']}]")
                print(f"  Speech duration: {segment_duration:.2f}s")
                print(f"  VAD time: {vad_time:.0f}ms")

                # Process with all methods
                start_time = time.time()
                result = matcher.recognize(segment, mode='all')
                proc_time = (time.time() - start_time) * 1000
                stats['processing_times'].append(proc_time)

                total_time = vad_time + proc_time

                print(f"  Processing time: {proc_time:.0f}ms")
                print(f"  Total latency: {total_time:.0f}ms")
                print()

                # Show results from all methods
                has_match = False
                for method, res in result['all_results'].items():
                    cmd = res['command']
                    dist = res['distance']
                    threshold = matcher.matchers[method].threshold

                    if cmd != 'NONE':
                        status = f"✓ MATCH (conf={(1-dist/threshold)*100:.0f}%)"
                        has_match = True
                    else:
                        status = "✗ NO MATCH"

                    print(f"  {method:12s}: {cmd:8s} (dist={dist:6.2f}, th={threshold:5.1f}) {status}")

                if has_match:
                    stats['successful_matches'] += 1

                print()
                print("-" * 70)

                # Reset VAD
                vad.reset()
                vad_start_time = None

    except KeyboardInterrupt:
        print("\n\nStopping...")
    finally:
        audio_stream.stop()

    # Print statistics
    print("\n" + "=" * 70)
    print("Session Statistics")
    print("=" * 70)
    print(f"Total detections: {stats['total_detections']}")
    print(f"Successful matches: {stats['successful_matches']}")
    if stats['total_detections'] > 0:
        accuracy = stats['successful_matches'] / stats['total_detections'] * 100
        print(f"Match rate: {accuracy:.1f}%")

    if stats['processing_times']:
        print(f"\nProcessing time:")
        print(f"  Average: {sum(stats['processing_times'])/len(stats['processing_times']):.0f}ms")
        print(f"  Min: {min(stats['processing_times']):.0f}ms")
        print(f"  Max: {max(stats['processing_times']):.0f}ms")

    if stats['vad_times']:
        print(f"\nVAD detection time:")
        print(f"  Average: {sum(stats['vad_times'])/len(stats['vad_times']):.0f}ms")

    if stats['processing_times'] and stats['vad_times']:
        total_times = [v + p for v, p in zip(stats['vad_times'], stats['processing_times'])]
        print(f"\nTotal latency (VAD + Processing):")
        print(f"  Average: {sum(total_times)/len(total_times):.0f}ms")
        print(f"  Max: {max(total_times):.0f}ms")

        if max(total_times) <= 300:
            print("\n✓ Meets latency requirement (≤ 300ms)")
        else:
            print("\n✗ Exceeds latency requirement (≤ 300ms)")

    print("=" * 70)


if __name__ == '__main__':
    test_live_recognition()
