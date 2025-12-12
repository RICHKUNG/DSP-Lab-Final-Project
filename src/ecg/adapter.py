"""
ECG Adapter - 使用 ecg_reader.py 並提供 BPM 低於閾值時的 fallback
"""

import threading
import time
import numpy as np
from typing import Optional
from collections import deque

try:
    from .ecg_reader import ECGProcessor
    ECG_READER_AVAILABLE = True
except ImportError:
    ECG_READER_AVAILABLE = False
    print("[WARN] ecg_reader not available")

from ..event_bus import EventBus, Event, EventType


class ECGAdapter:
    """
    ECG 適配器

    功能：
    - 使用 ECGProcessor (ecg_reader.py) 處理真實 ECG
    - BPM 低於閾值或 None 時自動切換到假訊號
    - 發布 ECG_PEAK 和 ECG_BPM_UPDATE 事件
    """

    def __init__(
        self,
        port: Optional[str] = None,
        baud_rate: int = 115200,
        sample_rate: float = 500.0,
        event_bus: Optional[EventBus] = None,
        bpm_threshold: float = -10.0,      # BPM 低於此值時使用假訊號
        bpm_recovery: float = 50.0,        # BPM 高於此值時恢復真實訊號
        fallback_bpm: float = 75.0,        # 假訊號的 BPM
        no_signal_timeout: float = 5.0,    # 多久沒訊號就切換 fallback (秒)
        retry_interval: float = 10.0       # fallback 模式下多久重試真實 ECG (秒)
    ):
        """
        初始化 ECG 適配器 (支援動態切換)

        Args:
            port: Serial Port (None=自動偵測)
            baud_rate: 鮑率
            sample_rate: 採樣率 (Hz)
            event_bus: EventBus 實例
            bpm_threshold: BPM 低於此值時切換到假訊號
            bpm_recovery: BPM 高於此值時恢復真實訊號 (應 > bpm_threshold)
            fallback_bpm: 假訊號的 BPM
            no_signal_timeout: 多久沒訊號就切換 fallback (秒)
            retry_interval: fallback 模式下多久重試真實 ECG (秒)
        """
        self.port = port
        self.baud_rate = baud_rate
        self.sample_rate = sample_rate
        self.event_bus = event_bus or EventBus()
        self.bpm_threshold = bpm_threshold
        self.bpm_recovery = bpm_recovery
        self.fallback_bpm = fallback_bpm
        self.no_signal_timeout = no_signal_timeout
        self.retry_interval = retry_interval

        # ECG Processor
        self.processor: Optional[ECGProcessor] = None
        self.hardware_available = False

        # Fallback 狀態
        self.use_fallback = False
        self.last_fallback_peak_time = time.time()
        self.fallback_interval_sec = 60.0 / self.fallback_bpm
        self.last_retry_time = time.time()

        # BPM 追蹤
        self.bpm_history = deque(maxlen=10)
        self.last_valid_bpm = fallback_bpm
        self.last_peak_time = time.time()
        self.consecutive_good_bpm = 0  # 連續好的 BPM 次數 (用於恢復判斷)

        # 執行緒
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_peak_dir = 1  # 交替方向

    def start(self) -> None:
        """啟動 ECG 處理"""
        if self._running:
            print("[ECGAdapter] Already running")
            return

        # 嘗試初始化真實 ECG
        self._init_ecg_hardware()

        # 啟動處理執行緒
        self._running = True
        self._thread = threading.Thread(
            target=self._processing_loop,
            name="ECGAdapter-Processing",
            daemon=True
        )
        self._thread.start()

        if self.use_fallback:
            print(f"[ECGAdapter] Started in FALLBACK mode ({self.fallback_bpm} BPM)")
        else:
            print("[ECGAdapter] Started with real ECG")

    def stop(self) -> None:
        """停止 ECG 處理"""
        if not self._running:
            return

        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

        # 關閉 Serial Port
        if self.processor and hasattr(self.processor, 'ser') and self.processor.ser.is_open:
            self.processor.ser.close()
            print("[ECGAdapter] Serial port closed")

        print("[ECGAdapter] Stopped")

    def close(self) -> None:
        """關閉適配器"""
        self.stop()

    def _init_ecg_hardware(self) -> bool:
        """初始化 ECG 硬體，返回是否成功"""
        if not ECG_READER_AVAILABLE:
            print("[ECGAdapter] ECG reader not available, using fallback mode")
            self.use_fallback = True
            self.hardware_available = False
            return False

        try:
            if self.port:
                print(f"[ECGAdapter] Connecting to {self.port}...")
                self.processor = ECGProcessor(
                    port=self.port,
                    baud=self.baud_rate,
                    fs=self.sample_rate
                )
                print(f"[ECGAdapter] Connected to {self.port}")
            else:
                # 自動偵測
                print("[ECGAdapter] Auto-detecting serial port...")
                self.processor = ECGProcessor(
                    port=self._auto_detect_port(),
                    baud=self.baud_rate,
                    fs=self.sample_rate
                )
                print(f"[ECGAdapter] Connected to {self.processor.ser.port}")

            self.hardware_available = True
            self.use_fallback = False
            self.last_retry_time = time.time()
            return True

        except Exception as e:
            print(f"[ECGAdapter] Failed to initialize ECG hardware: {e}")
            print(f"[ECGAdapter] Using fallback mode ({self.fallback_bpm} BPM)")
            self.use_fallback = True
            self.hardware_available = False
            self.processor = None
            self.last_retry_time = time.time()
            return False

    def _auto_detect_port(self) -> str:
        """自動偵測 Serial Port"""
        try:
            import serial.tools.list_ports
            ports = list(serial.tools.list_ports.comports())

            if not ports:
                raise Exception("No serial ports found")

            # 優先尋找 Arduino
            for p in ports:
                if "Arduino" in p.description or "Arduino" in p.manufacturer:
                    return p.device

            # 返回第一個
            return ports[0].device
        except Exception as e:
            raise Exception(f"Auto-detection failed: {e}")

    def _processing_loop(self) -> None:
        """主要處理迴圈 (支援動態切換)"""
        while self._running:
            try:
                if self.use_fallback:
                    # 假訊號模式
                    self._process_fallback()

                    # 定期重試真實 ECG
                    if time.time() - self.last_retry_time >= self.retry_interval:
                        print(f"[ECGAdapter] Retrying real ECG connection...")
                        if self._init_ecg_hardware():
                            print(f"[ECGAdapter] Switched back to real ECG")
                            self.consecutive_good_bpm = 0
                else:
                    # 真實 ECG 模式
                    self._process_real_ecg()

                time.sleep(0.001)  # 1ms

            except Exception as e:
                print(f"[ECGAdapter] Error in processing loop: {e}")
                # 切換到 fallback
                if not self.use_fallback:
                    print(f"[ECGAdapter] Switching to fallback mode due to error")
                    self.use_fallback = True
                    self.hardware_available = False
                    self.last_retry_time = time.time()
                time.sleep(0.1)

    def _process_real_ecg(self) -> None:
        """處理真實 ECG 訊號 (支援動態切換)"""
        if not self.processor:
            return

        try:
            bpm, filtered_values = self.processor.process()

            # 檢查是否有新的峰值 (bpm 不為 None 表示偵測到新峰值)
            if bpm is not None:
                # 更新時間戳
                self.last_peak_time = time.time()

                # 記錄 BPM
                self.bpm_history.append(bpm)
                self.last_valid_bpm = bpm

                # 發布 BPM 更新事件
                self.event_bus.publish(Event(
                    EventType.ECG_BPM_UPDATE,
                    {'bpm': bpm}
                ))

                # 檢查 BPM 是否過低 (使用 threshold)
                if bpm < self.bpm_threshold:
                    print(f"[ECGAdapter] BPM too low ({bpm:.1f} < {self.bpm_threshold}), switching to fallback")
                    self.use_fallback = True
                    self.hardware_available = False
                    self.last_retry_time = time.time()
                    self.consecutive_good_bpm = 0
                    return

                # BPM 正常，重置連續計數
                self.consecutive_good_bpm += 1

                # 發布峰值事件
                self._last_peak_dir *= -1
                event_data = {
                    'type': 'peak',
                    'dir': self._last_peak_dir,
                    'value': np.max(filtered_values) if filtered_values is not None and len(filtered_values) > 0 else 800.0,
                    'bpm': bpm
                }

                self.event_bus.publish(Event(EventType.ECG_PEAK, event_data))
                print(f"[ECGAdapter] Real ECG peak: BPM={bpm:.1f}")

            else:
                # 沒有新峰值 - 檢查超時
                time_since_last_peak = time.time() - self.last_peak_time
                if time_since_last_peak > self.no_signal_timeout:
                    print(f"[ECGAdapter] No signal for {time_since_last_peak:.1f}s, switching to fallback")
                    self.use_fallback = True
                    self.hardware_available = False
                    self.last_retry_time = time.time()
                    self.consecutive_good_bpm = 0

        except Exception as e:
            print(f"[ECGAdapter] Error processing real ECG: {e}")
            raise

    def _process_fallback(self) -> None:
        """生成假 ECG 訊號 (基於時間)"""
        current_time = time.time()
        time_since_last_peak = current_time - self.last_fallback_peak_time

        # 檢查是否該生成下一個峰值
        if time_since_last_peak >= self.fallback_interval_sec:
            self.last_fallback_peak_time = current_time

            # 交替方向
            self._last_peak_dir *= -1

            event_data = {
                'type': 'peak',
                'dir': self._last_peak_dir,
                'value': 800.0,  # 假振幅
                'bpm': self.fallback_bpm
            }

            # [MODIFIED] Fallback 模式也要產生障礙物
            self.event_bus.publish(Event(EventType.ECG_PEAK, event_data))
            
            self.event_bus.publish(Event(
                EventType.ECG_BPM_UPDATE,
                {'bpm': self.fallback_bpm}
            ))
            print(f"[ECGAdapter] Fallback peak generated: BPM={self.fallback_bpm}")
