"""
Import-only test - verify all modules can be imported
"""

import sys
from pathlib import Path

# Add src path
sys.path.insert(0, str(Path(__file__).parent.parent))

print("="  * 60)
print("Module Import Test (Import Only)")
print("=" * 60)

# Test EventBus
print("\n[1/5] Testing EventBus...")
try:
    from src.event_bus import EventBus, EventType, Event
    print("  [OK] EventBus")
except Exception as e:
    print(f"  [ERROR] {e}")

# Test Audio module
print("\n[2/5] Testing Audio module...")
try:
    from src.audio import estimate_snr, load_templates_from_dir
    from src.audio.controller import VoiceController
    from src.audio.io import AudioStream
    from src.audio.vad import VAD
    from src.audio.features import extract_mfcc
    from src.audio.recognizers import MultiMethodMatcher
    print("  [OK] Audio module")
except Exception as e:
    print(f"  [ERROR] {e}")

# Test ECG module
print("\n[3/5] Testing ECG module...")
try:
    from src.ecg import ECGManager
    print("  [OK] ECG module")
except Exception as e:
    print(f"  [ERROR] {e}")

# Test Game module
print("\n[4/5] Testing Game module...")
try:
    from src.game import GameServer
    print("  [OK] Game module")
except Exception as e:
    print(f"  [ERROR] {e}")

# Test Flask packages
print("\n[5/5] Testing packages...")
try:
    import flask
    import flask_socketio
    import serial
    import numpy
    import scipy
    import librosa
    import sounddevice
    print(f"  [OK] Flask {flask.__version__}")
    print(f"  [OK] Flask-SocketIO {flask_socketio.__version__}")
    print(f"  [OK] All required packages installed")
except Exception as e:
    print(f"  [ERROR] {e}")

print("\n" + "=" * 60)
print("Import test completed!")
print("=" * 60)
