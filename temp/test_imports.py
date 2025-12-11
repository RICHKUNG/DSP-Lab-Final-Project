"""
快速導入測試 - 驗證所有模組可以正確導入
"""

import sys
from pathlib import Path

# 加入 src 路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

print("=" * 60)
print("模組導入測試")
print("=" * 60)

# 測試 EventBus
print("\n[1/5] 測試 EventBus...")
try:
    from src.event_bus import EventBus, EventType, Event
    print("  ✓ EventBus 導入成功")

    # 快速功能測試
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
    print("  ✓ EventBus 功能正常")
except Exception as e:
    print(f"  ✗ EventBus 錯誤: {e}")

# 測試 Audio 模組
print("\n[2/5] 測試 Audio 模組...")
try:
    from src.audio import estimate_snr, load_templates_from_dir
    from src.audio.controller import VoiceController
    print("  ✓ Audio 模組導入成功")
except Exception as e:
    print(f"  ✗ Audio 模組錯誤: {e}")

# 測試 ECG 模組
print("\n[3/5] 測試 ECG 模組...")
try:
    from src.ecg import ECGManager
    print("  ✓ ECG 模組導入成功")
except Exception as e:
    print(f"  ✗ ECG 模組錯誤: {e}")

# 測試 Game 模組
print("\n[4/5] 測試 Game 模組...")
try:
    from src.game import GameServer
    print("  ✓ Game 模組導入成功")
except Exception as e:
    print(f"  ✗ Game 模組錯誤: {e}")

# 測試 Flask 套件
print("\n[5/5] 測試 Flask 相關套件...")
try:
    import flask
    import flask_socketio
    import serial
    print(f"  ✓ Flask {flask.__version__}")
    print(f"  ✓ Flask-SocketIO {flask_socketio.__version__}")
    print(f"  ✓ PySerial 已安裝")
except Exception as e:
    print(f"  ✗ 套件錯誤: {e}")

print("\n" + "=" * 60)
print("所有導入測試完成！")
print("=" * 60)
