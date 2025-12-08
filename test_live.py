"""Live microphone test with detailed metrics."""

import sys
import os
import time
import argparse

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

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Live microphone test for Bio-Voice Commander.")
    parser.add_argument(
        "--device-index",
        type=int,
        help="Specify the input audio device index to use. Skips automatic detection."
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
        print("Please ensure audio files with Chinese command names are in the directory.")
        return

    # Find suitable audio device or use specified
    print("\n" + "=" * 70)
    if args.device_index is not None:
        print(f"Attempting to use specified device index: {args.device_index}")
        # Need to re-check if this device works and its rate
        pa = pyaudio.PyAudio()
        try:
            info = pa.get_device_info_by_index(args.device_index)
            if info.get('maxInputChannels', 0) > 0:
                device_index = args.device_index
                device_rate = int(info.get("defaultSampleRate", config.SAMPLE_RATE))
                print(f"  Device '{info['name']}' found.")
            else:
                print(f"  Device {args.device_index} has no input channels. Falling back to auto-detect.")
                args.device_index = None # Fallback
        except Exception as e:
            print(f"  Device {args.device_index} not found or invalid: {e}. Falling back to auto-detect.")
            args.device_index = None # Fallback
        finally:
            pa.terminate()

    if args.device_index is None:
        print("Finding suitable audio device automatically...")
        device_info = find_suitable_device(config.SAMPLE_RATE, verbose=True)
    else:
        # If specified device was valid, use its info
        device_info = (device_index, device_rate)


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
            'processing_times': []
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
                stats['total_detections'] += 1
                segment_duration = len(segment) / config.SAMPLE_RATE

                print(f"\n[Detection #{stats['total_detections']}]")
                print(f"  Speech duration: {segment_duration:.2f}s")

                # Process with all methods
                start_time = time.time()
                raw_results = matcher.recognize(segment, mode='all') # Get all individual results
                proc_time = (time.time() - start_time) * 1000
                stats['processing_times'].append(proc_time)
                
                # Compute ensemble decision manually
                best_command = 'NONE'
                best_confidence = 0.0
                best_method = None
                
                for method, res in raw_results['all_results'].items():
                    cmd = res['command']
                    dist = res['distance']
                    threshold = matcher.matchers[method].threshold # Get matcher to access its threshold
                    
                    if cmd != 'NONE':
                        conf = 1 - min(dist / threshold, 1)
                        if conf > best_confidence:
                            best_confidence = conf
                            best_command = cmd
                            best_method = method

                # Show results from all methods
                for method, res in raw_results['all_results'].items():
                    cmd = res['command']
                    dist = res['distance']
                    threshold = matcher.matchers[method].threshold
                    
                    status = f"✓ MATCH (conf={(1-dist/threshold)*100:.0f}%)" if cmd != 'NONE' else "✗ NO MATCH"
                    print(f"  {method:12s}: {cmd:8s} (dist={dist:6.2f}, th={threshold:5.1f}) {status}")

                # Show Ensemble Decision
                print(f"  {'>> DECISION':12s}: {best_command:8s} (conf={best_confidence*100:.0f}%, by {best_method})")
                
                if best_command != 'NONE':
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

    print("=" * 70)


if __name__ == '__main__':
    # Temp for test_live.py only, remove after this specific fix
    import pyaudio # Added here for the temp check in main
    test_live_recognition()

