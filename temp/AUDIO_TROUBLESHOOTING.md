# Audio Troubleshooting Guide

## Problem
PyAudio is unable to access any microphone devices, failing with error `-9999: Unanticipated host error`.

## Root Cause
This is a **Windows system configuration issue**, not a code problem. The error occurs when:
- Windows microphone permissions are disabled
- Audio device is in exclusive mode
- Another application is using the microphone
- Audio drivers need updating

## Solutions (Try in order)

### 1. Fix Windows Microphone Permissions ⭐ **MOST COMMON**

1. Open Windows Settings
2. Go to **Privacy & Security** > **Microphone**
3. Enable these options:
   - ✅ **Microphone access**: ON
   - ✅ **Let apps access your microphone**: ON
   - ✅ **Let desktop apps access your microphone**: ON

4. Restart your Python script

### 2. Disable Exclusive Mode

1. Right-click the **speaker icon** in the taskbar
2. Select **Sounds**
3. Go to the **Recording** tab
4. Select your microphone (e.g., "麥克風 (Galaxy Buds3)")
5. Click **Properties**
6. Go to the **Advanced** tab
7. **Uncheck**: "Allow applications to take exclusive control of this device"
8. Click **Apply** and **OK**

### 3. Close Applications Using Microphone

Check if these apps are running and close them:
- Discord
- Zoom / Teams / Skype
- OBS Studio
- Any voice recording software
- Browser tabs with microphone access

**To check**: Open Task Manager and look for apps accessing audio devices.

### 4. Try Different Audio Device

Your system shows multiple input devices:
- **Device 1**: 麥克風 (Galaxy Buds3) - Bluetooth, 44100 Hz
- **Device 17**: 麥克風 (Galaxy Buds3) - Bluetooth, **16000 Hz** ← Best for this app
- **Device 34**: Realtek HD Audio - Built-in mic, **16000 Hz**

**Recommendation**: Try using the built-in laptop microphone instead of Bluetooth:
- Disconnect Galaxy Buds3
- Use the laptop's built-in microphone
- Bluetooth audio can have compatibility issues with PyAudio

### 5. Update Audio Drivers

1. Open **Device Manager**
2. Expand **Audio inputs and outputs**
3. Right-click your microphone
4. Select **Update driver**
5. Choose **Search automatically for drivers**

### 6. Reinstall PyAudio (Advanced)

If nothing else works:

```bash
pip uninstall pyaudio
pip install pyaudio
```

Or try PyAudio with better Windows support:
```bash
pip install pipwin
pipwin install pyaudio
```

## Testing

After trying each solution, test with:

```bash
python temp/audio_diagnostic.py
```

Look for `[OK]` messages instead of `[FAIL]`.

## Code Updates Made

The code has been updated to:
1. ✅ Auto-detect audio devices that support 16kHz
2. ✅ Show helpful error messages when no device is found
3. ✅ Allow manual device selection via `device_index` parameter

## Quick Test Commands

```bash
# Run diagnostic
python temp/audio_diagnostic.py

# Test device selection only
python temp/test_device_only.py

# Run full live test (after fixing permissions)
python test_live.py
```

## Still Not Working?

If you still get error -9999 after trying all solutions:
1. Restart your computer
2. Check Windows Update for system updates
3. Consider using a USB microphone instead of Bluetooth
4. Try running Python as Administrator (not recommended for security)
