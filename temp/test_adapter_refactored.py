"""
測試重構後的 ECGAdapter (使用 ECGProcessor)
"""
import sys
import time
sys.path.insert(0, 'C:/Users/user/Desktop/DSPLab/Final')

from src.ecg.adapter import ECGAdapter
from src.event_bus import EventBus, EventType

# 創建 event bus
event_bus = EventBus()
event_bus.start()

# 追蹤事件
peak_count = 0
bpm_updates = []

def on_peak(event):
    global peak_count
    peak_count += 1
    bpm = event.data['bpm']
    print(f"[PEAK #{peak_count}] BPM={bpm:.1f}")

def on_bpm_update(event):
    bpm = event.data['bpm']
    bpm_updates.append(bpm)

event_bus.subscribe(EventType.ECG_PEAK, on_peak)
event_bus.subscribe(EventType.ECG_BPM_UPDATE, on_bpm_update)

# 創建 adapter (會嘗試連接真實 ECG，失敗則用 fallback)
print("Creating ECG Adapter...")
adapter = ECGAdapter(
    event_bus=event_bus,
    bpm_threshold=-10.0,      # 幾乎不會觸發
    bpm_recovery=50.0,
    fallback_bpm=75.0,
    no_signal_timeout=3.0,    # 3s 超時
    retry_interval=10.0       # 10s 重試
)

print("Starting adapter...")
start_time = time.time()
adapter.start()

print("\nMonitoring for 15 seconds...\n")

try:
    time.sleep(15)
except KeyboardInterrupt:
    print("\n\nInterrupted by user")

elapsed = time.time() - start_time

print(f"\n{'='*60}")
print(f"Test Summary ({elapsed:.1f}s)")
print(f"{'='*60}")
print(f"Total peaks: {peak_count}")
print(f"BPM updates: {len(bpm_updates)}")

if bpm_updates:
    avg_bpm = sum(bpm_updates) / len(bpm_updates)
    min_bpm = min(bpm_updates)
    max_bpm = max(bpm_updates)
    print(f"BPM range: {min_bpm:.1f} - {max_bpm:.1f} (avg: {avg_bpm:.1f})")

adapter.stop()
event_bus.stop()

print("\n✓ Test completed successfully!")
