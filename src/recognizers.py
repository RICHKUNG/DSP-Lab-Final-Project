"""Template matching recognizers with DTW."""

import numpy as np
from typing import Dict, List, Tuple
from pathlib import Path
from fastdtw import fastdtw
from scipy.spatial.distance import euclidean

from . import config
from .vad import preprocess_audio
from .features import extract_mfcc, extract_stats_features, extract_mel_template, extract_lpc_features, mel_distance


# =============================================================================
# DTW Distance
# =============================================================================

def dtw_distance(seq1: np.ndarray, seq2: np.ndarray, radius: int = 5) -> float:
    """
    Compute DTW distance between two sequences.

    Args:
        seq1: First sequence (n_frames1, n_features)
        seq2: Second sequence (n_frames2, n_features)
        radius: Sakoe-Chiba band radius

    Returns:
        DTW distance
    """
    if len(seq1) == 0 or len(seq2) == 0:
        return float('inf')

    distance, _ = fastdtw(seq1, seq2, radius=radius, dist=euclidean)
    return distance


def dtw_distance_normalized(seq1: np.ndarray, seq2: np.ndarray, radius: int = 5) -> float:
    """
    Compute length-normalized DTW distance.

    Args:
        seq1, seq2: Feature sequences
        radius: Sakoe-Chiba band radius

    Returns:
        Normalized DTW distance
    """
    dist = dtw_distance(seq1, seq2, radius)
    path_length = len(seq1) + len(seq2)
    return dist / path_length if path_length > 0 else float('inf')


# =============================================================================
# Template Matcher
# =============================================================================

class TemplateMatcher:
    """Base template matcher for a single method."""

    def __init__(self, method: str = 'mfcc_dtw', threshold: float = None):
        """
        Args:
            method: 'mfcc_dtw', 'stats', 'mel', 'lpc'
            threshold: Recognition threshold (None for default)
        """
        self.method = method
        self.templates: Dict[str, List[np.ndarray]] = {}

        if threshold is None:
            threshold_map = {
                'mfcc_dtw': config.THRESHOLD_MFCC_DTW,
                'stats': config.THRESHOLD_STATS,
                'mel': config.THRESHOLD_MEL,
                'lpc': config.THRESHOLD_LPC
            }
            threshold = threshold_map.get(method, 50.0)
        self.threshold = threshold

    def _extract_features(self, audio: np.ndarray) -> np.ndarray:
        """Extract features based on method."""
        processed = preprocess_audio(audio)

        if self.method == 'mfcc_dtw':
            return extract_mfcc(processed)
        elif self.method == 'stats':
            return extract_stats_features(processed)
        elif self.method == 'mel':
            return extract_mel_template(processed)
        elif self.method == 'lpc':
            return extract_lpc_features(processed)
        else:
            raise ValueError(f"Unknown method: {self.method}")

    def add_template(self, command: str, audio: np.ndarray):
        """Add a template for a command."""
        features = self._extract_features(audio)
        if command not in self.templates:
            self.templates[command] = []
        self.templates[command].append(features)

    def _compute_distance(self, feat1: np.ndarray, feat2: np.ndarray) -> float:
        """Compute distance between features."""
        if self.method == 'mfcc_dtw':
            return dtw_distance_normalized(feat1, feat2)
        elif self.method == 'mel':
            return mel_distance(feat1, feat2)
        else:
            return np.sqrt(np.sum((feat1 - feat2) ** 2))

    def recognize(self, audio: np.ndarray) -> Tuple[str, float]:
        """
        Recognize command from audio.

        Returns:
            (command, distance) or ('NONE', inf) if no match
        """
        if not self.templates:
            return ('NONE', float('inf'))

        features = self._extract_features(audio)

        best_command = 'NONE'
        best_distance = float('inf')

        for command, templates in self.templates.items():
            for template in templates:
                dist = self._compute_distance(features, template)
                if dist < best_distance:
                    best_distance = dist
                    best_command = command

        if best_distance > self.threshold:
            return ('NONE', best_distance)

        return (best_command, best_distance)


# =============================================================================
# Multi-Method Matcher
# =============================================================================

class MultiMethodMatcher:
    """Ensemble matcher using multiple methods."""

    def __init__(self, methods: List[str] = None):
        """
        Args:
            methods: List of methods to use (default: all)
        """
        if methods is None:
            methods = ['mfcc_dtw', 'stats', 'mel', 'lpc']

        self.matchers = {m: TemplateMatcher(method=m) for m in methods}

    def add_template(self, command: str, audio: np.ndarray):
        """Add template to all matchers."""
        for matcher in self.matchers.values():
            matcher.add_template(command, audio)

    def recognize(self, audio: np.ndarray, mode: str = 'best') -> Dict:
        """
        Recognize using all methods.

        Args:
            audio: Audio samples
            mode: 'best' returns only best result, 'all' returns all results

        Returns:
            Dict with recognition results
        """
        results = {}
        for method, matcher in self.matchers.items():
            cmd, dist = matcher.recognize(audio)
            results[method] = {'command': cmd, 'distance': dist}

        if mode == 'all':
            return {'all_results': results}

        best_method = None
        best_command = 'NONE'
        best_confidence = 0

        for method, result in results.items():
            if result['command'] != 'NONE':
                threshold = self.matchers[method].threshold
                conf = 1 - min(result['distance'] / threshold, 1)
                if conf > best_confidence:
                    best_confidence = conf
                    best_command = result['command']
                    best_method = method

        return {
            'command': best_command,
            'confidence': best_confidence,
            'method': best_method,
            'all_results': results
        }

    def load_templates_from_dir(self, template_dir: str):
        """
        Load templates from directory structure.

        Expected structure:
            template_dir/
                <speaker>/
                    <command>_<take>.wav
        or:
            template_dir/
                <command><number>.m4a
        """
        from .audio_io import load_audio_file

        template_path = Path(template_dir)

        # Check for direct files (like 開始1.m4a)
        for audio_file in template_path.glob('*.[mw][4a][av]'):
            filename = audio_file.stem
            for cn_cmd, en_cmd in config.COMMAND_MAPPING.items():
                if filename.startswith(cn_cmd):
                    audio = load_audio_file(str(audio_file))
                    self.add_template(en_cmd, audio)
                    print(f"Loaded template: {audio_file.name} -> {en_cmd}")
                    break

        # Check for speaker subdirectories
        for speaker_dir in template_path.iterdir():
            if speaker_dir.is_dir() and speaker_dir.name not in ['features', 'raw']:
                for audio_file in speaker_dir.glob('*.[mw][4a][av]'):
                    filename = audio_file.stem
                    for cn_cmd, en_cmd in config.COMMAND_MAPPING.items():
                        if cn_cmd in filename:
                            audio = load_audio_file(str(audio_file))
                            self.add_template(en_cmd, audio)
                            print(f"Loaded template: {speaker_dir.name}/{audio_file.name} -> {en_cmd}")
                            break
