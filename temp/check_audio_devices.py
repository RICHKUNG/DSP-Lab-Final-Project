"""Check available audio devices and test them."""

import pyaudio
import sys

def list_audio_devices():
    """List all available audio devices."""
    pa = pyaudio.PyAudio()

    print("=" * 70)
    print("Available Audio Devices")
    print("=" * 70)

    num_devices = pa.get_device_count()
    print(f"Total devices found: {num_devices}\n")

    input_devices = []

    for i in range(num_devices):
        try:
            info = pa.get_device_info_by_index(i)

            # Check if device supports input
            max_input_channels = info.get('maxInputChannels', 0)
            max_output_channels = info.get('maxOutputChannels', 0)

            device_type = []
            if max_input_channels > 0:
                device_type.append("INPUT")
                input_devices.append(i)
            if max_output_channels > 0:
                device_type.append("OUTPUT")

            type_str = "/".join(device_type) if device_type else "UNKNOWN"

            print(f"Device {i}: {info['name']}")
            print(f"  Type: {type_str}")
            print(f"  Input channels: {max_input_channels}")
            print(f"  Output channels: {max_output_channels}")
            print(f"  Default sample rate: {info['defaultSampleRate']}")

            if i == pa.get_default_input_device_info()['index']:
                print(f"  *** DEFAULT INPUT DEVICE ***")
            if i == pa.get_default_output_device_info()['index']:
                print(f"  *** DEFAULT OUTPUT DEVICE ***")

            print()
        except Exception as e:
            print(f"Device {i}: Error reading info - {e}\n")

    pa.terminate()

    print("=" * 70)
    print(f"Input devices: {input_devices}")
    print("=" * 70)

    return input_devices


def test_device(device_index, sample_rate=16000):
    """Test if a device can be opened with given parameters."""
    pa = pyaudio.PyAudio()

    print(f"\nTesting device {device_index} at {sample_rate} Hz...")

    try:
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=sample_rate,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=512
        )
        stream.close()
        print(f"[OK] Device {device_index} works at {sample_rate} Hz!")
        return True
    except Exception as e:
        print(f"[FAIL] Device {device_index} failed: {e}")
        return False
    finally:
        pa.terminate()


if __name__ == '__main__':
    input_devices = list_audio_devices()

    if not input_devices:
        print("\n[ERROR] No input devices found!")
        print("Please check your microphone connection.")
        sys.exit(1)

    print("\nTesting input devices at 16000 Hz...")
    print("=" * 70)

    working_devices = []
    for device_id in input_devices:
        if test_device(device_id, 16000):
            working_devices.append(device_id)

    print("\n" + "=" * 70)
    if working_devices:
        print(f"Working devices at 16kHz: {working_devices}")
        print(f"\nRecommendation: Use device {working_devices[0]}")
    else:
        print("No working devices found at 16kHz!")
        print("Try testing with different sample rates (e.g., 44100, 48000)")
    print("=" * 70)
