"""
簡單測試：驗證重構後的模組可以正常 import
"""
import sys
sys.path.insert(0, 'C:/Users/user/Desktop/DSPLab/Final')

print("Testing imports...")

try:
    from src.ecg.adapter import ECGAdapter
    print("✓ ECGAdapter imported successfully")
except Exception as e:
    print(f"✗ Failed to import ECGAdapter: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    from src.ecg.ecg_reader import ECGProcessor
    print("✓ ECGProcessor imported successfully")
except Exception as e:
    print(f"✗ Failed to import ECGProcessor: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    from src.event_bus import EventBus, EventType
    print("✓ EventBus imported successfully")
except Exception as e:
    print(f"✗ Failed to import EventBus: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\nTesting initialization...")

try:
    event_bus = EventBus()
    event_bus.start()
    print("✓ EventBus created and started")
except Exception as e:
    print(f"✗ Failed to create EventBus: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    adapter = ECGAdapter(
        event_bus=event_bus,
        port=None,  # Auto-detect
        bpm_threshold=-10.0,
        fallback_bpm=75.0
    )
    print("✓ ECGAdapter created successfully")
    print(f"  - hardware_available: {adapter.hardware_available}")
    print(f"  - use_fallback: {adapter.use_fallback}")
    print(f"  - consecutive_good_bpm: {adapter.consecutive_good_bpm}")
except Exception as e:
    print(f"✗ Failed to create ECGAdapter: {e}")
    import traceback
    traceback.print_exc()
    event_bus.stop()
    sys.exit(1)

event_bus.stop()
print("\n✓ All tests passed!")
