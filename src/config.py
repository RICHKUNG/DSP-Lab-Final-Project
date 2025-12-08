"""Global configuration for Bio-Voice Commander."""

# Audio settings
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SIZE = 512  # ~32ms at 16kHz
DTYPE = 'int16'

# VAD settings
VAD_ENERGY_THRESHOLD_MULT_LOW = 1.5
VAD_ENERGY_THRESHOLD_MULT_HIGH = 5.0
VAD_MIN_SPEECH_MS = 200
VAD_MAX_SPEECH_MS = 1500
VAD_SILENCE_MS = 300  # silence to end recording
VAD_PRE_ROLL_MS = 100  # pre-roll buffer

# Feature extraction settings
N_MFCC = 13
N_FFT = 1024
HOP_LENGTH = 256
N_MELS = 128
FMIN = 80
FMAX = 7600

# LPC settings
LPC_ORDER = 12
LPC_FRAME_MS = 25
LPC_HOP_MS = 10

# Template settings
TEMPLATE_FIXED_FRAMES = 50  # for mel template resizing
STATS_SEGMENTS = 3  # number of segments for stats features

# Recognition thresholds (to be tuned)
THRESHOLD_MFCC_DTW = 150.0  # Increased from 50.0 based on tests (obs: 60-110)
THRESHOLD_STATS = 400.0     # Increased from 30.0 (obs: 150-370)
THRESHOLD_MEL = 50.0        # Decreased from 100.0 (obs: 30-35)
THRESHOLD_LPC = 2.0         # Drastically decreased from 20.0 (obs: 0.3-0.8)

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
