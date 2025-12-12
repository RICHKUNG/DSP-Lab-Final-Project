"""Real-time audio visualization debug tool - MFCC and Spectrogram display."""

import sys
import os
import time
import argparse
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from collections import deque
import threading

# Ensure the project root is in the Python path for module imports
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_current_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.audio.io import AudioStream, find_suitable_device
from src.audio.vad import VAD, VADState
from src.audio.features import extract_mfcc, extract_mel_template
from src import config


class AudioVisualizer:
    """Real-time audio visualization with MFCC and Spectrogram."""

    def __init__(self, audio_stream, mode='spectrogram', buffer_duration=3.0):
        """
        Initialize the visualizer.

        Args:
            audio_stream: AudioStream instance
            mode: 'mfcc', 'spectrogram', or 'both'
            buffer_duration: Duration of audio to display (seconds)
        """
        self.audio_stream = audio_stream
        self.mode = mode
        self.buffer_duration = buffer_duration
        self.buffer_samples = int(config.SAMPLE_RATE * buffer_duration)

        # Audio buffer
        self.audio_buffer = deque(maxlen=self.buffer_samples)

        # VAD for segmentation (optional)
        self.vad = None
        self.use_vad = False

        # Lock for thread safety
        self.lock = threading.Lock()

        # Setup matplotlib
        self.fig = None
        self.ax_spec = None
        self.ax_mfcc = None
        self.ax_waveform = None
        self.im_spec = None
        self.im_mfcc = None
        self.line_wave = None

        self._setup_plot()

    def _setup_plot(self):
        """Setup matplotlib figure and axes."""
        if self.mode == 'both':
            self.fig, (self.ax_waveform, self.ax_spec, self.ax_mfcc) = plt.subplots(
                3, 1, figsize=(12, 10)
            )
        elif self.mode == 'spectrogram':
            self.fig, (self.ax_waveform, self.ax_spec) = plt.subplots(
                2, 1, figsize=(12, 8)
            )
        elif self.mode == 'mfcc':
            self.fig, (self.ax_waveform, self.ax_mfcc) = plt.subplots(
                2, 1, figsize=(12, 8)
            )
        else:
            raise ValueError(f"Unknown mode: {self.mode}")

        self.fig.suptitle('Real-Time Audio Visualization', fontsize=16, fontweight='bold')

        # Waveform plot
        self.ax_waveform.set_title('Waveform')
        self.ax_waveform.set_xlabel('Time (s)')
        self.ax_waveform.set_ylabel('Amplitude')
        self.ax_waveform.set_ylim(-32768, 32768)
        self.line_wave, = self.ax_waveform.plot([], [], 'b-', linewidth=0.5)

        # Spectrogram plot
        if self.ax_spec is not None:
            self.ax_spec.set_title('Mel-Spectrogram (dB)')
            self.ax_spec.set_xlabel('Time (frames)')
            self.ax_spec.set_ylabel('Mel Frequency Bins')
            # Initialize with empty image
            self.im_spec = self.ax_spec.imshow(
                np.zeros((config.N_MELS, 100)),
                aspect='auto',
                origin='lower',
                cmap='viridis',
                interpolation='nearest'
            )
            self.fig.colorbar(self.im_spec, ax=self.ax_spec, label='dB')

        # MFCC plot
        if self.ax_mfcc is not None:
            self.ax_mfcc.set_title('MFCC Features (with Delta & Delta-Delta)')
            self.ax_mfcc.set_xlabel('Time (frames)')
            self.ax_mfcc.set_ylabel('MFCC Coefficients')
            # Initialize with empty image
            n_mfcc_total = config.N_MFCC * 3  # MFCC + Delta + Delta-Delta
            self.im_mfcc = self.ax_mfcc.imshow(
                np.zeros((n_mfcc_total, 100)),
                aspect='auto',
                origin='lower',
                cmap='coolwarm',
                interpolation='nearest'
            )
            self.fig.colorbar(self.im_mfcc, ax=self.ax_mfcc, label='Coefficient Value')

        plt.tight_layout()

    def enable_vad(self, background_rms):
        """Enable VAD for segmentation markers."""
        self.vad = VAD(background_rms=background_rms)
        self.use_vad = True

    def _collect_audio(self):
        """Background thread to collect audio."""
        while self.running:
            chunk = self.audio_stream.get_chunk(timeout=0.01)
            if len(chunk) > 0:
                with self.lock:
                    self.audio_buffer.extend(chunk)

    def _process_audio(self):
        """Process current audio buffer and extract features."""
        with self.lock:
            if len(self.audio_buffer) < config.SAMPLE_RATE // 10:  # At least 100ms
                return None, None, None

            audio = np.array(list(self.audio_buffer), dtype=np.int16)

        # Convert to float32 for processing
        audio_float = audio.astype(np.float32) / 32768.0

        # Extract features
        mel_spec = None
        mfcc = None

        if self.mode in ['spectrogram', 'both']:
            # Compute mel spectrogram
            import librosa
            mel = librosa.feature.melspectrogram(
                y=audio_float,
                sr=config.SAMPLE_RATE,
                n_mels=config.N_MELS,
                n_fft=config.N_FFT,
                hop_length=config.HOP_LENGTH,
                fmin=config.FMIN,
                fmax=config.FMAX
            )
            # Convert to dB
            mel_spec = librosa.power_to_db(mel, ref=np.max)

        if self.mode in ['mfcc', 'both']:
            # Extract MFCC with deltas
            mfcc = extract_mfcc(audio_float, include_delta=True)
            # Transpose to (n_features, n_frames) for display
            mfcc = mfcc.T

        return audio, mel_spec, mfcc

    def _update_plot(self, frame):
        """Update plot callback for animation."""
        audio, mel_spec, mfcc = self._process_audio()

        if audio is None:
            return []

        artists = []

        # Update waveform
        time_axis = np.arange(len(audio)) / config.SAMPLE_RATE
        self.line_wave.set_data(time_axis, audio)
        self.ax_waveform.set_xlim(0, len(audio) / config.SAMPLE_RATE)
        artists.append(self.line_wave)

        # Update spectrogram
        if mel_spec is not None:
            self.im_spec.set_data(mel_spec)
            self.im_spec.set_extent([0, mel_spec.shape[1], 0, config.N_MELS])
            # Auto-adjust color scale
            vmin, vmax = np.percentile(mel_spec, [5, 95])
            self.im_spec.set_clim(vmin, vmax)
            artists.append(self.im_spec)

        # Update MFCC
        if mfcc is not None:
            self.im_mfcc.set_data(mfcc)
            self.im_mfcc.set_extent([0, mfcc.shape[1], 0, mfcc.shape[0]])
            # Auto-adjust color scale
            vmin, vmax = np.percentile(mfcc, [5, 95])
            self.im_mfcc.set_clim(vmin, vmax)
            artists.append(self.im_mfcc)

        return artists

    def run(self):
        """Start the visualizer."""
        self.running = True

        # Start audio collection thread
        self.collector_thread = threading.Thread(target=self._collect_audio, daemon=True)
        self.collector_thread.start()

        # Setup animation
        self.ani = FuncAnimation(
            self.fig,
            self._update_plot,
            interval=50,  # Update every 50ms
            blit=True,
            cache_frame_data=False
        )

        plt.show()

        # Stop when window is closed
        self.running = False


