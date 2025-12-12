"""
Test ECGAdapter with fallback mechanism
"""
import sys
import time
sys.path.insert(0, 'C:/Users/user/Desktop/DSPLab/Final')

from src.ecg.adapter import ECGAdapter
from src.event_bus import EventBus, EventType

# Create event bus
event_bus = EventBus()
event_bus.start()

# Track events
peak_count = 0
bpm_updates = []

def on_peak(event):
    global peak_count
    peak_count += 1
    print(f"[PEAK #{peak_count}] BPM={event.data['bpm']:.1f}, Dir={event.data['dir']}")

def on_bpm(event):
    bpm_updates.append(event.data['bpm'])
    print(f"[BPM UPDATE] {event.data['bpm']:.1f}")

event_bus.subscribe(EventType.ECG_PEAK, on_peak)
event_bus.subscribe(EventType.ECG_BPM_UPDATE, on_bpm)

# Create adapter (will use fallback since no hardware)
print("Creating ECG Adapter...")
adapter = ECGAdapter(
    event_bus=event_bus,
    bpm_threshold=40.0,
    fallback_bpm=75.0,
    no_signal_timeout=2.0
)

print("Starting adapter...")
adapter.start()

print("Running for 10 seconds...")
time.sleep(10)

print(f"\nTotal peaks: {peak_count}")
print(f"Average BPM: {sum(bpm_updates)/len(bpm_updates) if bpm_updates else 0:.1f}")

adapter.stop()
event_bus.stop()
