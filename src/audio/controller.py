"""
VoiceController - 語音辨識控制器
整合 EventBus、AudioStream、VAD、MultiMethodMatcher
"""

import threading
import queue
import time
import numpy as np
from typing import Optional
from pathlib import Path

from ..event_bus import EventBus, Event, EventType
from .. import config
from .io import AudioStream, find_suitable_device
from .vad import VAD, VADState
from .recognizers import MultiMethodMatcher


class VoiceController:
    """
    語音命令控制器

    功能：
    - 整合音訊輸入、VAD、辨識器
    - 發布 VOICE_COMMAND 事件
    - 支援輪詢和事件驅動兩種模式
    - 支援動態切換辨識方法

    使用方式：
        controller = VoiceController(method='adaptive_ensemble')
        controller.start()
        # 輪詢模式
        cmd = controller.listen_and_analyze()
        # 或訂閱事件
        event_bus.subscribe(EventType.VOICE_COMMAND, callback)
    """

    # 指令映射
    COMMAND_TO_ACTION = {
        'START': 'START',
        'PAUSE': 'PAUSE',
        'JUMP': 'JUMP',
        'FLIP': 'FLIP',
    }

    def __init__(
        self,
        template_dir: Optional[str] = None,
        event_bus: Optional[EventBus] = None,
        method: str = 'adaptive_ensemble',
        freedom_mode: bool = False
    ):
        """
        初始化語音控制器

        Args:
            template_dir: 模板目錄路徑，預設使用 config.TEMPLATE_DIR
            event_bus: EventBus 實例，預設建立新的
            method: 辨識方法
                - 'mfcc_dtw': 僅 MFCC (最快 ~160ms)
                - 'ensemble': 固定權重 Ensemble
                - 'adaptive_ensemble': SNR 自適應 (預設，最準 97.9%)
            freedom_mode: 自由模式，不載入預設模板，僅使用校正時的自訂口令
        """
        self.event_bus = event_bus or EventBus()
        self.template_dir = template_dir or str(Path(__file__).parent.parent.parent / "cmd_templates")
        self.method = method
        self.freedom_mode = freedom_mode

        # 組件
        self._audio_stream: Optional[AudioStream] = None
        self._vad: Optional[VAD] = None
        self._matcher = MultiMethodMatcher()

        # 狀態
        self._running = False
        self._is_calibrating = False  # 校正狀態旗標
        self._thread: Optional[threading.Thread] = None
        self._command_queue = queue.Queue()
        self._calibration_target: Optional[str] = None # 目前校正目標指令
        self._calibration_start_time: float = 0.0

        # 載入模板（自由模式下跳過）
        if not freedom_mode:
            self._load_templates()
        else:
            print("[VoiceController] Freedom mode - skipping template loading")

    def _load_templates(self) -> None:
        """載入語音模板"""
        print(f"[VoiceController] Loading templates from: {self.template_dir}")
        try:
            self._matcher.load_templates_from_dir(self.template_dir)
        except Exception as e:
            print(f"[VoiceController] Error loading templates: {e}")

    def start(self) -> None:
        """啟動語音辨識（背景執行緒）"""
        if self._running:
            print("[VoiceController] Already running")
            return

        try:
            # 尋找音訊裝置
            device_info = find_suitable_device(config.SAMPLE_RATE, verbose=False)
            if device_info is None:
                raise RuntimeError("No audio input device found")

            device_index, device_rate = device_info
            print(f"[VoiceController] Using device {device_index} @ {device_rate}Hz")

            # 啟動音訊串流
            self._audio_stream = AudioStream(
                device_index=device_index,
                input_rate=device_rate,
                target_rate=config.SAMPLE_RATE
            )
            self._audio_stream.start()

            # 校準 VAD
            print("[VoiceController] Calibrating VAD... stay quiet for 1 second")
            bg_rms = self._audio_stream.measure_background(1000)
            self._vad = VAD(background_rms=bg_rms)
            print(f"[VoiceController] Background RMS: {bg_rms:.2f}")

            # 收集噪音樣本
            self._collect_noise_samples()

            # 啟動辨識執行緒
            self._running = True
            self._thread = threading.Thread(
                target=self._recognition_loop,
                name="VoiceController-Recognition",
                daemon=True
            )
            self._thread.start()

            print(f"[VoiceController] Started with method: {self.method}")

        except Exception as e:
            self.event_bus.publish(Event(EventType.VOICE_ERROR, {'error': str(e)}))
            print(f"[VoiceController] Error starting: {e}")
            raise

    def stop(self) -> None:
        """停止語音辨識"""
        if not self._running:
            return

        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

        if self._audio_stream:
            self._audio_stream.stop()
            self._audio_stream = None

        print("[VoiceController] Stopped")

    def close(self) -> None:
        """關閉控制器（別名為 stop）"""
        self.stop()

    def listen_and_analyze(self, timeout: float = 0.1) -> Optional[str]:
        """
        取得下一個辨識的指令（輪詢模式）

        Args:
            timeout: 超時時間（秒）

        Returns:
            指令字串 ('START', 'JUMP' 等) 或 None
        """
        try:
            return self._command_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def set_method(self, method: str) -> None:
        """
        動態切換辨識方法

        Args:
            method: 'mfcc_dtw', 'ensemble', 'adaptive_ensemble'
        """
        self.method = method
        print(f"[VoiceController] Switched to method: {method}")

    def _collect_noise_samples(self, duration_ms: int = 1000, num_samples: int = 3) -> None:
        """
        收集噪音樣本供辨識器使用

        Args:
            duration_ms: 每個樣本長度（毫秒）
            num_samples: 樣本數量
        """
        import numpy as np

        samples_needed = int(config.SAMPLE_RATE * duration_ms / 1000)
        collected = []

        # 清空緩衝
        self._audio_stream.get_chunk()

        while len(collected) < samples_needed:
            chunk = self._audio_stream.get_chunk(timeout=0.1)
            if len(chunk) > 0:
                collected.extend(chunk)

        audio = np.array(collected[:samples_needed], dtype=np.int16)
        segment_len = len(audio) // num_samples

        for i in range(num_samples):
            segment = audio[i * segment_len:(i + 1) * segment_len]
            if len(segment) > 0:
                self._matcher.add_noise_template(segment)

        print(f"[VoiceController] Collected {num_samples} noise samples")

    def start_calibration_mode(self, command: str) -> None:
        """進入校正模式：當偵測到指定指令時自動加入模板"""
        print(f"[VoiceController] Entering calibration mode for: {command}")
        self._calibration_target = command
        self._calibration_start_time = time.time()
        # 清除舊的 VAD 狀態以免混淆
        if self._vad:
            self._vad.reset()

    def stop_calibration_mode(self) -> None:
        """離開校正模式"""
        if self._calibration_target:
            print(f"[VoiceController] Stopping calibration mode (was: {self._calibration_target})")
            self._calibration_target = None

    def _validate_audio(self, audio: np.ndarray) -> bool:
        """
        驗證錄製的音訊是否適合作為模板

        Returns:
            True if valid, False otherwise
        """
        # 檢查非空
        if len(audio) == 0:
            print("[VoiceController] Validation failed: empty audio")
            return False

        # 檢查最小長度 (100ms = 1600 samples at 16kHz)
        min_samples = int(config.SAMPLE_RATE * 0.1)
        if len(audio) < min_samples:
            print(f"[VoiceController] Validation failed: too short ({len(audio)} < {min_samples} samples)")
            return False

        # 檢查能量 (RMS 必須高於背景噪音 1.5 倍)
        rms = np.sqrt(np.mean(audio.astype(np.float32) ** 2))
        if self._vad:
            threshold = self._vad.background_rms * 1.5
            if rms < threshold:
                print(f"[VoiceController] Validation failed: too quiet (RMS={rms:.1f} < {threshold:.1f})")
                return False

        print(f"[VoiceController] Audio validation passed (length={len(audio)}, RMS={rms:.1f})")
        return True

    def _clear_command_templates(self, command: str) -> None:
        """清除指定指令的所有模板（自由模式用）"""
        print(f"[VoiceController] Clearing all templates for command: {command}")
        for method_name, matcher in self._matcher.matchers.items():
            if command in matcher.templates:
                matcher.templates[command] = []
                matcher.template_names[command] = []
                print(f"[VoiceController]   Cleared {method_name} templates for {command}")

    def _playback_audio(self, audio: np.ndarray) -> None:
        """播放音訊以確認錄製結果"""
        try:
            from .io import playback_audio
            print("[VoiceController] Playing back captured audio...")
            playback_audio(audio)
            print("[VoiceController] Playback complete")
        except Exception as e:
            print(f"[VoiceController] Playback error (non-critical): {e}")

    def _recognition_loop(self) -> None:
        """主要辨識迴圈"""
        while self._running:
            try:
                # 取得音訊塊
                chunk = self._audio_stream.get_chunk(timeout=0.1)
                if len(chunk) == 0:
                    continue

                # VAD 處理
                state, segment = self._vad.process_chunk(chunk)

                if state == VADState.PROCESSING and segment is not None:
                    # 辨識
                    start_time = time.time()

                    # Calculate SNR
                    sig_rms = np.sqrt(np.mean(segment.astype(np.float32) ** 2))
                    noise_rms = self._vad.background_rms

                    if noise_rms > 0 and sig_rms > noise_rms:
                        snr = 20 * np.log10(sig_rms / noise_rms)
                    else:
                        snr = 0.0

                    # 根據模式選擇方法
                    if self.method == 'mfcc_dtw':
                        result = self._matcher.recognize(segment, mode='best', adaptive=False, methods=['mfcc_dtw'])
                    elif self.method == 'ensemble':
                        result = self._matcher.recognize(segment, mode='best', adaptive=False)
                    else:
                        result = self._matcher.recognize(segment, mode='best', adaptive=True, known_snr=snr)

                    latency = (time.time() - start_time) * 1000
                    cmd = result['command']
                    conf = result.get('confidence', 0)

                    # 校正邏輯：如果正在校正且指令匹配
                    if self._calibration_target:
                        # 檢查是否超時 (例如 10秒)
                        if time.time() - self._calibration_start_time > 10.0:
                            print(f"[VoiceController] Calibration timeout for {self._calibration_target}")
                            self.event_bus.publish(Event(
                                EventType.CALIBRATION_RESULT,
                                {'command': self._calibration_target, 'success': False, 'message': 'Timeout'}
                            ))
                            self._calibration_target = None

                        # 自由模式：直接使用錄製的音訊，不需辨識
                        elif self.freedom_mode:
                            print(f"[VoiceController] Freedom mode: Capturing custom command for {self._calibration_target}")

                            # 驗證音訊品質
                            if self._validate_audio(segment):
                                print(f"[VoiceController] ✓ Valid audio captured for {self._calibration_target}")

                                try:
                                    # 清除該指令的所有現有模板
                                    self._clear_command_templates(self._calibration_target)

                                    # 加入新模板（這是唯一的模板）
                                    self._matcher.add_template(
                                        self._calibration_target,
                                        segment,
                                        f'freedom_{self._calibration_target}_{int(time.time())}'
                                    )
                                    print(f"[VoiceController] Custom template added for {self._calibration_target}")

                                    # 發布播放開始事件
                                    self.event_bus.publish(Event(
                                        EventType.PLAYBACK_START,
                                        {'command': self._calibration_target}
                                    ))

                                    # 播放確認
                                    self._playback_audio(segment)

                                    # 發布播放完成事件
                                    self.event_bus.publish(Event(
                                        EventType.PLAYBACK_COMPLETE,
                                        {'command': self._calibration_target}
                                    ))

                                    # 發布校正成功事件
                                    self.event_bus.publish(Event(
                                        EventType.CALIBRATION_RESULT,
                                        {
                                            'command': self._calibration_target,
                                            'success': True,
                                            'message': 'Custom command recorded',
                                            'energy': sig_rms
                                        }
                                    ))
                                    self._calibration_target = None  # 完成後移到下一個指令

                                except Exception as e:
                                    print(f"[VoiceController] Failed to add custom template: {e}")
                                    self.event_bus.publish(Event(
                                        EventType.CALIBRATION_RESULT,
                                        {'command': self._calibration_target, 'success': False, 'message': str(e)}
                                    ))
                                    # 不清除 _calibration_target，允許重試
                            else:
                                # 驗證失敗，發布失敗事件但不清除 target（自動重試）
                                print(f"[VoiceController] Invalid audio, waiting for retry...")
                                self.event_bus.publish(Event(
                                    EventType.CALIBRATION_RESULT,
                                    {
                                        'command': self._calibration_target,
                                        'success': False,
                                        'message': 'Audio too quiet or too short, please try again'
                                    }
                                ))
                                # 不清除 _calibration_target，停留在同一指令等待重試

                        # 一般模式：需要辨識匹配
                        elif cmd == self._calibration_target:
                            print(f"[VoiceController] ✓✓✓ Calibration MATCH! Adding template for {cmd}")
                            try:
                                # 加入一次性模板 (session only)
                                self._matcher.add_template(cmd, segment, f'live_calib_{int(time.time())}')
                                print(f"[VoiceController] Template added. Publishing CALIBRATION_RESULT for {cmd}")

                                # 發布成功事件
                                self.event_bus.publish(Event(
                                    EventType.CALIBRATION_RESULT,
                                    {'command': cmd, 'success': True, 'message': 'Calibration successful', 'energy': sig_rms}
                                ))
                                self._calibration_target = None # 完成後自動退出
                            except Exception as e:
                                print(f"[VoiceController] Failed to add calibration template: {e}")
                                self.event_bus.publish(Event(
                                    EventType.CALIBRATION_RESULT,
                                    {'command': self._calibration_target, 'success': False, 'message': str(e)}
                                ))
                                self._calibration_target = None
                        
                        # 如果是在校正模式，我們*仍然*可以發布 voice_command 讓遊戲繼續反應 (如果使用者希望的話)
                        # 但使用者說 "校正期間不是忽略口令"，暗示他希望口令被 "保存"。
                        # 是否要同時觸發遊戲動作？通常校正時介面會擋住遊戲，所以觸發動作也沒關係 (被前端擋住)。
                        # 但為了讓使用者看到 "我說了START，系統認到了START"，發布事件是好的。

                    if cmd not in ('NONE', 'NOISE'):
                        action = self.COMMAND_TO_ACTION.get(cmd, cmd)

                        self.event_bus.publish(Event(
                            EventType.VOICE_COMMAND,
                            {
                                'command': cmd,
                                'action': action,
                                'confidence': conf,
                                'method': self.method,
                                'latency_ms': latency,
                                'snr': snr
                            }
                        ))
                        self._command_queue.put(action)
                        print(f"[Voice] {cmd} (conf={conf:.2f}, {latency:.1f}ms, SNR={snr:.1f}dB)")
                    else:
                        self.event_bus.publish(Event(EventType.VOICE_NOISE, {'snr': snr}))

                    self._vad.reset()

            except Exception as e:
                print(f"[VoiceController] Error in recognition loop: {e}")
                self.event_bus.publish(Event(EventType.VOICE_ERROR, {'error': str(e)}))
                time.sleep(0.1)

    def calibrate_command(self, command: str, timeout: float = 5.0, on_progress=None) -> dict:
        """(Deprecated) Legacy blocking calibration. Now just wraps start_calibration_mode."""
        # 為了相容性保留介面，但實際上應該由 Server 呼叫 start_calibration_mode
        # 這裡簡單回傳 Error 提示改用非阻塞
        print("[VoiceController] Warning: Blocking calibrate_command is deprecated.")
        return {'success': False, 'message': 'Deprecated', 'energy': 0}