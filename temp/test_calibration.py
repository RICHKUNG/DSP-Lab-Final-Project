"""測試語音校正功能"""

import sys
import os
import time

# Add project root to path
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_current_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.audio.controller import VoiceController
from src.event_bus import EventBus
from src import config

def test_calibration():
    """測試校正功能"""
    print("=" * 60)
    print("Voice Calibration Test")
    print("=" * 60)

    # 初始化
    event_bus = EventBus()
    event_bus.start()

    print("\n初始化語音控制器...")
    controller = VoiceController(
        event_bus=event_bus,
        method='mfcc_dtw'
    )

    try:
        controller.start()
        print("語音控制器啟動成功\n")

        # 測試每個指令的校正
        commands = ['START', 'JUMP', 'FLIP', 'PAUSE']
        command_names = {
            'START': '開始',
            'JUMP': '跳',
            'FLIP': '翻',
            'PAUSE': '暫停'
        }

        for cmd in commands:
            print(f"\n{'='*60}")
            print(f"請說出指令：{command_names[cmd]} ({cmd})")
            print(f"等待錄音... (5秒超時)")
            print("="*60)

            result = controller.calibrate_command(cmd, timeout=5.0)

            if result['success']:
                print(f"✓ {cmd} 校正成功!")
                print(f"  能量: {result['energy']:.2f}")
            else:
                print(f"✗ {cmd} 校正失敗")
                print(f"  原因: {result['message']}")
                print("  請重試...")
                time.sleep(1)

        print("\n" + "="*60)
        print("校正完成！")
        print("="*60)

        # 測試辨識
        print("\n現在測試辨識...")
        print("請隨意說出指令...")
        print("按 Ctrl+C 停止")

        try:
            while True:
                cmd = controller.listen_and_analyze(timeout=0.1)
                if cmd:
                    print(f"辨識到指令: {cmd}")
        except KeyboardInterrupt:
            print("\n停止測試")

    except Exception as e:
        print(f"\n錯誤: {e}")
        import traceback
        traceback.print_exc()
    finally:
        controller.stop()
        event_bus.stop()
        print("\n清理完成")


if __name__ == '__main__':
    test_calibration()
