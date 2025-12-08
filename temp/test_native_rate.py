"""Test audio with native sample rate."""

import pyaudio

def test_native_rates():
    """Test common sample rates."""
    pa = pyaudio.PyAudio()

    # Get default input device
    try:
        default_info = pa.get_default_input_device_info()
        device_id = default_info['index']
        print(f"Default input device: {device_id}")
        print(f"Name: {default_info['name']}")
        print(f"Default sample rate: {default_info['defaultSampleRate']}")

        # Test common sample rates
        test_rates = [16000, 22050, 44100, 48000]

        for rate in test_rates:
            print(f"\nTesting {rate} Hz...")
            try:
                stream = pa.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=rate,
                    input=True,
                    input_device_index=device_id,
                    frames_per_buffer=512
                )
                stream.close()
                print(f"  [OK] {rate} Hz works!")
            except Exception as e:
                print(f"  [FAIL] {rate} Hz: {e}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        pa.terminate()

if __name__ == '__main__':
    test_native_rates()
