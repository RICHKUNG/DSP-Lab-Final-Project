"""
Test ECGAdapter dynamic switching between real ECG and fallback
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
mode_switches = []
last_mode = None

def on_peak(event):
    global peak_count, last_mode
    peak_count += 1
    bpm = event.data['bpm']

    # Detect mode based on BPM
    current_mode = "fallback" if abs(bpm - 75.0) < 1.0 else "real"

    if last_mode and current_mode != last_mode:
        mode_switches.append({
            'time': time.time(),
            'from': last_mode,
            'to': current_mode,
            'peak_num': peak_count
        })
        print(f"\n[MODE SWITCH] {last_mode} → {current_mode} (peak #{peak_count})\n")

    last_mode = current_mode
    print(f"[PEAK #{peak_count}] BPM={bpm:.1f} (mode: {current_mode})")

event_bus.subscribe(EventType.ECG_PEAK, on_peak)

# Create adapter with short retry interval for testing
print("Creating ECG Adapter with 5s retry interval...")
adapter = ECGAdapter(
    event_bus=event_bus,
    bpm_threshold=-10.0,      # Very low, won't trigger on BPM
    bpm_recovery=50.0,
    fallback_bpm=75.0,
    no_signal_timeout=3.0,    # 3s timeout
    retry_interval=5.0        # Retry every 5s
)

print("Starting adapter...")
start_time = time.time()
adapter.start()

print("\nMonitoring for 30 seconds to observe dynamic switching...")
print("(Real ECG will timeout → fallback → retry → repeat)\n")

try:
    time.sleep(30)
except KeyboardInterrupt:
    print("\n\nInterrupted by user")

elapsed = time.time() - start_time
print(f"\n{'='*60}")
print(f"Test Summary ({elapsed:.1f}s)")
print(f"{'='*60}")
print(f"Total peaks: {peak_count}")
print(f"Mode switches: {len(mode_switches)}")

if mode_switches:
    print(f"\nSwitch timeline:")
    for i, sw in enumerate(mode_switches, 1):
        print(f"  {i}. {sw['from']} → {sw['to']} at peak #{sw['peak_num']}")
else:
    print("\nNo mode switches detected (stayed in one mode)")

adapter.stop()
event_bus.stop()
