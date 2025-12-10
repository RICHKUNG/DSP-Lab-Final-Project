"""Global configuration for Bio-Voice Commander."""

import os
from pathlib import Path

# Path settings
# Resolve the project root relative to this config file (src/config.py -> src/ -> root)
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = BASE_DIR / "cmd_templates"

# Audio settings
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SIZE = 512  # ~32ms at 16kHz
DTYPE = 'int16'

# VAD settings
# --- Default (Quiet/Normal Environment) ---
VAD_ENERGY_THRESHOLD_MULT_LOW = 2.0
VAD_ENERGY_THRESHOLD_MULT_HIGH = 5.0

# --- NOISY Environment Presets (Uncomment to use for deployment) ---
# If the background is loud, increase these to prevent VAD from triggering on background chatter.
# VAD_ENERGY_THRESHOLD_MULT_LOW = 3.5  # Requires signal to be 3.5x louder than background
# VAD_ENERGY_THRESHOLD_MULT_HIGH = 6.0 # Requires strong speech peak

VAD_MIN_SPEECH_MS = 200
VAD_MAX_SPEECH_MS = 1500
VAD_SILENCE_MS = 300  # silence to end recording
VAD_PRE_ROLL_MS = 100  # pre-roll buffer

# Feature extraction settings
N_MFCC = 13
N_FFT = 1024
HOP_LENGTH = 512
N_MELS = 128
FMIN = 80
FMAX = 7600

# LPC settings
LPC_ORDER = 12
LPC_FRAME_MS = 25
LPC_HOP_MS = 16

# Template settings
TEMPLATE_FIXED_FRAMES = 50  # for mel template resizing
STATS_SEGMENTS = 3  # number of segments for stats features

# DTW settings
DTW_RADIUS = 6  # Increased to 6 to handle speed variations better (e.g., 暫停4.wav)

# Recognition thresholds
# Experimentally validated (2025-12-10): Current values are optimal. See docs/EXPERIMENT_NOISE_ROBUSTNESS.md
THRESHOLD_MFCC_DTW = 140.0  # Optimal threshold (validated via arena testing)
THRESHOLD_STATS = 600.0     # Increased due to more features (deltas+ZCR)
THRESHOLD_MEL = 0.50        # Cosine distance - Optimized for a balance of no_match and wrong_command
THRESHOLD_LPC = 100.0       # FastLPCMatcher - Balanced (tested: 80 too loose, 120 too strict)
THRESHOLD_RASTA_PLP = 140.0 # RASTA-PLP Matcher

# Command list
COMMANDS = ['START', 'PAUSE', 'JUMP', 'MAGNET', 'INVERT']

# Chinese command mapping (for template files)
COMMAND_MAPPING = {
    '開始': 'START',
    '暫停': 'PAUSE',
    '跳': 'JUMP',
    '磁鐵': 'MAGNET',
    '反轉': 'INVERT',
}
