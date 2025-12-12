"""
Debug ECG peak detection - log all potential peaks
"""
import sys
import time
sys.path.insert(0, 'C:/Users/user/Desktop/DSPLab/Final')

from src.ecg.manager import ECGManager

# Monkey patch the _detect_peak method to add logging
original_detect_peak = ECGManager._detect_peak

def debug_detect_peak(self):
    # Check if we have enough samples
    if self.sample_counter < 3:
        return False, 0.0, self.bpm
    # Check refractory
    in_refractory = (self.sample_counter - self.last_peak_counter) <= self.refractory_samples

    # Get MWI values
    mwi_buf = list(self.mwi_history)
    if len(mwi_buf) < 3:
        return False, 0.0, self.bpm

    prev = mwi_buf[-3]
    curr = mwi_buf[-2]
    nextv = mwi_buf[-1]

    is_local_max = curr > prev and curr > nextv
    above_threshold = curr > self.threshold

    # Log potential peaks
    if is_local_max and above_threshold and not in_refractory:
        print(f"[{self.sample_counter:5d}] CANDIDATE: MWI={curr:.1f}, prev={prev:.1f}, next={nextv:.1f}, thresh={self.threshold:.1f}")

    return original_detect_peak(self)

ECGManager._detect_peak = debug_detect_peak

# Create and run
manager = ECGManager(simulate=True)

peak_count = 0
def count_callback(data):
    global peak_count
    if data['is_peak']:
        peak_count += 1

manager.set_data_callback(count_callback)
manager.start()

print("Running for 10 seconds with debug logging...")
time.sleep(10)

print(f"\nTotal peaks: {peak_count}")
manager.stop()
