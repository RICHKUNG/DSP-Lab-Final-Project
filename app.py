"""
ECG Pulse Runner - 主程式入口
整合 ECG、語音、遊戲模組
"""

import argparse
import signal
import sys
import time

from src.event_bus import EventBus
from src.ecg import ECGManager
from src.audio.controller import VoiceController
from src.game import GameServer


def main():
    """主程式"""
    parser = argparse.ArgumentParser(
        description='ECG Pulse Runner - 心電圖跑酷遊戲',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例：
  python app.py                    # 啟動完整系統
  python app.py --no-ecg           # 不使用 ECG (測試模式)
  python app.py --no-voice         # 不使用語音 (測試模式)
  python app.py --ecg-port COM3    # 指定 ECG Port
  python app.py --voice-method mfcc_dtw  # 指定語音辨識方法
  python app.py --web-port 8080    # 指定網頁埠號
        """
    )

    parser.add_argument('--ecg-port', type=str, default=None,
                        help='ECG Serial Port (預設: 自動偵測)')
    parser.add_argument('--no-ecg', action='store_true',
                        help='停用 ECG 模組')
    parser.add_argument('--no-voice', action='store_true',
                        help='停用語音模組')
    parser.add_argument('--voice-method', type=str,
                        default=config.DEFAULT_VOICE_METHOD,
                        choices=['mfcc_dtw', 'ensemble', 'adaptive_ensemble'],
                        help=f'語音辨識方法 (預設: {config.DEFAULT_VOICE_METHOD})')
    parser.add_argument('--web-port', type=int, default=5000,
                        help='網頁伺服器埠號 (預設: 5000)')

    args = parser.parse_args()

    # Banner
    print("=" * 60)
    print("  ECG Pulse Runner - 心電圖跑酷遊戲")
    print("  整合語音辨識 + ECG 訊號 + 網頁遊戲")
    print("=" * 60)
    print()

    # 初始化 EventBus
    event_bus = EventBus()
    event_bus.start()
    print("[Main] EventBus started")

    # 模組實例
    ecg_manager = None
    voice_controller = None
    game_server = None

    try:
        # 啟動 ECG 模組
        if not args.no_ecg:
            print(f"\n[Main] Initializing ECG module (port={args.ecg_port or 'auto'})")
            ecg_manager = ECGManager(port=args.ecg_port, event_bus=event_bus)
            try:
                ecg_manager.start()
                print("[Main] ✓ ECG module started")
            except Exception as e:
                print(f"[Main] ✗ ECG module failed: {e}")
                print("[Main]   Continuing without ECG...")
                ecg_manager = None
        else:
            print("\n[Main] ECG module disabled (--no-ecg)")

        # 啟動語音模組
        if not args.no_voice:
            print(f"\n[Main] Initializing Voice module (method={args.voice_method})")
            voice_controller = VoiceController(
                event_bus=event_bus,
                method=args.voice_method
            )
            try:
                voice_controller.start()
                print("[Main] ✓ Voice module started")
            except Exception as e:
                print(f"[Main] ✗ Voice module failed: {e}")
                print("[Main]   Continuing without Voice...")
                voice_controller = None
        else:
            print("\n[Main] Voice module disabled (--no-voice)")

        # 啟動遊戲伺服器
        print(f"\n[Main] Starting Game Server on port {args.web_port}")
        game_server = GameServer(event_bus=event_bus, port=args.web_port)

        # 處理 Ctrl+C
        def signal_handler(sig, frame):
            print("\n\n[Main] Shutting down...")
            event_bus.stop()
            if ecg_manager:
                ecg_manager.stop()
            if voice_controller:
                voice_controller.stop()
            print("[Main] Goodbye!")
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)

        # 啟動伺服器（阻塞）
        print("\n" + "=" * 60)
        print("  System Ready!")
        print(f"  Open browser: http://localhost:{args.web_port}")
        print("  Press Ctrl+C to exit")
        print("=" * 60 + "\n")

        game_server.start()

    except KeyboardInterrupt:
        print("\n[Main] Interrupted")
    except Exception as e:
        print(f"\n[Main] Fatal error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 清理
        event_bus.stop()
        if ecg_manager:
            ecg_manager.stop()
        if voice_controller:
            voice_controller.stop()
        print("\n[Main] Shutdown complete")


if __name__ == '__main__':
    main()
