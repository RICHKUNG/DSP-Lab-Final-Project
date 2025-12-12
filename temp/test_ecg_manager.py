"""
Test ECG Manager to debug peak detection
"""
import sys
import time
sys.path.insert(0, 'C:/Users/user/Desktop/DSPLab/Final')

from src.ecg.manager import ECGManager

# Create manager in simulation mode
print("Creating ECG Manager in simulation mode...")
manager = ECGManager(simulate=True)

# Add debug callback
peak_count = 0
def debug_callback(data):
    global peak_count
    if data['is_peak']:
        peak_count += 1
        print(f"[PEAK #{peak_count}] BPM: {data['bpm']:.1f}, Amplitude: {data['amplitude']:.1f}, MWI: {data['mwi']:.2f}")

manager.set_data_callback(debug_callback)

print("Starting manager...")
manager.start()

print("Running for 10 seconds...")
time.sleep(10)

print(f"\nTotal peaks detected: {peak_count}")
print(f"Expected peaks (75 BPM): ~{75 * 10 / 60:.1f}")

manager.stop()
