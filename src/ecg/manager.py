"""
ECGManager - ECG 訊號處理與 R-R 峰值偵測
整合 Serial 通訊、濾波鏈、峰值偵測
"""

import threading
import time
import numpy as np
from collections import deque
from typing import Optional, Dict, Any, List
from scipy import signal as sp_signal

try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    print("[WARN] pyserial not installed, ECG功能將無法使用")

from ..event_bus import EventBus, Event, EventType


class ECGManager:
    """
    ECG 訊號管理器

    功能：
    - Serial 通訊（自動偵測 COM Port）
    - 即時濾波（MA → 差分 → 平方 → MWI）
    - R-R 峰值偵測（附 Refractory Period）
    - BPM 計算
    - EventBus 整合

    使用方式：
        manager = ECGManager(port=None)  # 自動偵測
        manager.start()
        # 輪詢模式
        signal = manager.get_signal()
        # 或訂閱事件
        event_bus.subscribe(EventType.ECG_PEAK, callback)
    """

    def __init__(
        self,
        port: Optional[str] = None,
        baud_rate: int = 115200,
        sample_rate: float = 500.0,
        event_bus: Optional[EventBus] = None,
        simulate: bool = False
    ):
        """
        初始化 ECG 管理器

        Args:
            port: Serial Port (None=自動偵測)
            baud_rate: 鮑率
            sample_rate: 採樣率 (Hz)
            event_bus: EventBus 實例
            simulate: 是否強制使用模擬模式
        """
        self.port = port
        self.baud_rate = baud_rate
        self.sample_rate = sample_rate
        self.event_bus = event_bus or EventBus()
        self.simulate = simulate

        # Serial
        self._serial: Optional[serial.Serial] = None
        self._serial_buffer = ""
        self._is_simulating = False
        self._sim_counter = 0

        # 濾波器狀態
        self._init_filters()

        # 峰值偵測
        self._init_peak_detector()

        # 狀態
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_peak_dir = 1  # 交替方向

        # 輪詢佇列
        self._signal_queue = deque(maxlen=100)

    def _init_filters(self) -> None:
        """初始化濾波器"""
        # MA1: 平滑 (8 點)
        self.window_ma1 = 8
        self.b_ma1 = np.ones(self.window_ma1) / self.window_ma1
        self.zi_ma1 = np.zeros(self.window_ma1 - 1)

        # 差分
        self.b_diff = np.array([1, -1])
        self.zi_diff = np.zeros(1)

        # MWI: 移動窗積分 (40 點)
        self.window_mwi = 40
        self.b_mwi = np.ones(self.window_mwi) / self.window_mwi
        self.zi_mwi = np.zeros(self.window_mwi - 1)

    def _init_peak_detector(self) -> None:
        """初始化峰值偵測器"""
        # Refractory Period: 250ms
        self.refractory_samples = int(0.25 * self.sample_rate)
        self.last_peak_counter = -self.refractory_samples
        self.sample_counter = 0

        # 歷史資料
        self.mwi_history = deque(maxlen=int(2 * self.sample_rate))
        self.ma1_history = deque(maxlen=int(0.05 * self.sample_rate))

        # R-R 間隔歷史 (用於 BPM)
        self.rr_history = deque(maxlen=5)
        self.last_peak_time = 0.0

        # 前3個樣本（用於局部極大值偵測）
        self.prev_mwi = [0, 0, 0]

    def start(self) -> None:
        """啟動 ECG 處理"""
        if self._running:
            print("[ECGManager] Already running")
            return

        if not SERIAL_AVAILABLE and not self.simulate:
            print("[ECGManager] ERROR: pyserial not installed and simulation not enabled")
            return

        try:
            # 連接 Serial 或 啟動模擬
            self._connect_serial()

            # 啟動處理執行緒
            self._running = True
            self._thread = threading.Thread(
                target=self._processing_loop,
                name="ECGManager-Processing",
                daemon=True
            )
            self._thread.start()

            if self._is_simulating:
                print("[ECGManager] Started in SIMULATION mode")
            else:
                print(f"[ECGManager] Started on {self._serial.port if self._serial else 'N/A'}")

        except Exception as e:
            self.event_bus.publish(Event(EventType.ECG_ERROR, {'error': str(e)}))
            print(f"[ECGManager] Error starting: {e}")
            raise

    def stop(self) -> None:
        """停止 ECG 處理"""
        if not self._running:
            return

        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

        if self._serial:
            self._serial.close()
            self._serial = None
        
        self._is_simulating = False

        print("[ECGManager] Stopped")

    def close(self) -> None:
        """關閉管理器（別名為 stop）"""
        self.stop()

    def get_signal(self) -> Optional[Dict[str, Any]]:
        """
        取得下一個訊號事件（輪詢模式）

        Returns:
            Dict: {'type': 'peak', 'dir': ±1, 'value': amplitude, 'bpm': ...}
            或 None
        """
        try:
            return self._signal_queue.popleft()
        except IndexError:
            return None

    def _connect_serial(self) -> None:
        """連接 Serial Port（自動偵測）或啟用模擬"""
        if self.simulate:
            self._is_simulating = True
            return

        if self.port:
            # 使用使用者指定 Port
            try:
                self._serial = serial.Serial(self.port, self.baud_rate, timeout=0)
                self._serial.reset_input_buffer()
                print(f"[ECGManager] Connected to specified port: {self.port}")
                return
            except Exception as e:
                print(f"[ECGManager] Failed to connect to specified {self.port}: {e}")
                print("[ECGManager] Falling back to SIMULATION mode")
                self._is_simulating = True
                return

        # 自動偵測
        import serial.tools.list_ports
        ports = list(serial.tools.list_ports.comports())
        
        if not ports:
            print("[ECGManager] No serial ports found.")
            print("[ECGManager] Falling back to SIMULATION mode")
            self._is_simulating = True
            return

        print(f"[ECGManager] Scanning {len(ports)} ports...")
        
        # 優先尋找 "Arduino"
        arduino_port = None
        for p in ports:
            if "Arduino" in p.description or "Arduino" in p.manufacturer:
                arduino_port = p
                break
        
        # 如果有 Arduino，把它排到第一個測試
        if arduino_port:
            ports.remove(arduino_port)
            ports.insert(0, arduino_port)

        for port_info in ports:
            try:
                print(f"[ECGManager] Testing {port_info.device} ({port_info.description})...")
                test_serial = serial.Serial(port_info.device, self.baud_rate, timeout=0)
                # 測試讀取
                time.sleep(1.0) # 等待 Arduino 重啟
                test_serial.close()
                
                # 真正連線
                self._serial = serial.Serial(port_info.device, self.baud_rate, timeout=0)
                self._serial.reset_input_buffer()
                self.port = port_info.device
                print(f"[ECGManager] ✓ Successfully connected to: {self.port}")
                return
            except Exception as e:
                print(f"[ECGManager] ✗ Failed {port_info.device}: {e}")
                continue
        
        # 若找不到 Port，啟用模擬
        print("[ECGManager] Could not connect to any COM Port.")
        print("[ECGManager] Falling back to SIMULATION mode")
        self._is_simulating = True

    def _read_samples(self) -> List[float]:
        """讀取並解析 Serial 樣本"""
        if self._is_simulating:
            return self._generate_simulated_samples()

        if not self._serial:
            return []

        bytes_available = self._serial.in_waiting
        if bytes_available == 0:
            return []

        raw_data = self._serial.read(bytes_available).decode('utf-8', errors='ignore')
        self._serial_buffer += raw_data

        samples = []
        lines = self._serial_buffer.split('\n')
        self._serial_buffer = lines[-1]  # 保留未完成的行

        for line in lines[:-1]:
            line = line.strip()
            if not line:
                continue
            try:
                val = float(line)
                # 有效範圍過濾
                if 10 < val < 1000:
                    samples.append(val)
            except ValueError:
                continue

        return samples

    def _generate_simulated_samples(self) -> List[float]:
        """生成模擬 ECG 樣本"""
        samples = []
        # 每次生成 5 個樣本 (約 10ms at 500Hz)
        for _ in range(5):
            self._sim_counter += 1
            # 基線 512 + 雜訊
            val = 512 + np.random.normal(0, 5)
            
            # 每 400 點 (0.8s, 75 BPM) 產生一個 P-QRS-T 波形
            cycle = 400
            phase = self._sim_counter % cycle
            
            # 簡單的 QRS 模擬
            if 0 <= phase < 10:  # Q (dip)
                val -= 30
            elif 10 <= phase < 25: # R (spike)
                val += 300
            elif 25 <= phase < 35: # S (dip)
                val -= 50
            elif 60 <= phase < 90: # T (bump)
                val += 40
                
            samples.append(val)
        
        time.sleep(0.01) # 控制模擬速率
        return samples

    def _process_sample(self, raw_value: float) -> Dict[str, Any]:
        """
        處理單一樣本（濾波 + 峰值偵測）

        Returns:
            Dict: {'ma1': ..., 'mwi': ..., 'is_peak': bool, 'amplitude': ..., 'bpm': ...}
        """
        self.sample_counter += 1

        # 1. MA1 平滑
        x = np.array([raw_value])
        out_ma1, self.zi_ma1 = sp_signal.lfilter(self.b_ma1, 1, x, zi=self.zi_ma1)
        ma1_value = out_ma1[0]
        self.ma1_history.append(ma1_value)

        # 2. 差分
        out_diff, self.zi_diff = sp_signal.lfilter(self.b_diff, 1, out_ma1, zi=self.zi_diff)

        # 3. 平方
        out_sq = out_diff ** 2

        # 4. MWI
        out_mwi, self.zi_mwi = sp_signal.lfilter(self.b_mwi, 1, out_sq, zi=self.zi_mwi)
        mwi_value = out_mwi[0]
        self.mwi_history.append(mwi_value)

        # 更新前3個樣本
        self.prev_mwi = [self.prev_mwi[1], self.prev_mwi[2], mwi_value]

        # 5. 峰值偵測
        is_peak, amplitude, bpm = self._detect_peak()

        return {
            'ma1': ma1_value,
            'mwi': mwi_value,
            'is_peak': is_peak,
            'amplitude': amplitude,
            'bpm': bpm
        }

    def _detect_peak(self) -> tuple:
        """
        偵測 R 波峰值

        Returns:
            (is_peak: bool, amplitude: float, bpm: float)
        """
        # 計算動態閾值
        if len(self.mwi_history) > 10:
            local_max = max(self.mwi_history)
            threshold = max(0.6 * local_max, 20)
        else:
            threshold = 20

        # 檢查 Refractory Period
        if (self.sample_counter - self.last_peak_counter) <= self.refractory_samples:
            return False, 0.0, 0.0

        # 局部極大值偵測
        is_peak = (
            self.prev_mwi[1] > threshold and
            self.prev_mwi[1] > self.prev_mwi[2] and
            self.prev_mwi[1] > self.prev_mwi[0]
        )

        if not is_peak:
            return False, 0.0, 0.0

        # 找到峰值 - 計算 BPM
        current_time = self.sample_counter / self.sample_rate

        bpm = 0.0
        if self.last_peak_time > 0:
            rr_interval = current_time - self.last_peak_time
            # 有效 R-R 範圍: 0.25-2.0 秒 (30-240 BPM)
            if 0.25 < rr_interval < 2.0:
                self.rr_history.append(rr_interval)

        if len(self.rr_history) > 0:
            avg_rr = np.mean(self.rr_history)
            bpm = 60.0 / avg_rr

        self.last_peak_time = current_time
        self.last_peak_counter = self.sample_counter

        # 取得 R 波振幅（從 MA1 訊號）
        amplitude = max(self.ma1_history) if self.ma1_history else self.prev_mwi[1]

        return True, amplitude, bpm

    def _processing_loop(self) -> None:
        """主要處理迴圈"""
        while self._running:
            try:
                # 讀取樣本
                samples = self._read_samples()
                if not samples:
                    time.sleep(0.001)
                    continue

                # 處理每個樣本
                for raw_value in samples:
                    result = self._process_sample(raw_value)

                    if result['is_peak']:
                        # 交替方向（遊戲障礙物多樣性）
                        self._last_peak_dir *= -1

                        event_data = {
                            'type': 'peak',
                            'dir': self._last_peak_dir,
                            'value': result['amplitude'],
                            'bpm': result['bpm']
                        }

                        # 發布事件
                        self.event_bus.publish(Event(EventType.ECG_PEAK, event_data))

                        # 加入輪詢佇列
                        self._signal_queue.append(event_data)

                        # BPM 更新事件
                        if result['bpm'] > 0:
                            self.event_bus.publish(Event(
                                EventType.ECG_BPM_UPDATE,
                                {'bpm': result['bpm']}
                            ))

                        print(f"[ECG] Peak detected: BPM={result['bpm']:.1f}")

            except Exception as e:
                print(f"[ECGManager] Error in processing loop: {e}")
                self.event_bus.publish(Event(EventType.ECG_ERROR, {'error': str(e)}))
                time.sleep(0.1)
