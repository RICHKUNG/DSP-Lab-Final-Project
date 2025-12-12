import serial
import numpy as np
from collections import deque
from scipy.signal import lfilter, lfilter_zi, iirnotch, butter

class ECGProcessor:

    def __init__(self, port='COM4', baud=115200, fs=500):

        # --- Serial ---
        self.ser = serial.Serial(port, baud, timeout=0)
        self.ser.reset_input_buffer()

        # --- Basic parameters ---
        self.fs = fs
        self.dt = 1.0 / fs

        # Buffers
        self.BUF_LEN = int(3 * fs)
        self.raw_buf = deque([0]*self.BUF_LEN, maxlen=self.BUF_LEN)
        self.sig_buf = deque([0]*self.BUF_LEN, maxlen=self.BUF_LEN)
        self.mwi_buf = deque([0]*self.BUF_LEN, maxlen=self.BUF_LEN)

        # --- Filters ---
        # 1. Notch (60 Hz)
        f0 = 60.0
        Q = 20.0
        self.b_notch, self.a_notch = iirnotch(f0, Q, fs)
        self.zi_notch = lfilter_zi(self.b_notch, self.a_notch) * 0

        # 2. Low Pass (40 Hz)
        self.b_lp, self.a_lp = self._create_lowpass_filter(40, fs, order=2)
        self.zi_lp = lfilter_zi(self.b_lp, self.a_lp) * 0

        # 3. Pan–Tompkins smoothing filters
        self.B_MA1 = np.ones(8)/8  # MA1
        self.A_MA1 = 1
        self.zi_ma1 = lfilter_zi(self.B_MA1, self.A_MA1)*0

        self.B_DIFF = np.array([1, -1])
        self.A_DIFF = 1
        self.zi_diff = lfilter_zi(self.B_DIFF, self.A_DIFF)*0

        win_ma2 = int(0.150*fs)
        self.B_MA2 = np.ones(win_ma2) / win_ma2
        self.A_MA2 = 1
        self.zi_ma2 = lfilter_zi(self.B_MA2, self.A_MA2)*0

        # --- Peak Detection ---
        self.sample_counter = 0
        self.last_peak = -int(0.25*fs)
        self.RR_HISTORY = deque(maxlen=5)
        self.threshold = 40
        self.signal_mean = 120

        self.SEARCH_WIN = int(0.1*fs)
        self.REFRACTORY = int(0.25*fs)

        self.peak_history = []
        self.bpm = 0

    # ----------------------
    def _create_lowpass_filter(self, cutoff, fs, order=2):
        nyq = 0.5 * fs
        normal = cutoff / nyq
        return butter(order, normal, btype="low")

    # ----------------------
    def _read_from_serial(self):
        n = self.ser.in_waiting
        if n == 0:
            return None

        raw = self.ser.read(n).decode("utf-8", errors="ignore").split("\n")
        arr = []
        for line in raw:
            line = line.strip()
            if line:
                try:
                    arr.append(float(line))
                except:
                    pass
        if len(arr) == 0:
            return None
        return np.array(arr)

    # ----------------------
    def process(self):
        """
        回傳： (bpm, filtered_values)
        - bpm: 若沒有新的 R 峰 → None
        - filtered_values: 當批濾波後的 ECG 值 ndarray
        """
        data = self._read_from_serial()
        if data is None:
            return None, None

        # ==== FILTER CHAIN ====
        out1, self.zi_notch = lfilter(self.b_notch, self.a_notch, data, zi=self.zi_notch)
        out2, self.zi_lp    = lfilter(self.b_lp, self.a_lp, out1, zi=self.zi_lp)
        out3, self.zi_ma1   = lfilter(self.B_MA1, self.A_MA1, out2, zi=self.zi_ma1)
        out4, self.zi_diff  = lfilter(self.B_DIFF, self.A_DIFF, out3, zi=self.zi_diff)
        out_sq = out4**2
        out_mwi, self.zi_ma2 = lfilter(self.B_MA2, self.A_MA2, out_sq, zi=self.zi_ma2)

        # 更新 buffer
        self.sig_buf.extend(out3)
        self.mwi_buf.extend(out_mwi)

        # baseline 更新
        self.signal_mean = 0.99*self.signal_mean + 0.01*np.mean(out3)

        # ==== PEAK DETECTION ====
        new_bpm = self._detect_peak(out_mwi)
        if new_bpm is not None:
            self.bpm = new_bpm

        return self.bpm, out3   # 回傳：BPM 與 濾波後訊號

    # ----------------------
    def _detect_peak(self, mwi_batch):

        new_bpm = None
        for i in range(len(mwi_batch)):

            abs_idx = self.sample_counter + i
            buf = list(self.mwi_buf)

            # 動態 threshold
            if abs_idx % 50 == 0:
                recent = buf[-self.fs:]
                if recent:
                    self.threshold = 0.5 * max(recent)
                    if self.threshold < 20:
                        self.threshold = 20

            # 三點 peak 檢查
            if abs_idx < 2:
                continue

            prev = buf[-(len(mwi_batch)-i+1)]
            curr = buf[-(len(mwi_batch)-i)]
            nextv = buf[-(len(mwi_batch)-i-1)]

            if curr > self.threshold and curr > prev and curr > nextv:

                if (abs_idx - self.last_peak) > self.REFRACTORY:

                    # 在原始訊號上回推找 local max
                    buf_sig = list(self.sig_buf)
                    start = -len(mwi_batch) + i - self.SEARCH_WIN
                    end   = -len(mwi_batch) + i
                    search_region = buf_sig[start:end]

                    if len(search_region) > 0:
                        local_max = max(search_region)
                        if local_max > self.signal_mean + 20:

                            self.last_peak = abs_idx
                            self.peak_history.append(abs_idx)

                            # 計算 BPM
                            if len(self.peak_history) >= 2:
                                rr = (self.peak_history[-1] - self.peak_history[-2]) / self.fs
                                if 0.4 < rr < 1.5:
                                    self.RR_HISTORY.append(rr)
                                    new_bpm = 60 / np.mean(self.RR_HISTORY)

        self.sample_counter += len(mwi_batch)
        return new_bpm
