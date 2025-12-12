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
        method: str = 'adaptive_ensemble'
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
        """
        self.event_bus = event_bus or EventBus()
        self.template_dir = template_dir or str(Path(__file__).parent.parent.parent / "cmd_templates")
        self.method = method

        # 組件
        self._audio_stream: Optional[AudioStream] = None
        self._vad: Optional[VAD] = None
        self._matcher = MultiMethodMatcher()

        # 狀態
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._command_queue = queue.Queue()

        # 載入模板
        self._load_templates()

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

                    # Calculate SNR using VAD background estimation
                    sig_rms = np.sqrt(np.mean(segment.astype(np.float32) ** 2))
                    noise_rms = self._vad.background_rms
                    
                    if noise_rms > 0 and sig_rms > noise_rms:
                        snr = 20 * np.log10(sig_rms / noise_rms)
                    else:
                        snr = 0.0

                    if self.method == 'mfcc_dtw':
                        # 僅使用 MFCC
                        result = self._matcher.recognize(segment, mode='best', adaptive=False, methods=['mfcc_dtw'])
                    elif self.method == 'ensemble':
                        # 固定權重 Ensemble
                        result = self._matcher.recognize(segment, mode='best', adaptive=False)
                    else:  # adaptive_ensemble
                        # SNR 自適應 Ensemble
                        result = self._matcher.recognize(segment, mode='best', adaptive=True, known_snr=snr)

                    latency = (time.time() - start_time) * 1000  # ms

                    cmd = result['command']
                    conf = result.get('confidence', 0)

                    if cmd not in ('NONE', 'NOISE'):
                        action = self.COMMAND_TO_ACTION.get(cmd, cmd)

                        # 發布事件
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

                        # 加入輪詢佇列
                        self._command_queue.put(action)

                        print(f"[Voice] {cmd} (conf={conf:.2f}, {latency:.1f}ms, SNR={snr:.1f}dB)")
                    else:
                        # 噪音事件
                        self.event_bus.publish(Event(EventType.VOICE_NOISE, {'snr': snr}))

                    # 重置 VAD
                    self._vad.reset()

            except Exception as e:
                print(f"[VoiceController] Error in recognition loop: {e}")
                self.event_bus.publish(Event(EventType.VOICE_ERROR, {'error': str(e)}))
                time.sleep(0.1)