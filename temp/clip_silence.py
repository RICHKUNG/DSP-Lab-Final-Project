"""
Clip silence from the beginning of audio files in cmd_templates
and save them to new_templates directory.
"""

import os
import numpy as np
import librosa
import soundfile as sf
from pathlib import Path

def detect_speech_start(audio, sample_rate, energy_threshold_mult=2.0, window_ms=20):
    """
    Detect the start of speech by finding where energy exceeds threshold.

    Args:
        audio: Audio signal (numpy array)
        sample_rate: Sample rate in Hz
        energy_threshold_mult: Multiplier for energy threshold (relative to background)
        window_ms: Window size in milliseconds for energy calculation

    Returns:
        Index where speech starts
    """
    # Calculate window size in samples
    window_size = int(sample_rate * window_ms / 1000)

    # Calculate energy for each window
    energies = []
    for i in range(0, len(audio) - window_size, window_size // 2):
        window = audio[i:i + window_size]
        energy = np.sum(window.astype(np.float64) ** 2)
        energies.append(energy)

    if len(energies) == 0:
        return 0

    energies = np.array(energies)

    # Use first few windows to estimate background noise
    background_windows = min(5, len(energies) // 4)
    if background_windows < 1:
        background_windows = 1

    background_energy = np.mean(energies[:background_windows])
    threshold = background_energy * energy_threshold_mult

    # Find first window that exceeds threshold
    for i, energy in enumerate(energies):
        if energy > threshold:
            # Convert window index back to sample index
            # Subtract one window to include a bit of lead-in
            start_window = max(0, i - 1)
            return start_window * (window_size // 2)

    # If no speech detected, return 0 (keep entire audio)
    return 0

def clip_audio_file(input_path, output_path, top_db=30, frame_length=512, hop_length=128):
    """
    Load audio file, clip silence from beginning, and save to output path.

    Args:
        input_path: Path to input audio file
        output_path: Path to output audio file
        top_db: Threshold in dB below reference to consider as silence (lower = more aggressive)
        frame_length: Frame length for energy calculation
        hop_length: Hop length for energy calculation
    """
    # Read audio file using librosa (more robust than scipy)
    audio, sample_rate = librosa.load(input_path, sr=None, mono=True)

    original_length = len(audio)

    # Use librosa's trim function to remove silence from beginning and end
    # top_db: The threshold (in decibels) below reference to consider as silence
    # Lower values = more aggressive trimming
    trimmed_audio, index = librosa.effects.trim(
        audio,
        top_db=top_db,
        frame_length=frame_length,
        hop_length=hop_length
    )

    # Only trim from the beginning (keep the original end)
    # index[0] is where the non-silent portion starts
    clipped_audio = audio[index[0]:]

    # Save clipped audio
    sf.write(output_path, clipped_audio, sample_rate)

    # Calculate and return statistics
    duration_removed = index[0] / sample_rate
    return duration_removed

def main():
    # Setup paths
    base_dir = Path(__file__).resolve().parent.parent
    input_dir = base_dir / "cmd_templates"
    output_dir = base_dir / "new_templates"

    # Create output directory if it doesn't exist
    output_dir.mkdir(exist_ok=True)

    # Get all wav files in input directory
    wav_files = list(input_dir.glob("*.wav"))

    if not wav_files:
        print(f"No .wav files found in {input_dir}")
        return

    print(f"Found {len(wav_files)} audio files")
    print(f"Processing files from: {input_dir}")
    print(f"Saving to: {output_dir}\n")

    # Process each file
    # top_db: lower value = more aggressive trimming (20-25 is quite aggressive)
    total_removed = 0
    for wav_file in wav_files:
        try:
            output_path = output_dir / wav_file.name
            duration_removed = clip_audio_file(
                wav_file,
                output_path,
                top_db=25,  # More aggressive threshold
                frame_length=512,
                hop_length=128
            )
            total_removed += duration_removed

            print(f"[OK] {wav_file.name:20s} - Removed {duration_removed:.3f}s of silence")
        except Exception as e:
            print(f"[ERR] {wav_file.name:20s} - Error: {e}")

    print(f"\n{'='*60}")
    print(f"Processing complete!")
    print(f"Total files processed: {len(wav_files)}")
    print(f"Total silence removed: {total_removed:.3f}s")
    print(f"Output directory: {output_dir}")

if __name__ == "__main__":
    main()
