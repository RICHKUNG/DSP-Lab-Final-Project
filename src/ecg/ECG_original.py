import serial
import numpy as np
from scipy.signal import lfilter, lfilter_zi, iirnotch, butter
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from collections import deque
import sys
import time  # [新增] 用於計時

# -------- 1. 參數設定 (Settings) --------
COM_PORT = 'COM4'       
BAUD_RATE = 115200       
FS = 500.0               
WIN_SEC = 3              
BUF_LEN = int(FS * WIN_SEC)
DT = 1 / FS

# -------- 進階濾波器設計 (Advanced Filters) --------

# 1. Notch Filter (針對 60Hz 電源雜訊)
# [修改] 降低 Q 值從 30 -> 20，讓頻寬變寬，更容易抓到不穩定的 60Hz
f0 = 60.0  
Q = 20.0  
b_notch, a_notch = iirnotch(f0, Q, FS)

# 2. [新增] Low Pass Filter (強效去除毛邊)
# ECG 有效訊號通常在 40Hz 以下，40Hz 以上大多是肌電雜訊和電源諧波
# 使用 2階 Butterworth，截止頻率 40Hz
def create_lowpass_filter(cutoff, fs, order=2):
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = butter(order, normal_cutoff, btype='low', analog=False)
    return b, a

b_lp, a_lp = create_lowpass_filter(40.0, FS, order=2)

# 3. Pan-Tompkins 原始濾波器
# MA1 (Smoothing)
WINDOW_MA1 = 8
B_MA1 = np.ones(WINDOW_MA1) / WINDOW_MA1
A_MA1 = 1

# Diff (微分)
B_DIFF = np.array([1, -1])
A_DIFF = 1

# MA2 (積分窗口)
WINDOW_MA2 = int(0.150 * FS) 
B_MA2 = np.ones(WINDOW_MA2) / WINDOW_MA2
A_MA2 = 1

# -------- 峰值偵測參數 --------
REFRACTORY_PERIOD = int(0.25 * FS)
SEARCH_WIN = int(0.1 * FS) 
RR_AVG_LEN = 5

# -------- 2. Serial Port 初始化 --------
try:
    ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=0)
    ser.reset_input_buffer()
    print(f"Serial Port {COM_PORT} opened successfully.")
except Exception as e:
    print(f"Error: {e}")
    sys.exit()

# -------- 3. 變數與 Buffer 初始化 --------
raw_buf = deque([0]*BUF_LEN, maxlen=BUF_LEN)
sig_ma1_buf = deque([0]*BUF_LEN, maxlen=BUF_LEN) 
sig_mwi_buf = deque([0]*BUF_LEN, maxlen=BUF_LEN) 

# 濾波器狀態 (zi)
zi_notch = lfilter_zi(b_notch, a_notch) * 0
zi_lp = lfilter_zi(b_lp, a_lp) * 0  # [新增] Low Pass 狀態
zi_ma1 = lfilter_zi(B_MA1, A_MA1) * 0
zi_diff = lfilter_zi(B_DIFF, A_DIFF) * 0
zi_ma2 = lfilter_zi(B_MA2, A_MA2) * 0

t_axis = np.linspace(0, WIN_SEC, BUF_LEN)

sample_counter = 0              
last_peak_abs_idx = -REFRACTORY_PERIOD
peak_indices_history = []       
rr_history = deque(maxlen=RR_AVG_LEN)

threshold_mwi = 50 
signal_mean = 120 
signal_std = 10   

# [新增] 效能計時變數
loop_counter = 0
start_time = time.time()
PERF_REPORT_INTERVAL = 100 # 每 100 loops 印出一次

# -------- 4. 繪圖物件初始化 --------
fig, ax = plt.subplots(figsize=(10, 6))
fig.canvas.manager.set_window_title('Optimized ECG (Notch + LowPass + PT)')

hECG, = ax.plot(t_axis, [0]*BUF_LEN, 'b', linewidth=1.2, label='Filtered ECG')
hPeak, = ax.plot([], [], 'ro', markersize=8, markeredgewidth=2, zorder=10)
hTextBPM = ax.text(0.02, 0.9, 'BPM: --', transform=ax.transAxes, fontsize=14, color='r', fontweight='bold')
# [新增] 用於顯示濾波器資訊
ax.text(0.02, 0.85, 'Filter: 60Hz Notch + 40Hz LP', transform=ax.transAxes, fontsize=10, color='blue')

ax.set_title('Real-time ECG Monitor')
ax.set_xlabel('Time (s)')
ax.set_ylabel('Amplitude')
ax.grid(True)
ax.set_xlim(0, WIN_SEC)
ax.set_ylim(0, 255) 

