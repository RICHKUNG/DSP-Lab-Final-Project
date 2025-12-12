"""
ECG Pulse Runner - Main Entry Point
Integrates ECG, Voice, and Game modules
"""

import argparse
import signal
import sys
import time

from src.event_bus import EventBus
from src.ecg import ECGAdapter
from src.audio.controller import VoiceController
from src.game import GameServer
from src import config


def main():
    """Main Program"""
    parser = argparse.ArgumentParser(
        description='ECG Pulse Runner - ECG Parkour Game',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python app.py                    # Start full system
  python app.py --no-ecg           # No ECG (Test mode)
  python app.py --no-voice         # No Voice (Test mode)
  python app.py --ecg-port COM3    # Specify ECG Port
  python app.py --voice-method mfcc_dtw  # Specify voice recognition method
  python app.py --web-port 8080    # Specify web port
  python app.py --freedom          # Freedom mode - use custom voice commands
        """
    )

    parser.add_argument('--ecg-port', type=str, default=None,
                        help='ECG Serial Port (Default: Auto-detect)')
    parser.add_argument('--no-ecg', action='store_true',
                        help='Disable ECG module')
    parser.add_argument('--bpm-threshold', type=float, default=-10.0,
                        help='Switch to fake signal if BPM below this (Default: -10, rarely triggers)')
    parser.add_argument('--bpm-recovery', type=float, default=50.0,
                        help='Resume real signal if BPM above this (Default: 50)')
    parser.add_argument('--fallback-bpm', type=float, default=75.0,
                        help='Fake signal BPM (Default: 75)')
    parser.add_argument('--retry-interval', type=float, default=10.0,
                        help='Retry interval for real ECG in fallback mode (Default: 10)')
    parser.add_argument('--no-voice', action='store_true',
                        help='Disable Voice module')
    parser.add_argument('--voice-method', type=str,
                        default=config.DEFAULT_VOICE_METHOD,
                        choices=['mfcc_dtw', 'ensemble', 'adaptive_ensemble'],
                        help=f'Voice recognition method (Default: {config.DEFAULT_VOICE_METHOD})')
    parser.add_argument('--web-port', type=int, default=5000,
                        help='Web server port (Default: 5000)')
    parser.add_argument('--user', type=str, default='Player',
                        help='Player name (Default: Player)')
    parser.add_argument('--freedom', action='store_true',
                        help='Freedom Mode: Use custom commands during calibration')

    args = parser.parse_args()

    # Banner
    print("=" * 60)
    print("  ECG Pulse Runner - ECG Parkour Game")
    print(f"  Player: {args.user}")
    print("  Integrated Voice + ECG + Web Game")
    print("=" * 60)
    print()

    # Initialize EventBus
    event_bus = EventBus()
    event_bus.start()
    print("[Main] EventBus started")

    # Module Instances
    ecg_manager = None
    voice_controller = None
    game_server = None

    try:
        # Start ECG Module
        if not args.no_ecg:
            print(f"\n[Main] Initializing ECG module (port={args.ecg_port or 'auto'})")
            print(f"[Main]   BPM threshold: {args.bpm_threshold} (switch to fallback)")
            print(f"[Main]   BPM recovery: {args.bpm_recovery} (switch back to real)")
            print(f"[Main]   Fallback BPM: {args.fallback_bpm}")
            print(f"[Main]   Retry interval: {args.retry_interval}s")
            ecg_manager = ECGAdapter(
                port=args.ecg_port,
                event_bus=event_bus,
                bpm_threshold=args.bpm_threshold,
                bpm_recovery=args.bpm_recovery,
                fallback_bpm=args.fallback_bpm,
                retry_interval=args.retry_interval
            )
            try:
                ecg_manager.start()
                print("[Main] ✓ ECG module started")
            except Exception as e:
                print(f"[Main] ✗ ECG module failed: {e}")
                print("[Main]   Continuing without ECG...")
                ecg_manager = None
        else:
            print("\n[Main] ECG module disabled (--no-ecg)")

        # Start Voice Module
        if not args.no_voice:
            print(f"\n[Main] Initializing Voice module (method={args.voice_method})")
            if args.freedom:
                print(f"[Main]   Freedom Mode ENABLED - custom voice commands")
            voice_controller = VoiceController(
                event_bus=event_bus,
                method=args.voice_method,
                freedom_mode=args.freedom
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

        # Start Game Server
        print(f"\n[Main] Starting Game Server on port {args.web_port}")
        game_server = GameServer(
            event_bus=event_bus,
            port=args.web_port,
            voice_controller=voice_controller,
            user_name=args.user,
            freedom_mode=args.freedom
        )

        # Handle Ctrl+C
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

        # Start Server (Blocking)
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
        # Cleanup
        event_bus.stop()
        if ecg_manager:
            ecg_manager.stop()
        if voice_controller:
            voice_controller.stop()
        print("\n[Main] Shutdown complete")


if __name__ == '__main__':
    main()