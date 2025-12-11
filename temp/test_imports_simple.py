"""
Simple import test without Unicode characters
"""

import sys
from pathlib import Path

# Add src path
sys.path.insert(0, str(Path(__file__).parent.parent))

print("=" * 60)
print("Module Import Test")
print("=" * 60)

# Test EventBus
print("\n[1/5] Testing EventBus...")
try:
    from src.event_bus import EventBus, EventType, Event
    print("  [OK] EventBus import successful")

    # Quick functionality test
    bus = EventBus()
    received = []
    bus.subscribe(EventType.VOICE_COMMAND, lambda e: received.append(e))
    bus.start()
    bus.publish(Event(EventType.VOICE_COMMAND, {'test': True}))
    import time
    time.sleep(0.1)
    assert len(received) == 1
    bus.stop()
    EventBus.reset_instance()
    print("  [OK] EventBus functionality working")
except Exception as e:
    print(f"  [ERROR] EventBus error: {e}")

# Test Audio module
print("\n[2/5] Testing Audio module...")
try:
    from src.audio import estimate_snr, load_templates_from_dir
    from src.audio.controller import VoiceController
    print("  [OK] Audio module import successful")
except Exception as e:
    print(f"  [ERROR] Audio module error: {e}")

# Test ECG module
print("\n[3/5] Testing ECG module...")
try:
    from src.ecg import ECGManager
    print("  [OK] ECG module import successful")
except Exception as e:
    print(f"  [ERROR] ECG module error: {e}")

# Test Game module
print("\n[4/5] Testing Game module...")
try:
    from src.game import GameServer
    print("  [OK] Game module import successful")
except Exception as e:
    print(f"  [ERROR] Game module error: {e}")

# Test Flask packages
print("\n[5/5] Testing Flask packages...")
try:
    import flask
    import flask_socketio
    import serial
    print(f"  [OK] Flask {flask.__version__}")
    print(f"  [OK] Flask-SocketIO {flask_socketio.__version__}")
    print(f"  [OK] PySerial installed")
except Exception as e:
    print(f"  [ERROR] Package error: {e}")

print("\n" + "=" * 60)
print("All import tests completed!")
print("=" * 60)