def main():
    """Main entry point."""
    print("=" * 80)
    print("Real-Time Audio Visualization Debug Tool")
    print("=" * 80)

    # Parse arguments
    parser = argparse.ArgumentParser(description="Real-time audio visualization for debugging.")
    parser.add_argument(
        "--mode",
        type=str,
        choices=['mfcc', 'spectrogram', 'both'],
        default='both',
        help="Visualization mode: 'mfcc', 'spectrogram', or 'both' (default: both)"
    )
    parser.add_argument(
        "--device-index",
        type=int,
        help="Specify the input audio device index to use. Skips automatic detection."
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=3.0,
        help="Duration of audio buffer to display in seconds (default: 3.0)"
    )
    parser.add_argument(
        "--use-vad",
        action="store_true",
        help="Enable VAD for segmentation visualization (experimental)"
    )
    args = parser.parse_args()

    # Find audio device
    print("\n" + "=" * 80)
    print("Finding suitable audio device...")
    device_info = find_suitable_device(
        config.SAMPLE_RATE,
        verbose=True,
        preferred_device_index=args.device_index
    )

    if device_info is None:
        print("[ERROR] Cannot access any audio input device!")
        print("\nThis is likely a Windows permissions issue or exclusive mode issue.")
        print("\nQuick fix:")
        print("  1. Go to Settings > Privacy & Security > Microphone")
        print("  2. Enable 'Let apps access your microphone'")
        print("  3. Enable 'Let desktop apps access your microphone'")
        print("  4. In Sound Settings -> Recording tab -> Device Properties -> Advanced Tab,")
        print("     uncheck 'Allow applications to take exclusive control of this device'.")
        return

    device_index, device_rate = device_info
    print(f"Using audio device index: {device_index}")
    if device_rate != config.SAMPLE_RATE:
        print(f"Device native rate: {device_rate} Hz (will resample to {config.SAMPLE_RATE} Hz)")

    # Start audio stream
    print("\nStarting audio stream...")
    audio_stream = AudioStream(
        device_index=device_index,
        input_rate=device_rate,
        target_rate=config.SAMPLE_RATE,
    )
    audio_stream.start()

    # Calibrate VAD if requested
    bg_rms = None
    if args.use_vad:
        print("\n" + "-" * 80)
        print("VAD Calibration - Please stay QUIET for 2 seconds")
        print("-" * 80)
        time.sleep(0.3)
        bg_rms = audio_stream.measure_background(1500)
        print(f"Background RMS: {bg_rms:.1f}")

    # Create visualizer
    print("\n" + "=" * 80)
    print(f"Starting visualization (mode: {args.mode.upper()})...")
    print("Close the plot window to stop.")
    print("=" * 80)
    print()

    try:
        visualizer = AudioVisualizer(
            audio_stream=audio_stream,
            mode=args.mode,
            buffer_duration=args.duration
        )

        if args.use_vad and bg_rms is not None:
            visualizer.enable_vad(bg_rms)

        visualizer.run()

    except KeyboardInterrupt:
        print("\n\nStopping...")
    finally:
        audio_stream.stop()
        print("Stream stopped. Goodbye!")


if __name__ == '__main__':
    main()
