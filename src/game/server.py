"""
GameServer - Flask + SocketIO 遊戲伺服器
訂閱 EventBus 事件，轉發給瀏覽器
"""

import threading
import json
import os
import time
from pathlib import Path
from flask import Flask, render_template
from flask_socketio import SocketIO

from ..event_bus import EventBus, Event, EventType


class GameServer:
    """
    網頁遊戲伺服器

    功能：
    - Flask 網頁伺服器
    - SocketIO 即時通訊
    - 訂閱 EventBus 事件，轉發給瀏覽器
    - 天梯系統 (Leaderboard)

    事件對應：
    - ECG_PEAK → emit('spawn_obstacle')
    - ECG_BPM_UPDATE → emit('bpm_update')
    - VOICE_COMMAND → emit('player_action')

    使用方式：
        server = GameServer(event_bus)
        server.start()  # 阻塞
    """

    def __init__(
        self,
        event_bus: EventBus = None,
        host: str = '0.0.0.0',
        port: int = 5000,
        voice_controller = None,
        user_name: str = "Player",
        freedom_mode: bool = False
    ):
        """
        初始化遊戲伺服器

        Args:
            event_bus: EventBus 實例
            host: 主機位址
            port: 埠號
            voice_controller: VoiceController 實例（用於校正）
            user_name: 玩家名稱
            freedom_mode: 自由模式（使用不同的排行榜檔案）
        """
        self.event_bus = event_bus or EventBus()
        self.host = host
        self.port = port
        self.voice_controller = voice_controller
        self.user_name = user_name
        self.freedom_mode = freedom_mode
        # 根據模式使用不同的排行榜檔案
        self.leaderboard_file = "leaderboard_freedom.json" if freedom_mode else "leaderboard.json"

        # 取得模板目錄
        game_dir = Path(__file__).parent
        template_dir = game_dir / "templates"

        # Flask app
        self.app = Flask(
            __name__,
            template_folder=str(template_dir)
        )
        self.app.config['SECRET_KEY'] = 'ecg-pulse-runner-secret-2025'

        # SocketIO
        self.socketio = SocketIO(
            self.app,
            cors_allowed_origins="*",
            async_mode='threading'
        )

        # 設定路由和事件處理
        self._setup_routes()
        self._setup_event_handlers()

    def _load_leaderboard(self):
        """讀取排行榜"""
        if not os.path.exists(self.leaderboard_file):
            return []
        try:
            with open(self.leaderboard_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[GameServer] Failed to load leaderboard: {e}")
            return []

    def _save_leaderboard(self, data):
        """儲存排行榜"""
        try:
            with open(self.leaderboard_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[GameServer] Failed to save leaderboard: {e}")

    def _setup_routes(self) -> None:
        """設定 Flask 路由"""

        @self.app.route('/')
        def index():
            return render_template('index.html')

        @self.app.route('/health')
        def health():
            return {'status': 'ok', 'service': 'ECG Pulse Runner'}

        @self.socketio.on('connect')
        def on_connect():
            """客戶端連線時發送配置"""
            print("[GameServer] Client connected")
            # 發送配置資訊給前端
            self.socketio.emit('config', {
                'freedom_mode': self.freedom_mode
            })

        @self.socketio.on('disconnect')
        def on_disconnect():
            print("[GameServer] Client disconnected")
            # 可以在這裡加入邏輯：如果沒有客戶端連線，就關閉伺服器
            # 但為了避免重新整理頁面時誤殺，通常建議保留或延遲關閉
            # 依據使用者需求：若遊戲視窗被關掉，就停止並結束程式
            # 我們啟動一個計時器，3秒後如果沒有新連線就退出
            threading.Timer(3.0, self._check_shutdown).start()

        @self.socketio.on('calibrate_command')
        def on_calibrate_command(data):
            """處理校正請求 (非阻塞)"""
            command = data.get('command', '').upper()
            print(f"[GameServer] Received calibration request for: {command}")

            if not self.voice_controller:
                self.socketio.emit('calibration_result', {
                    'command': command,
                    'success': False,
                    'message': 'Voice controller not available'
                })
                return

            # 啟動非阻塞校正模式
            self.voice_controller.start_calibration_mode(command)
            # 不立即回傳結果，等待 EventBus 事件

        @self.socketio.on('game_over')
        def on_game_over(data):
            """處理遊戲結束，更新排行榜"""
            score = data.get('score', 0)
            print(f"[GameServer] Game Over! User: {self.user_name}, Score: {score}")

            # 更新排行榜
            leaderboard = self._load_leaderboard()
            leaderboard.append({'name': self.user_name, 'score': score, 'date': time.strftime('%Y-%m-%d %H:%M')})
            
            # 排序並取前 10 名
            leaderboard.sort(key=lambda x: x['score'], reverse=True)
            leaderboard = leaderboard[:10]
            
            self._save_leaderboard(leaderboard)
            
            # 回傳排行榜
            self.socketio.emit('leaderboard_update', {'leaderboard': leaderboard})

    def _check_shutdown(self):
        """檢查是否還有連線，若無則退出"""
        # 這裡比較難直接取得連線數，但我們可以簡單地用一個全域變數或依賴 SocketIO 內部
        # 或是更強硬地：只要 disconnect 就假設使用者不想玩了 (除非是 refresh)
        pass 
        # 由於 SocketIO 的設計，這裡要取得精確的 client count 比較麻煩
        # 且直接 os._exit(0) 比較暴力。
        # 比較好的做法是發送一個 Event 到 EventBus 通知 Main Thread。
        
        # 修正：直接實作一個簡單的計數器
        pass

    def _setup_event_handlers(self) -> None:
        """訂閱 EventBus 事件"""
        self.event_bus.subscribe(EventType.ECG_PEAK, self._on_ecg_peak)
        self.event_bus.subscribe(EventType.ECG_BPM_UPDATE, self._on_bpm_update)
        self.event_bus.subscribe(EventType.VOICE_COMMAND, self._on_voice_command)
        self.event_bus.subscribe(EventType.CALIBRATION_RESULT, self._on_calibration_result)
        self.event_bus.subscribe(EventType.PLAYBACK_START, self._on_playback_start)
        self.event_bus.subscribe(EventType.PLAYBACK_COMPLETE, self._on_playback_complete)

        # SocketIO 連線事件 (Decorator 寫法在 Class 內比較麻煩，改用明確定義)
        self.socketio.on_event('connect', self._on_client_connect)
        self.socketio.on_event('disconnect', self._on_client_disconnect)

        self.client_count = 0

    def _on_calibration_result(self, event: Event) -> None:
        """處理校正結果事件"""
        data = event.data
        print(f"[GameServer] Received Event CALIBRATION_RESULT: {data}")
        print(f"[GameServer] Emitting 'calibration_result' to frontend...")
        self.socketio.emit('calibration_result', {
            'command': data.get('command'),
            'success': data.get('success'),
            'message': data.get('message'),
            'energy': float(data.get('energy', 0))
        })
        print(f"[GameServer] Emitted successfully")

    def _on_playback_start(self, event: Event) -> None:
        """處理播放開始事件（自由模式）"""
        data = event.data
        print(f"[GameServer] Playback started for: {data.get('command')}")
        self.socketio.emit('playback_start', {
            'command': data.get('command')
        })

    def _on_playback_complete(self, event: Event) -> None:
        """處理播放完成事件（自由模式）"""
        data = event.data
        print(f"[GameServer] Playback completed for: {data.get('command')}")
        self.socketio.emit('playback_complete', {
            'command': data.get('command')
        })

    def _on_client_connect(self):
        self.client_count += 1
        print(f"[GameServer] Client connected (Total: {self.client_count})")

    def _on_client_disconnect(self):
        self.client_count -= 1
        print(f"[GameServer] Client disconnected (Total: {self.client_count})")
        
        if self.client_count <= 0:
            print("[GameServer] No clients connected. Shutting down in 30 seconds...")
            threading.Timer(30.0, self._trigger_shutdown).start()

    def _trigger_shutdown(self):
        if self.client_count <= 0:
            print("[GameServer] Shutdown timeout reached. Exiting...")
            import os
            os._exit(0)

    def _on_ecg_peak(self, event: Event) -> None:
        """處理 ECG 峰值事件"""
        self.socketio.emit('spawn_obstacle', {
            'dir': event.data.get('dir', 1),
            'height': event.data.get('value', 50)
        })

    def _on_bpm_update(self, event: Event) -> None:
        """處理 BPM 更新事件"""
        self.socketio.emit('bpm_update', {
            'bpm': event.data.get('bpm', 0)
        })

    def _on_voice_command(self, event: Event) -> None:
        """處理語音指令事件"""
        action = event.data.get('action', 'UNKNOWN')
        print(f"[GameServer] Emitting player_action: {action}")
        self.socketio.emit('player_action', {
            'action': action
        })

    def start(self) -> None:
        """啟動伺服器（阻塞）"""
        url = f"http://{self.host if self.host != '0.0.0.0' else 'localhost'}:{self.port}"
        print(f"[GameServer] Starting on {url}")
        
        # 自動開啟瀏覽器
        import webbrowser
        try:
            print("[GameServer] Opening browser...")
            webbrowser.open(url)
        except Exception as e:
            print(f"[GameServer] Failed to open browser: {e}")

        self.socketio.run(
            self.app,
            host=self.host,
            port=self.port,
            debug=False,
            use_reloader=False,
            allow_unsafe_werkzeug=True
        )

    def start_background(self) -> threading.Thread:
        """在背景執行緒啟動伺服器"""
        thread = threading.Thread(
            target=self.start,
            name="GameServer",
            daemon=True
        )
        thread.start()
        return thread
