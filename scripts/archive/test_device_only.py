"""Simple test to verify audio device detection works."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.audio_io import AudioStream, find_suitable_device
from src import config

def test_device():
    """Test audio device selection."""
    print("=" * 70)
    print("Audio Device Test")
    print("=" * 70)

    print(f"\nSearching for device that supports {config.SAMPLE_RATE} Hz...")
    device_info = find_suitable_device(config.SAMPLE_RATE, verbose=True)

    if device_info is None:
        print("[ERROR] No suitable device found!")
        return False

    device_index, device_rate = device_info
    print(f"[OK] Found suitable device: {device_index}")
    if device_rate != config.SAMPLE_RATE:
        print(f"Device native rate: {device_rate} Hz (resampling to {config.SAMPLE_RATE} Hz)")

    print("\nTrying to start audio stream...")
    audio_stream = AudioStream(
        device_index=device_index,
        input_rate=device_rate,
        target_rate=config.SAMPLE_RATE,
    )

    try:
        audio_stream.start()
        print("[OK] Audio stream started successfully!")

        # Test reading a few chunks
        print("\nReading audio chunks...")
        for i in range(5):
            chunk = audio_stream.get_chunk(timeout=0.5)
            print(f"  Chunk {i+1}: {len(chunk)} samples")

        print("\n[SUCCESS] Audio stream is working!")
        return True

    except Exception as e:
        print(f"[ERROR] Failed to start stream: {e}")
        return False

    finally:
        audio_stream.stop()
        print("\nAudio stream stopped.")

if __name__ == '__main__':
    success = test_device()
    sys.exit(0 if success else 1)
