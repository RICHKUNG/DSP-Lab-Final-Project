"""Template loading utilities for Bio-Voice Commander.

Centralizes filesystem traversal, filename→command mapping, and noise-template
handling so that recognizers stay focused on matching logic.
"""

from pathlib import Path
from typing import Callable, Dict, Iterable, Tuple

import numpy as np

from . import config
from .audio_io import load_audio_file

NoiseDecider = Callable[[str], bool]
TemplateAdder = Callable[[str, "np.ndarray", str], None]  # command, audio, filename
NoiseAdder = Callable[["np.ndarray"], None]


def default_noise_decider(stem: str) -> bool:
    """Identify noise files by simple substring checks."""
    lowered = stem.lower()
    return "noise" in lowered or "噪音" in stem


def _iter_audio_files(root: Path) -> Iterable[Path]:
    """Yield audio files under root using broad extension matching."""
    return root.glob("*.[mw][4a][av]")


def load_templates_from_dir(
    template_dir: str,
    add_template: TemplateAdder,
    add_noise: NoiseAdder,
    noise_decider: NoiseDecider = default_noise_decider,
    command_mapping: Dict[str, str] = None,
) -> Tuple[int, int]:
    """
    Load templates and noise profiles from a directory tree.

    Returns:
        (num_templates, num_noise) loaded.
    """
    if command_mapping is None:
        command_mapping = config.COMMAND_MAPPING

    base = Path(template_dir)
    if not base.exists():
        print(f"[WARN] Template directory does not exist: {base}")
        return 0, 0

    templates_loaded = 0
    noise_loaded = 0

    def handle_file(audio_path: Path):
        nonlocal templates_loaded, noise_loaded
        stem = audio_path.stem

        if noise_decider(stem):
            audio = load_audio_file(str(audio_path))
            add_noise(audio)
            noise_loaded += 1
            print(f"Loaded noise template: {audio_path.name}")
            return

        for cn_cmd, en_cmd in command_mapping.items():
            if stem.startswith(cn_cmd) or cn_cmd in stem:
                audio = load_audio_file(str(audio_path))
                add_template(en_cmd, audio, audio_path.name)
                templates_loaded += 1
                print(f"Loaded template: {audio_path.name} -> {en_cmd}")
                return

    # 1) cmd_templates subdir (preferred)
    cmd_templates_dir = base / "cmd_templates"
    if cmd_templates_dir.exists():
        for audio_file in _iter_audio_files(cmd_templates_dir):
            handle_file(audio_file)

    # 2) Top-level audio files
    for audio_file in _iter_audio_files(base):
        handle_file(audio_file)

    # 3) noise subdir
    noise_dir = base / "noise"
    if noise_dir.exists() and noise_dir.is_dir():
        for audio_file in _iter_audio_files(noise_dir):
            audio = load_audio_file(str(audio_file))
            add_noise(audio)
            noise_loaded += 1
            print(f"Loaded noise template: {noise_dir.name}/{audio_file.name}")

    # 4) Speaker subdirectories (exclude code/tools dirs)
    skip_dirs = {"features", "raw", "cmd_templates", "noise", "record", "src", "temp", "__pycache__", ".git"}
    for speaker_dir in base.iterdir():
        if speaker_dir.is_dir() and speaker_dir.name not in skip_dirs:
            for audio_file in _iter_audio_files(speaker_dir):
                handle_file(audio_file)

    return templates_loaded, noise_loaded
