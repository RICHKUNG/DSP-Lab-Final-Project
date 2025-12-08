"""Simulated live test using file input instead of microphone."""

import sys
import os
import time
import numpy as np
import queue
import threading
import glob

# Ensure src is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.audio_io import load_audio_file
from src.vad import VAD, VADState
from src.recognizers import MultiMethodMatcher
from src import config

class FileAudioStream:
    """Mock AudioStream that plays files."""
    def __init__(self, audio_data, chunk_size=512):
        self.audio = audio_data
        self.chunk_size = chunk_size
        self._output_queue = queue.Queue()
        self._running = False
        self._ptr = 0
        self._thread = None
        self._background_rms = 50.0
    
    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run)
        self._thread.start()
        
    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join()
            
    def _run(self):
        while self._running:
            if self._ptr + self.chunk_size > len(self.audio):
                print("\n[End of file loop, restarting in 2 seconds...]")
                time.sleep(2.0)
                self._ptr = 0
                continue
                
            chunk = self.audio[self._ptr : self._ptr + self.chunk_size]
            self._output_queue.put(chunk)
            self._ptr += self.chunk_size
            
            # Simulate real-time delay
            time.sleep(self.chunk_size / config.SAMPLE_RATE)
            
    def get_chunk(self, timeout=0.1):
        try:
            return self._output_queue.get(timeout=timeout)
        except queue.Empty:
            return np.array([], dtype=np.int16)
            
    def measure_background(self, duration_ms):
        return 50.0

    @property
    def background_rms(self):
        return 50.0

def test_file_simulation():
    print("=" * 70)
    print("Bio-Voice Commander - File Simulation Test")
    print("=" * 70)

    # 1. Load Templates
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    matcher = MultiMethodMatcher()
    print("Loading templates from:", base_dir)
    matcher.load_templates_from_dir(base_dir)

    # 2. Prepare Input Audio (Concatenate all templates with silence)
    print("\nPreparing input audio from templates...")
    input_audio = np.array([], dtype=np.int16)
    silence = np.zeros(int(config.SAMPLE_RATE * 1.0), dtype=np.int16) # 1 sec silence
    
    # Find files
    template_files = glob.glob(os.path.join(base_dir, "cmd_templates", "*.*"))
    for f in template_files:
        print(f"  Adding {os.path.basename(f)}")
        try:
            data = load_audio_file(f)
            # Add silence before and after
            input_audio = np.concatenate((input_audio, silence, data, silence))
        except Exception as e:
            print(f"    Error loading {f}: {e}")

    if len(input_audio) == 0:
        print("[ERROR] No audio data loaded.")
        return

    print(f"\nTotal simulation duration: {len(input_audio)/config.SAMPLE_RATE:.1f}s")

    # 3. Start Stream
    audio_stream = FileAudioStream(input_audio)
    audio_stream.start()
    
    # 4. Initialize VAD
    vad = VAD(background_rms=50.0)
    
    print("\n" + "=" * 70)
    print("Simulating live input...")
    print("=" * 70)

    stats = {
        'total_detections': 0,
        'successful_matches': 0,
        'processing_times': [],
        'vad_times': []
    }
    vad_start_time = None

    try:
        start_wall_time = time.time()
        while True:
            # Stop after one full loop roughly
            # if time.time() - start_wall_time > (len(input_audio)/config.SAMPLE_RATE) + 5:
            #     break

            chunk = audio_stream.get_chunk(timeout=0.1)
            if len(chunk) == 0:
                continue

            state, segment = vad.process_chunk(chunk)

            if state == VADState.RECORDING and vad_start_time is None:
                vad_start_time = time.time()

            if state == VADState.PROCESSING and segment is not None:
                vad_time = (time.time() - vad_start_time) * 1000 if vad_start_time else 0
                stats['vad_times'].append(vad_time)
                stats['total_detections'] += 1
                
                print(f"\n[Detection #{stats['total_detections']}]")
                
                # Recognize
                t0 = time.time()
                result = matcher.recognize(segment, mode='all')
                proc_time = (time.time() - t0) * 1000
                stats['processing_times'].append(proc_time)
                
                # Print Result
                has_match = False
                for method, res in result['all_results'].items():
                    cmd = res['command']
                    if cmd != 'NONE':
                        print(f"  {method:12s}: {cmd:8s} (dist={res['distance']:.1f}) ✓")
                        has_match = True
                    else:
                        print(f"  {method:12s}: NONE     (dist={res['distance']:.1f}) ✗")
                
                if has_match:
                    stats['successful_matches'] += 1
                
                print("-" * 50)
                
                vad.reset()
                vad_start_time = None

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        audio_stream.stop()

if __name__ == '__main__':
    test_file_simulation()
