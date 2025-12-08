"""Simulated live test using file input instead of microphone."""

import sys
import os
import time
import numpy as np
import queue
import threading
import glob
from collections import deque

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
                # End of audio
                self._running = False
                break
                
            chunk = self.audio[self._ptr : self._ptr + self.chunk_size]
            self._output_queue.put(chunk)
            self._ptr += self.chunk_size
            
            # Simulate real-time delay (fast forward 2x for testing speed)
            time.sleep((self.chunk_size / config.SAMPLE_RATE) * 0.5)
            
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

def get_expected_label(filename):
    fname = os.path.basename(filename)
    for cn, en in config.COMMAND_MAPPING.items():
        if cn in fname:
            return en
    return "UNKNOWN"

def test_file_simulation():
    print("=" * 70)
    print("Bio-Voice Commander - File Simulation Test")
    print("=" * 70)

    # 1. Load Templates
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    matcher = MultiMethodMatcher()
    print("Loading templates from:", base_dir)
    matcher.load_templates_from_dir(base_dir)

    # 2. Prepare Input Audio
    print("\nPreparing input audio from templates...")
    input_audio = np.array([], dtype=np.int16)
    # 1 second silence
    silence = np.zeros(int(config.SAMPLE_RATE * 1.0), dtype=np.int16)
    
    # Sort files to ensure deterministic order
    template_files = sorted(glob.glob(os.path.join(base_dir, "cmd_templates", "*.*" )))
    
    expected_sequence = []
    
    # Add silence at start
    input_audio = np.concatenate((input_audio, silence))

    for f in template_files:
        label = get_expected_label(f)
        print(f"  Adding {os.path.basename(f)} -> Expecting: {label}")
        try:
            data = load_audio_file(f)
            # Add to sequence
            expected_sequence.append({'label': label, 'start_sample': len(input_audio)})
            
            input_audio = np.concatenate((input_audio, data, silence))
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
        'processing_times': []
    }
    vad_start_time = None
    
    # Pointer to track which expected command we are near
    current_sample_idx = 0
    
    try:
        while True:
            chunk = audio_stream.get_chunk(timeout=0.5)
            if len(chunk) == 0:
                print("End of stream.")
                break
                
            current_sample_idx += len(chunk)

            state, segment = vad.process_chunk(chunk)

            if state == VADState.RECORDING and vad_start_time is None:
                vad_start_time = time.time()

            if state == VADState.PROCESSING and segment is not None:
                stats['total_detections'] += 1
                
                # Determine what we *should* have heard based on timing
                # This is approximate because VAD trims silence
                # Just popping the next expected command for simplicity
                expected = "???"
                if len(expected_sequence) > 0:
                    expected = expected_sequence.pop(0)['label']

                print(f"\n[Detection #{stats['total_detections']}] Expected: {expected}")
                
                # Recognize
                t0 = time.time()
                raw_results = matcher.recognize(segment, mode='all') # Get all individual results
                proc_time = (time.time() - t0) * 1000
                stats['processing_times'].append(proc_time)
                
                # Compute ensemble decision manually
                best_command = 'NONE'
                best_confidence = 0.0
                best_method = None
                
                for method, res in raw_results['all_results'].items():
                    cmd = res['command']
                    dist = res['distance']
                    threshold = matcher.matchers[method].threshold # Get matcher to access its threshold
                    
                    if cmd != 'NONE':
                        conf = 1 - min(dist / threshold, 1)
                        if conf > best_confidence:
                            best_confidence = conf
                            best_command = cmd
                            best_method = method

                # Print Result
                has_match = False
                matches = []
                for method, res in raw_results['all_results'].items():
                    cmd = res['command']
                    dist = res['distance']
                    threshold = matcher.matchers[method].threshold
                    
                    mark = "✗"
                    if cmd != 'NONE':
                        mark = "✓"
                        if cmd == expected:
                            mark = "✓✓ (Correct)"
                        else:
                            mark = "✓? (Wrong Cmd)"
                        matches.append(method)
                    
                    print(f"  {method:12s}: {cmd:8s} (dist={dist:6.2f}, th={threshold:5.1f}) {mark}")
                
                # Show Ensemble Decision
                print(f"  {'>> DECISION':12s}: {best_command:8s} (conf={best_confidence*100:.0f}%, by {best_method})")

                if best_command != 'NONE' and best_command == expected:
                    print(f"\n  Overall: ✓✓ CORRECT MATCH for {expected}")
                elif best_command != 'NONE' and best_command != expected:
                    print(f"\n  Overall: ✓? WRONG COMMAND! Expected {expected}, got {best_command}")
                else:
                    print(f"\n  Overall: ✗ NO MATCH!")

                print("-" * 60)
                
                vad.reset()
                vad_start_time = None

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        audio_stream.stop()
    
    print(f"\nCompleted. Total Detections: {stats['total_detections']}")

if __name__ == '__main__':
    test_file_simulation()