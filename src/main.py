"""Bio-Voice Commander - Main entry point."""

import sys
import queue
import time
from pathlib import Path

from . import config
from .audio_io import AudioStream, find_suitable_device, load_audio_file
from .vad import VAD, VADState, preprocess_audio
from .recognizers import MultiMethodMatcher


class VoiceCommander:
    """Main voice command recognition system."""

    def __init__(self, template_dir: str = None):
        self.audio_stream = None
        self.vad = None
        self.matcher = MultiMethodMatcher()
        self.command_queue = queue.Queue()
        self._running = False

        if template_dir:
            self.load_templates(template_dir)

    def load_templates(self, template_dir: str):
        """Load templates from directory."""
        print(f"Loading templates from: {template_dir}")
        self.matcher.load_templates_from_dir(template_dir)

        # Print template counts
        for method, m in self.matcher.matchers.items():
            counts = {cmd: len(templates) for cmd, templates in m.templates.items()}
            print(f"  {method}: {counts}")

    def start(self):
        """Start real-time recognition."""
        print("Finding audio device...")
        device_info = find_suitable_device(config.SAMPLE_RATE, verbose=True)
        if device_info is None:
            print("[ERROR] Cannot access any audio input device.")
            print("See temp/AUDIO_TROUBLESHOOTING.md or run: python temp/audio_diagnostic.py")
            return

        device_index, device_rate = device_info
        if device_rate != config.SAMPLE_RATE:
            print(f"Selected device {device_index} at {device_rate} Hz (resampling to {config.SAMPLE_RATE} Hz)")
        else:
            print(f"Selected device {device_index} at {device_rate} Hz")

        print("Starting audio stream...")
        self.audio_stream = AudioStream(
            device_index=device_index,
            input_rate=device_rate,
            target_rate=config.SAMPLE_RATE,
        )
        self.audio_stream.start()

        # Dynamic Noise Calibration
        print("\n" + "="*50)
        print("   ENVIRONMENT CALIBRATION")
        print("   Please stay QUIET for 2 seconds...")
        print("="*50)
        time.sleep(0.5)
        
        # 1. Measure RMS for VAD
        bg_rms = self.audio_stream.measure_background(1000)
        print(f"Background RMS: {bg_rms:.1f}")

        # 2. Collect dynamic noise templates for Recognizer
        noise_samples = self._collect_noise_samples(duration_ms=1500, num_samples=5)
        print(f"Captured {len(noise_samples)} noise profiles from current environment.")
        for ns in noise_samples:
            self.matcher.add_noise_template(ns)

        self.vad = VAD(background_rms=bg_rms)
        self._running = True

        print("\nListening for commands...")
        print("(Say: 開始, 暫停, 跳, 磁鐵, 反轉)")
        print("Press Ctrl+C to stop\n")

        try:
            self._recognition_loop()
        except KeyboardInterrupt:
            print("\nStopping...")
        finally:
            self.stop()

    def _collect_noise_samples(self, duration_ms=1500, num_samples=5):
        """Collect noise samples from live environment."""
        import numpy as np
        
        samples_needed = int(config.SAMPLE_RATE * duration_ms / 1000)
        collected = []
        
        # Drain buffer
        self.audio_stream.get_chunk()

        while len(collected) < samples_needed:
            chunk = self.audio_stream.get_chunk(timeout=0.1)
            if len(chunk) > 0:
                collected.extend(chunk)
            else:
                time.sleep(0.01)

        audio = np.array(collected[:samples_needed], dtype=np.int16)

        # Split into segments
        segment_len = len(audio) // num_samples
        noise_samples = []

        for i in range(num_samples):
            start = i * segment_len
            end = start + segment_len
            segment = audio[start:end]
            # Verify it's not empty
            if len(segment) > 0:
                noise_samples.append(segment)

        return noise_samples

    def _recognition_loop(self):
        """Main recognition loop."""
        while self._running:
            chunk = self.audio_stream.get_chunk(timeout=0.1)
            if len(chunk) == 0:
                continue

            state, segment = self.vad.process_chunk(chunk)

            if state == VADState.PROCESSING and segment is not None:
                # Process speech segment
                start_time = time.time()
                result = self.matcher.recognize(segment)
                proc_time = (time.time() - start_time) * 1000

                cmd = result['command']
                conf = result.get('confidence', 0)
                method = result.get('method', 'N/A')

                if cmd != 'NONE':
                    print(f"[{cmd}] (conf={conf:.2f}, method={method}, time={proc_time:.0f}ms)")
                    self.command_queue.put(cmd)
                else:
                    print(f"[No match] (time={proc_time:.0f}ms)")

                self.vad.reset()

    def stop(self):
        """Stop recognition."""
        self._running = False
        if self.audio_stream:
            self.audio_stream.stop()

    def get_command(self, timeout: float = None) -> str:
        """Get next recognized command."""
        try:
            return self.command_queue.get(timeout=timeout)
        except queue.Empty:
            return None


def test_with_file(audio_path: str, template_dir: str):
    """Test recognition with an audio file."""
    print(f"\nTesting with: {audio_path}")

    # Load templates
    matcher = MultiMethodMatcher()
    matcher.load_templates_from_dir(template_dir)

    # Load test audio
    audio = load_audio_file(audio_path)
    print(f"Audio length: {len(audio) / config.SAMPLE_RATE:.2f}s")

    # Recognize
    start_time = time.time()
    result = matcher.recognize(audio, mode='all')
    proc_time = (time.time() - start_time) * 1000

    print(f"\nResults (processing time: {proc_time:.1f}ms):")
    print("-" * 50)
    for method, res in result['all_results'].items():
        print(f"  {method:12s}: {res['command']:8s} (dist={res['distance']:.2f})")
    print("-" * 50)
    print(f"  Best: {result['command']} (confidence={result['confidence']:.2f})")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Bio-Voice Commander')
    parser.add_argument('--templates', '-t', type=str, default=str(config.TEMPLATE_DIR),
                        help='Template directory')
    parser.add_argument('--test', type=str, default=None,
                        help='Test with audio file')
    parser.add_argument('--live', action='store_true',
                        help='Run live recognition')

    args = parser.parse_args()

    if args.test:
        test_with_file(args.test, args.templates)
    elif args.live:
        commander = VoiceCommander(template_dir=args.templates)
        commander.start()
    else:
        # Default: show help
        parser.print_help()


if __name__ == '__main__':
    main()
