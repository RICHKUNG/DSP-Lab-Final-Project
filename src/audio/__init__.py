"""
Audio 模組 - 語音辨識相關功能
整合 I/O、VAD、特徵提取、辨識器
"""

# 匯出核心模組
from .io import *
from .vad import *
from .features import *
from .recognizers import *

# 匯出工具函數 (previously inline or from audio_utils)
# Now imported from their respective new homes
from .features import estimate_snr
from .io import load_templates_from_dir, default_noise_decider

__all__ = [
    'estimate_snr',
    'load_templates_from_dir',
    'default_noise_decider',
]