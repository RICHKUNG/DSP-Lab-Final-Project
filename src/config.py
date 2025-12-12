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
CHUNK_SIZE = 256  # Reduced to ~16ms for lower latency response
DTYPE = 'int16'

# VAD settings
# --- Default (Quiet/Normal Environment) ---
VAD_ENERGY_THRESHOLD_MULT_LOW = 1.6   # More sensitive start trigger
VAD_ENERGY_THRESHOLD_MULT_HIGH = 3.5  # Faster to consider speech active

# --- NOISY Environment Presets (Uncomment to use for deployment) ---
# If the background is loud, increase these to prevent VAD from triggering on background chatter.
# VAD_ENERGY_THRESHOLD_MULT_LOW = 3.5  # Requires signal to be 3.5x louder than background
# VAD_ENERGY_THRESHOLD_MULT_HIGH = 6.0 # Requires strong speech peak

VAD_MIN_SPEECH_MS = 120
VAD_MAX_SPEECH_MS = 1500
VAD_SILENCE_MS = 80   # Faster hangover to cut latency
VAD_PRE_ROLL_MS = 50  # Reduced buffer

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
DTW_RADIUS = 8  # Increased for better speed variation tolerance (was 3)

# Recognition thresholds (tuned for higher sensitivity in-game)
THRESHOLD_MFCC_DTW = 320.0  # Slightly looser to avoid false negatives on quiet speech
THRESHOLD_STATS = 600.0     # Increased due to more features (deltas+ZCR)
THRESHOLD_MEL = 0.60        # Cosine distance - allow more variation to improve hit rate
THRESHOLD_LPC = 110.0       # FastLPCMatcher - Balanced (tested: 80 too loose, 120 too strict)
THRESHOLD_RASTA_PLP = 280.0 # RASTA-PLP Matcher
THRESHOLD_RAW_DTW = 0.020  # Raw audio DTW (downsampled 16x, normalized distance)

# Command list
COMMANDS = ['START', 'PAUSE', 'JUMP', 'FLIP']

# Voice Recognition Strategy Settings
# Options:
# - 'adaptive_ensemble': Best accuracy (97.9%). Uses SNR to weight methods.
# - 'mfcc_dtw': Fast, standard DTW. Good for clean environments.
# - 'ensemble': Fixed-weight ensemble (MFCC+Mel+LPC).
DEFAULT_VOICE_METHOD = 'mfcc_dtw'

# Chinese command mapping (for template files)
COMMAND_MAPPING = {
    '開始': 'START',
    'start': 'START',
    '暫停': 'PAUSE',
    'pause': 'PAUSE',
    '跳': 'JUMP',
    'jump': 'JUMP',
    '翻': 'FLIP',
    'flip': 'FLIP',
}
