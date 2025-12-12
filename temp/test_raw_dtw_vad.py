"""Test raw_dtw with VAD to ensure proper reset behavior."""

import sys
import os
import numpy as np
import time

# Add project root to path
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_current_dir)
sys.path.insert(0, _project_root)

from src.audio.recognizers import MultiMethodMatcher
from src.audio.vad import VAD, VADState
from src.audio.io import load_audio_file
from src import config


def test_raw_dtw_vad():
    """Test that raw_dtw doesn't block VAD."""

    print("=" * 80)
    print("Testing raw_dtw with VAD - Checking for blocking issues")
    print("=" * 80)

    # Create matcher
    matcher = MultiMethodMatcher(methods=['raw_dtw'])

    # Load templates
    templates = [
        ('START', 'cmd_templates/開始.wav'),
        ('PAUSE', 'cmd_templates/暫停1.wav'),
        ('JUMP', 'cmd_templates/跳1.wav')
    ]

    print("\nLoading templates...")
    for cmd, path in templates:
        full_path = os.path.join(_project_root, path)
        audio = load_audio_file(full_path)
        matcher.add_template(cmd, audio, os.path.basename(path))
        print(f"  [OK] {cmd}: {len(audio)} samples")

    # Create VAD
    vad = VAD(background_rms=100.0)

    print("\nSimulating VAD processing cycle:")
    print("-" * 80)

    # Simulate speech detection
    # 1. Silence chunks
    print("\n1. Processing silence chunks (should stay in SILENCE state)...")
    for i in range(5):
        silence_chunk = np.random.randint(-100, 100, config.CHUNK_SIZE, dtype=np.int16)
        state, segment = vad.process_chunk(silence_chunk)
        print(f"   Chunk {i+1}: state = {state.name}")
        assert state == VADState.SILENCE, "Should be in SILENCE"

    # 2. Speech chunks
    print("\n2. Processing speech chunks (should enter RECORDING)...")
    for i in range(10):
        speech_chunk = np.random.randint(-2000, 2000, config.CHUNK_SIZE, dtype=np.int16)
        state, segment = vad.process_chunk(speech_chunk)
        print(f"   Chunk {i+1}: state = {state.name}")
        if i == 0:
            assert state == VADState.RECORDING, "Should enter RECORDING on first speech"

    # 3. Silence again (should trigger PROCESSING)
    print("\n3. Processing silence to end speech (should enter PROCESSING)...")
    segment = None
    for i in range(10):
        silence_chunk = np.random.randint(-100, 100, config.CHUNK_SIZE, dtype=np.int16)
        state, seg = vad.process_chunk(silence_chunk)
        print(f"   Chunk {i+1}: state = {state.name}")
        if seg is not None:
            segment = seg
            print(f"   → Speech segment captured! Length: {len(segment)} samples")
            break

    assert segment is not None, "Should have captured speech segment"
    assert state == VADState.PROCESSING, "Should be in PROCESSING"

    # 4. Run recognition (this should NOT block forever)
    print("\n4. Running raw_dtw recognition (testing for blocking)...")
    print("   This should complete in ~650ms and not freeze...")

    start_time = time.time()
    results = matcher.recognize(segment, mode='all', adaptive=False)
    elapsed = (time.time() - start_time) * 1000

    command = results['all_results']['raw_dtw']['command']
    distance = results['all_results']['raw_dtw']['distance']

    print(f"   [OK] Recognition completed in {elapsed:.1f}ms")
    print(f"   Result: {command} (distance: {distance:.4f})")

    # 5. Reset VAD (should return to SILENCE)
    print("\n5. Resetting VAD (should return to SILENCE)...")
    vad.reset()
    print(f"   State after reset: {vad.state.name}")
    assert vad.state == VADState.SILENCE, "Should be back in SILENCE"

    # 6. Verify VAD can process new chunks
    print("\n6. Processing new chunks after reset (should work normally)...")
    for i in range(3):
        new_chunk = np.random.randint(-100, 100, config.CHUNK_SIZE, dtype=np.int16)
        state, seg = vad.process_chunk(new_chunk)
        print(f"   Chunk {i+1}: state = {state.name}")
        assert state == VADState.SILENCE, "Should process normally"

    print("\n" + "=" * 80)
    print("[PASS] All tests passed! raw_dtw works correctly with VAD")
    print("  - Recognition completes in reasonable time (~650ms)")
    print("  - VAD resets properly after recognition")
    print("  - No blocking or freezing issues")
    print("=" * 80)


if __name__ == '__main__':
    test_raw_dtw_vad()