# -------- 5. 核心處理邏輯 --------
def update_plot(frame):
    global zi_notch, zi_lp, zi_ma1, zi_diff, zi_ma2, sample_counter, last_peak_abs_idx
    global peak_indices_history, rr_history, threshold_mwi, signal_mean, signal_std
    global loop_counter, start_time

    # --- [新增] 效能監控計時器 ---
    loop_counter += 1
    if loop_counter >= PERF_REPORT_INTERVAL:
        elapsed = time.time() - start_time
        avg_time = (elapsed / PERF_REPORT_INTERVAL) * 1000 # 轉毫秒
        print(f"[Performance] Avg time per loop: {avg_time:.2f} ms")
        loop_counter = 0
        start_time = time.time()
    # ---------------------------

    bytes_to_read = ser.in_waiting
    if bytes_to_read == 0:
        return hECG, hPeak, hTextBPM

    raw_data_str = ser.read(bytes_to_read).decode('utf-8', errors='ignore')
    lines = raw_data_str.split('\n')
    
    new_data = []
    for line in lines:
        line = line.strip()
        if line:
            try:
                val = float(line)
                new_data.append(val)
            except ValueError:
                continue
    
    if not new_data:
        return hECG, hPeak, hTextBPM

    new_data = np.array(new_data)
    
    # === 強化版濾波器鏈 (Filter Chain) ===
    
    # 1. Notch Filter (60Hz 去除)
    out_notch, zi_notch = lfilter(b_notch, a_notch, new_data, zi=zi_notch)

    # 2. [新增] Low Pass Filter (40Hz 熨斗，去除所有高頻毛邊)
    out_lp, zi_lp = lfilter(b_lp, a_lp, out_notch, zi=zi_lp)
    
    # 3. MA1 (Smoothing - Pan Tompkins 原有的)
    # 改用經過 Low Pass 處理過的訊號繼續
    out_ma1, zi_ma1 = lfilter(B_MA1, A_MA1, out_lp, zi=zi_ma1)
    
    # 4. Diff
    out_diff, zi_diff = lfilter(B_DIFF, A_DIFF, out_ma1, zi=zi_diff)
    
    # 5. Square
    out_sq = out_diff ** 2
    
    # 6. MA2 (MWI)
    out_mwi, zi_ma2 = lfilter(B_MA2, A_MA2, out_sq, zi=zi_ma2)

    # 更新 Buffer (顯示 Low Pass + MA1 處理後的乾淨訊號)
    sig_ma1_buf.extend(out_ma1)
    sig_mwi_buf.extend(out_mwi)
    
    # 更新基線 (用於 Amplitude Check)
    if len(out_ma1) > 0:
        batch_mean = np.mean(out_ma1)
        signal_mean = 0.99 * signal_mean + 0.01 * batch_mean

    # === 峰值偵測 ===
    start_idx_in_buffer = len(sig_mwi_buf) - len(out_mwi)

    for i in range(len(out_mwi)):
        curr_abs_idx = sample_counter + i
        buf_idx = -(len(out_mwi) - i) 
        
        if buf_idx > -3: continue 

        curr_mwi_val = sig_mwi_buf[buf_idx]
        prev_mwi_val = sig_mwi_buf[buf_idx-1]
        prev2_mwi_val = sig_mwi_buf[buf_idx-2]

        # 動態閾值
        if curr_abs_idx % 50 == 0:
             recent_mwi = list(sig_mwi_buf)[-int(FS):]
             if recent_mwi:
                 threshold_mwi = 0.5 * max(recent_mwi)
                 if threshold_mwi < 20: threshold_mwi = 20

        # Peak 條件
        if prev_mwi_val > threshold_mwi and prev_mwi_val > curr_mwi_val and prev_mwi_val > prev2_mwi_val:
            
            peak_candidate_abs = curr_abs_idx - 1
            
            if (peak_candidate_abs - last_peak_abs_idx) > REFRACTORY_PERIOD:
                
                # 回推 (在 LowPass 訊號上找)
                search_end = buf_idx - 1 
                search_start = search_end - SEARCH_WIN
                if search_start < -len(sig_ma1_buf): search_start = -len(sig_ma1_buf)
                
                search_data = list(sig_ma1_buf)[search_start:search_end]
                
                if search_data:
                    local_max = np.max(search_data)
                    local_max_idx = np.argmax(search_data)
                    
                    # 振幅檢查
                    amplitude_thresh = signal_mean + 20 
                    
                    if local_max > amplitude_thresh:
                        offset = len(search_data) - local_max_idx
                        real_peak_abs = peak_candidate_abs - offset
                        
                        if (real_peak_abs - last_peak_abs_idx) > REFRACTORY_PERIOD:
                            peak_indices_history.append(real_peak_abs)
                            last_peak_abs_idx = real_peak_abs
                            
                            if len(peak_indices_history) >= 2:
                                prev_peak = peak_indices_history[-2]
                                rr_sec = (real_peak_abs - prev_peak) / FS
                                if 0.4 < rr_sec < 1.5: 
                                    rr_history.append(rr_sec)
                                    bpm = 60 / np.mean(rr_history)
                                    hTextBPM.set_text(f'BPM: {bpm:.1f}')

    sample_counter += len(out_mwi)

    hECG.set_ydata(sig_ma1_buf)

    # 繪製紅點
    window_start_idx = sample_counter - BUF_LEN
    valid_x = []
    valid_y = []
    
    while peak_indices_history and peak_indices_history[0] < window_start_idx - 500:
        peak_indices_history.pop(0)

    for abs_idx in peak_indices_history:
        rel_idx = abs_idx - window_start_idx
        if 0 <= rel_idx < BUF_LEN:
            valid_x.append(t_axis[rel_idx])
            valid_y.append(sig_ma1_buf[rel_idx])
            
    hPeak.set_data(valid_x, valid_y)

    return hECG, hPeak, hTextBPM

ani = animation.FuncAnimation(fig, update_plot, interval=30, blit=True, cache_frame_data=False)
plt.show()

if ser.is_open:
    ser.close()