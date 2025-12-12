"""
ECG Adapter - Refactored based on ECG_original.py
"""

import threading
import time
import numpy as np
from typing import Optional, List, Deque
from collections import deque
from scipy.signal import lfilter, lfilter_zi, iirnotch, butter
import serial
import serial.tools.list_ports

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
        bpm_threshold: float = -10.0,      
        bpm_recovery: float = 50.0,       
        fallback_bpm: float = 75.0,       
        no_signal_timeout: float = 5.0,   
        retry_interval: float = 2.0      
    ):
        self.port = port
        self.baud_rate = baud_rate
        self.sample_rate = sample_rate
        self.event_bus = event_bus or EventBus()
        self.bpm_threshold = bpm_threshold
        self.bpm_recovery = bpm_recovery
        self.fallback_bpm = fallback_bpm
        self.no_signal_timeout = no_signal_timeout
        self.retry_interval = retry_interval

        # Serial
        self.ser: Optional[serial.Serial] = None
        self.hardware_available = False
        
        # Fallback state
        self.use_fallback = False
        self.last_fallback_peak_time = time.time()
        self.fallback_interval_sec = 60.0 / self.fallback_bpm
        self.last_retry_time = time.time()

        # Threading
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_peak_dir = 1

        # --- Logic from ECG_original.py ---
        # Constants
        self.FS = sample_rate
        self.BUF_LEN = int(self.FS * 3) # 3 seconds window
        
        # Buffers
        self.raw_buf = deque([0]*self.BUF_LEN, maxlen=self.BUF_LEN)
        self.sig_ma1_buf = deque([0]*self.BUF_LEN, maxlen=self.BUF_LEN)
        self.sig_mwi_buf = deque([0]*self.BUF_LEN, maxlen=self.BUF_LEN)

        # Filter initialization
        self._init_filters()

        # Peak Detection State
        self.sample_counter = 0
        self.REFRACTORY_PERIOD = int(0.25 * self.FS)
        self.SEARCH_WIN = int(0.1 * self.FS)
        self.last_peak_abs_idx = -self.REFRACTORY_PERIOD
        
        self.peak_indices_history = []
        self.rr_history = deque(maxlen=5) # RR_AVG_LEN = 5
        
        self.threshold_mwi = 50
        self.signal_mean = 120
        self.last_peak_time = time.time() # For timeout check

    def _init_filters(self):
        # 1. Notch Filter (60Hz)
        f0 = 60.0
        Q = 20.0
        self.b_notch, self.a_notch = iirnotch(f0, Q, self.FS)
        self.zi_notch = lfilter_zi(self.b_notch, self.a_notch) * 0

        # 2. Low Pass Filter (40Hz)
        def create_lowpass_filter(cutoff, fs, order=2):
            nyq = 0.5 * fs
            normal_cutoff = cutoff / nyq
            b, a = butter(order, normal_cutoff, btype='low', analog=False)
            return b, a

        self.b_lp, self.a_lp = create_lowpass_filter(40.0, self.FS, order=2)
        self.zi_lp = lfilter_zi(self.b_lp, self.a_lp) * 0

        # 3. Pan-Tompkins Filters
        # MA1
        self.WINDOW_MA1 = 8
        self.B_MA1 = np.ones(self.WINDOW_MA1) / self.WINDOW_MA1
        self.A_MA1 = 1
        self.zi_ma1 = lfilter_zi(self.B_MA1, self.A_MA1) * 0

        # Diff
        self.B_DIFF = np.array([1, -1])
        self.A_DIFF = 1
        self.zi_diff = lfilter_zi(self.B_DIFF, self.A_DIFF) * 0

        # MA2 (MWI)
        self.WINDOW_MA2 = int(0.150 * self.FS)
        self.B_MA2 = np.ones(self.WINDOW_MA2) / self.WINDOW_MA2
        self.A_MA2 = 1
        self.zi_ma2 = lfilter_zi(self.B_MA2, self.A_MA2) * 0

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

        print("[ECGAdapter] Stopped")

    def close(self) -> None:
        """關閉適配器"""
        self.stop()

    def _init_ecg_hardware(self) -> bool:
        """初始化 ECG 硬體"""
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()

            if self.port:
                print(f"[ECGAdapter] Connecting to {self.port}...")
                self.ser = serial.Serial(self.port, self.baud_rate, timeout=0)
            else:
                port_name = self._auto_detect_port()
                print(f"[ECGAdapter] Auto-detected port: {port_name}")
                self.ser = serial.Serial(port_name, self.baud_rate, timeout=0)
            
            self.ser.reset_input_buffer()
            print(f"[ECGAdapter] Connected to {self.ser.port}")
            
            self.hardware_available = True
            self.use_fallback = False
            self.last_retry_time = time.time()
            return True

        except Exception as e:
            print(f"[ECGAdapter] Failed to initialize ECG hardware: {e}")
            self.use_fallback = True
            self.hardware_available = False
            self.ser = None
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
        """處理真實 ECG 訊號 (Optimized logic)"""
        if not self.ser:
            return

        try:
            bytes_to_read = self.ser.in_waiting
            if bytes_to_read == 0:
                # Check timeout
                if time.time() - self.last_peak_time > self.no_signal_timeout:
                    print(f"[ECGAdapter] No signal timeout, switching to fallback")
                    self.use_fallback = True
                    self.hardware_available = False
                    return
                return

            raw_data_str = self.ser.read(bytes_to_read).decode('utf-8', errors='ignore')
            lines = raw_data_str.split('\n')
            
            new_data = []
            for line in lines:
                line = line.strip()
                if line:
                    try:
                        new_data.append(float(line))
                    except ValueError:
                        continue
            
            if not new_data:
                return

            new_data = np.array(new_data)

            # === Filter Chain ===
            # 1. Notch
            out_notch, self.zi_notch = lfilter(self.b_notch, self.a_notch, new_data, zi=self.zi_notch)
            # 2. Low Pass
            out_lp, self.zi_lp = lfilter(self.b_lp, self.a_lp, out_notch, zi=self.zi_lp)
            # 3. MA1
            out_ma1, self.zi_ma1 = lfilter(self.B_MA1, self.A_MA1, out_lp, zi=self.zi_ma1)
            # 4. Diff
            out_diff, self.zi_diff = lfilter(self.B_DIFF, self.A_DIFF, out_ma1, zi=self.zi_diff)
            # 5. Square
            out_sq = out_diff ** 2
            # 6. MA2 (MWI)
            out_mwi, self.zi_ma2 = lfilter(self.B_MA2, self.A_MA2, out_sq, zi=self.zi_ma2)

            # Update Buffers
            self.sig_ma1_buf.extend(out_ma1)
            self.sig_mwi_buf.extend(out_mwi)

            # Update Baseline
            if len(out_ma1) > 0:
                batch_mean = np.mean(out_ma1)
                self.signal_mean = 0.99 * self.signal_mean + 0.01 * batch_mean

            # === Peak Detection ===
            # Index logic from ECG_original.py
            # out_mwi is the new batch. We iterate over it.
            
            for i in range(len(out_mwi)):
                curr_abs_idx = self.sample_counter + i
                
                # We need access to recent MWI buffer.
                # Since we extended sig_mwi_buf, the last N points are the new ones.
                # We need to look back safely.
                # In ECG_original: buf_idx = -(len(out_mwi) - i)
                # sig_mwi_buf[-1] is the last element of the *entire* buffer (latest)
                # if i=0 (first in batch), buf_idx = -len(batch). 
                # e.g. batch size 5. i=0 -> -5. i=4 -> -1. Correct.
                
                buf_idx = -(len(out_mwi) - i)
                
                # Need at least 3 points in history
                if len(self.sig_mwi_buf) < 3: continue 
                if buf_idx > -3: continue # Safety check if batch is very small? 
                # Actually if buf_idx is -1, buf_idx-2 is -3. So we need valid indices.
                # standard deque supports negative indexing.
                
                curr_mwi_val = self.sig_mwi_buf[buf_idx]
                prev_mwi_val = self.sig_mwi_buf[buf_idx-1]
                prev2_mwi_val = self.sig_mwi_buf[buf_idx-2]

                # Dynamic Threshold Update
                if curr_abs_idx % 50 == 0:
                    # Look at recent 1 sec (FS samples)
                    recent_mwi = list(self.sig_mwi_buf)[-int(self.FS):]
                    if recent_mwi:
                        # Optimization: Lower threshold factor to 0.4 for better sensitivity
                        self.threshold_mwi = 0.4 * max(recent_mwi)
                        if self.threshold_mwi < 10: self.threshold_mwi = 10

                # Peak Condition
                if prev_mwi_val > self.threshold_mwi and prev_mwi_val > curr_mwi_val and prev_mwi_val > prev2_mwi_val:
                    
                    peak_candidate_abs = curr_abs_idx - 1
                    
                    if (peak_candidate_abs - self.last_peak_abs_idx) > self.REFRACTORY_PERIOD:
                        
                        # Backtracking in Signal Buffer (sig_ma1_buf)
                        # search window defined in init
                        search_end = buf_idx - 1
                        search_start = search_end - self.SEARCH_WIN
                        
                        # Handle deque slicing safely
                        # Convert to list is expensive if full buffer. 
                        # Optimization: just take the slice we need from the end
                        # sig_ma1_buf is deque. 
                        # We can convert the relevant tail to list.
                        # We need up to SEARCH_WIN + batch size roughly.
                        
                        # Simplify: convert tail to list
                        tail_len = int(self.SEARCH_WIN + len(out_mwi) + 10)
                        tail_data = list(self.sig_ma1_buf)[-tail_len:]
                        
                        # Adjust indices relative to tail
                        # buf_idx is negative from end.
                        # tail_end = len(tail_data) + buf_idx (e.g. 100 + (-5) = 95)
                        
                        t_end = len(tail_data) + search_end
                        t_start = len(tail_data) + search_start
                        
                        if t_start < 0: t_start = 0
                        if t_end > t_start:
                            search_data = tail_data[t_start:t_end]
                            
                            if search_data:
                                local_max = np.max(search_data)
                                local_max_idx = np.argmax(search_data)
                                
                                # Amplitude Check
                                # Optimization: Lower offset to 5 to catch weaker peaks
                                amplitude_thresh = self.signal_mean + 5
                                
                                if local_max > amplitude_thresh:
                                    # Calculate real peak abs index
                                    # offset from t_end
                                    # search_data is [t_start : t_end]
                                    # local_max_idx is relative to t_start
                                    # real index in deque?
                                    
                                    # offset = len(search_data) - local_max_idx (distance from end of search region)
                                    # real_peak_abs = peak_candidate_abs - offset
                                    
                                    offset = len(search_data) - local_max_idx
                                    real_peak_abs = peak_candidate_abs - offset
                                    
                                    if (real_peak_abs - self.last_peak_abs_idx) > self.REFRACTORY_PERIOD:
                                        self.peak_indices_history.append(real_peak_abs)
                                        self.last_peak_abs_idx = real_peak_abs
                                        self.last_peak_time = time.time() # Reset timeout
                                        
                                        # BPM Calculation
                                        bpm = 0
                                        if len(self.peak_indices_history) >= 2:
                                            prev_peak = self.peak_indices_history[-2]
                                            rr_sec = (real_peak_abs - prev_peak) / self.FS
                                            if 0.4 < rr_sec < 1.5:
                                                self.rr_history.append(rr_sec)
                                                bpm = 60.0 / np.mean(self.rr_history)
                                                
                                                # Event Publishing
                                                self._last_peak_dir *= -1
                                                event_data = {
                                                    'type': 'peak',
                                                    'dir': self._last_peak_dir,
                                                    'value': float(local_max),
                                                    'bpm': bpm
                                                }
                                                self.event_bus.publish(Event(EventType.ECG_PEAK, event_data))
                                                self.event_bus.publish(Event(EventType.ECG_BPM_UPDATE, {'bpm': bpm}))
                                                
                                                # [REQ] Required Print Format
                                                print(f"[ECGAdapter] Real ECG peak: BPM={bpm:.1f}")

            self.sample_counter += len(out_mwi)

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
