import sounddevice as sd

print(f"SoundDevice Version: {sd.__version__}")
print(f"PortAudio Version: {sd.get_portaudio_version()}")

print("\nHost APIs:")
for i, api in enumerate(sd.query_hostapis()):
    print(f"  {i}: {api['name']}")

print("\nInput Devices:")
devices = sd.query_devices()
for i, d in enumerate(devices):
    if d['max_input_channels'] > 0:
        print(f"  {i}: {d['name']}")
        print(f"     API: {d['hostapi']} ({sd.query_hostapis()[d['hostapi']]['name']})")
        print(f"     Channels: {d['max_input_channels']}")
        print(f"     Default Rate: {d['default_samplerate']}")
