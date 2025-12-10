"""Comprehensive audio diagnostic tool."""

import pyaudio
import sys

def check_audio_permissions():
    """Check if we can enumerate devices."""
    print("=" * 70)
    print("PyAudio Audio Diagnostic")
    print("=" * 70)

    pa = pyaudio.PyAudio()

    try:
        # Check version
        print(f"\nPyAudio version: {pyaudio.__version__}")
        try:
            print(f"PortAudio version: {pyaudio.get_portaudio_version()}")
        except:
            pass

        # Get device count
        num_devices = pa.get_device_count()
        print(f"\nTotal audio devices: {num_devices}")

        # Get default devices
        try:
            default_input = pa.get_default_input_device_info()
            print(f"\nDefault INPUT device:")
            print(f"  Index: {default_input['index']}")
            print(f"  Name: {default_input['name']}")
            print(f"  Channels: {default_input['maxInputChannels']}")
            print(f"  Sample Rate: {default_input['defaultSampleRate']}")
        except Exception as e:
            print(f"\n[ERROR] No default input device: {e}")

        # List all input devices
        print("\n" + "=" * 70)
        print("Input Devices:")
        print("=" * 70)

        input_devices = []
        for i in range(num_devices):
            try:
                info = pa.get_device_info_by_index(i)
                if info.get('maxInputChannels', 0) > 0:
                    input_devices.append(i)
                    host_api_info = pa.get_host_api_info_by_index(info['hostApi'])
                    print(f"\nDevice {i}:")
                    print(f"  Name: {info['name'][:60]}")
                    print(f"  Host API: {host_api_info['name']} (Index: {info['hostApi']})")
                    print(f"  Channels: {info['maxInputChannels']}")
                    print(f"  Sample Rate: {info['defaultSampleRate']}")
            except Exception as e:
                print(f"\nDevice {i}: [ERROR] {str(e)[:60]}")

        # Test opening devices without actually starting stream
        print("\n" + "=" * 70)
        print("Testing device access (using default callback)...")
        print("=" * 70)

        for device_id in input_devices[:3]:  # Test first 3 input devices
            print(f"\nTesting device {device_id}...")

            try:
                info = pa.get_device_info_by_index(device_id)
                rate = int(info['defaultSampleRate'])

                # Try to open without callback first
                stream = pa.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=rate,
                    input=True,
                    input_device_index=device_id,
                    frames_per_buffer=1024,
                    start=False  # Don't start yet
                )
                stream.close()
                print(f"  [OK] Device {device_id} opened successfully at {rate} Hz")

            except Exception as e:
                error_msg = str(e)
                print(f"  [FAIL] {error_msg}")

                if "-9999" in error_msg:
                    print("  Possible causes:")
                    print("    - Device in exclusive mode (another app using it)")
                    print("    - Microphone permissions denied")
                    print("    - Driver issue")

    except Exception as e:
        print(f"\n[CRITICAL ERROR] {e}")
        import traceback
        traceback.print_exc()

    finally:
        pa.terminate()

    print("\n" + "=" * 70)
    print("SOLUTIONS:")
    print("=" * 70)
    print("""
1. Check Windows Microphone Permissions:
   - Go to Settings > Privacy & Security > Microphone
   - Enable "Let apps access your microphone"
   - Enable "Let desktop apps access your microphone"

2. Disable Exclusive Mode:
   - Right-click the speaker icon in taskbar
   - Select "Sounds" > "Recording" tab
   - Select your microphone > Properties
   - Go to "Advanced" tab
   - Uncheck "Allow applications to take exclusive control"
   - Click Apply

3. Close other applications using microphone:
   - Close Discord, Zoom, Teams, or other voice apps
   - Check Task Manager for background apps

4. Try different audio device:
   - Use built-in laptop microphone instead of Bluetooth
   - Bluetooth audio sometimes has compatibility issues

5. Reinstall PyAudio with WASAPI support:
   - pip uninstall pyaudio
   - pip install pyaudio
    """)

if __name__ == '__main__':
    check_audio_permissions()
