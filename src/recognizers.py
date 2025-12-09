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
        self.template_names: Dict[str, List[str]] = {}  # Track template filenames
        self.noise_templates: List[np.ndarray] = []  # Noise templates for rejection

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

    def add_template(self, command: str, audio: np.ndarray, filename: str = None):
        """Add a template for a command."""
        features = self._extract_features(audio)
        if command not in self.templates:
            self.templates[command] = []
            self.template_names[command] = []
        self.templates[command].append(features)
        self.template_names[command].append(filename or "unknown")

    def add_noise_template(self, audio: np.ndarray):
        """Add a noise template for rejection."""
        features = self._extract_features(audio)
        self.noise_templates.append(features)

    def _compute_distance(self, feat1: np.ndarray, feat2: np.ndarray) -> float:
        """Compute distance between features."""
        if self.method == 'mfcc_dtw':
            return dtw_distance_normalized(feat1, feat2)
        elif self.method == 'mel':
            return mel_distance(feat1, feat2)
        elif self.method == 'lpc':
            # Use DTW for LPCC sequence
            return dtw_distance_normalized(feat1, feat2)
        else:
            return np.sqrt(np.sum((feat1 - feat2) ** 2))

    def recognize(self, audio: np.ndarray) -> Tuple[str, float, str, List[Tuple[str, str, float]], float]:
        """
        Recognize command from audio.

        Returns:
            (command, distance, best_template_name, all_distances, noise_distance)
            all_distances: List of (command, template_name, distance) sorted by distance
            noise_distance: Distance to closest noise template (inf if no noise templates)
        """
        if not self.templates:
            return ('NONE', float('inf'), '', [], float('inf'))

        features = self._extract_features(audio)

        best_command = 'NONE'
        best_distance = float('inf')
        best_template = ''
        all_distances = []

        for command, templates in self.templates.items():
            for i, template in enumerate(templates):
                dist = self._compute_distance(features, template)
                tpl_name = self.template_names[command][i]
                all_distances.append((command, tpl_name, dist))
                if dist < best_distance:
                    best_distance = dist
                    best_command = command
                    best_template = tpl_name

        # Compute noise distance
        noise_distance = float('inf')
        if self.noise_templates:
            for noise_feat in self.noise_templates:
                dist = self._compute_distance(features, noise_feat)
                if dist < noise_distance:
                    noise_distance = dist

        # Sort by distance
        all_distances.sort(key=lambda x: x[2])

        # Check if noise is closer than best command match
        # If input is closer to noise than to any command, return NOISE
        if noise_distance < best_distance:
            return ('NOISE', noise_distance, 'noise_template', all_distances, noise_distance)

        if best_distance > self.threshold:
            return ('NONE', best_distance, best_template, all_distances, noise_distance)

        return (best_command, best_distance, best_template, all_distances, noise_distance)


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

    def add_template(self, command: str, audio: np.ndarray, filename: str = None):
        """Add template to all matchers."""
        for matcher in self.matchers.values():
            matcher.add_template(command, audio, filename)

    def add_noise_template(self, audio: np.ndarray):
        """Add noise template to all matchers."""
        for matcher in self.matchers.values():
            matcher.add_noise_template(audio)

    def get_noise_template_count(self) -> int:
        """Get number of noise templates."""
        # All matchers have the same count, just return from first
        for matcher in self.matchers.values():
            return len(matcher.noise_templates)
        return 0

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
            cmd, dist, best_tpl, all_dists, noise_dist = matcher.recognize(audio)
            results[method] = {
                'command': cmd,
                'distance': dist,
                'best_template': best_tpl,
                'all_distances': all_dists,
                'noise_distance': noise_dist
            }

        # Weighted Ensemble Logic
        # Weights based on QA performance: MFCC is best for commands, Mel is best for noise rejection
        weights = {
            'mfcc_dtw': 4.0,  # MVP: High accuracy
            'mel': 2.0,       # Conservative noise filter
            'stats': 0.0,     # Disabled: Poor performance, biases towards START
            'lpc': 1.5        # Good noise rejection, but struggles with short commands
        }

        command_scores = {}
        total_weight = 0

        for method, result in results.items():
            cmd = result['command']
            weight = weights.get(method, 1.0)
            
            # Confidence calculation
            threshold = self.matchers[method].threshold
            # If distance > threshold (NONE), confidence is 0
            # If NOISE, confidence is based on how much closer it is to noise than command?
            # For simplicity, if cmd is valid, conf = 1 - dist/thresh
            
            if cmd not in ('NONE', 'NOISE'):
                conf = max(0, 1 - (result['distance'] / threshold))
            elif cmd == 'NOISE':
                conf = 1.0 # High confidence if it explicitly matches noise template
            else:
                conf = 0.0

            # Accumulate scores
            # We treat 'NOISE' and 'NONE' as distinct votes
            vote_cmd = cmd
            
            if vote_cmd not in command_scores:
                command_scores[vote_cmd] = 0.0
            
            command_scores[vote_cmd] += weight * conf
            total_weight += weight

        # Special Veto Rule: 
        # If Mel says NOISE, we lean heavily towards NOISE unless MFCC is VERY confident
        mel_res = results.get('mel')
        mfcc_res = results.get('mfcc_dtw')
        
        if mel_res and mel_res['command'] == 'NOISE':
            # Check MFCC confidence
            mfcc_conf = 0
            if mfcc_res and mfcc_res['command'] not in ('NONE', 'NOISE'):
                 mfcc_conf = max(0, 1 - (mfcc_res['distance'] / self.matchers['mfcc_dtw'].threshold))
            
            # If MFCC is not super confident (< 0.7), allow Mel to veto
            if mfcc_conf < 0.7:
                 command_scores['NOISE'] = command_scores.get('NOISE', 0) + 5.0 # Boost NOISE score

        # Find best command
        best_command = 'NONE'
        max_score = -1.0
        
        for cmd, score in command_scores.items():
            if score > max_score:
                max_score = score
                best_command = cmd

        # Fallback for method reporting
        best_method = 'ensemble' 
        best_confidence = max_score / sum(weights.values()) # Approximate normalized confidence
        best_template = ''
        
        # Try to find the template from the method that voted for the winner with highest weight
        highest_weight_for_winner = -1
        for method, result in results.items():
            if result['command'] == best_command:
                w = weights.get(method, 1.0)
                if w > highest_weight_for_winner:
                    highest_weight_for_winner = w
                    best_method = method
                    best_template = result['best_template']

        response = {
            'command': best_command,
            'confidence': best_confidence,
            'method': best_method,
            'best_template': best_template,
            'all_results': results
        }

        if mode == 'all':
            return response
        
        if mode == 'best':
             del response['all_results']
        
        return response

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

        # Check cmd_templates folder first
        cmd_templates_path = template_path / 'cmd_templates'
        if cmd_templates_path.exists():
            for audio_file in cmd_templates_path.glob('*.[mw][4a][av]'):
                filename = audio_file.stem
                
                # Check for noise
                if 'noise' in filename.lower() or '噪音' in filename:
                    audio = load_audio_file(str(audio_file))
                    self.add_noise_template(audio)
                    print(f"Loaded noise template: {audio_file.name}")
                    continue

                for cn_cmd, en_cmd in config.COMMAND_MAPPING.items():
                    if filename.startswith(cn_cmd):
                        audio = load_audio_file(str(audio_file))
                        self.add_template(en_cmd, audio, audio_file.name)
                        print(f"Loaded template: {audio_file.name} -> {en_cmd}")
                        break

        # Check for direct files (like 開始1.m4a)
        for audio_file in template_path.glob('*.[mw][4a][av]'):
            filename = audio_file.stem
            
            # Check for noise
            if 'noise' in filename.lower() or '噪音' in filename:
                audio = load_audio_file(str(audio_file))
                self.add_noise_template(audio)
                print(f"Loaded noise template: {audio_file.name}")
                continue

            for cn_cmd, en_cmd in config.COMMAND_MAPPING.items():
                if filename.startswith(cn_cmd):
                    audio = load_audio_file(str(audio_file))
                    self.add_template(en_cmd, audio, audio_file.name)
                    print(f"Loaded template: {audio_file.name} -> {en_cmd}")
                    break

        # Check for noise directory
        noise_dir = template_path / 'noise'
        if noise_dir.exists() and noise_dir.is_dir():
             for audio_file in noise_dir.glob('*.[mw][4a][av]'):
                audio = load_audio_file(str(audio_file))
                self.add_noise_template(audio)
                print(f"Loaded noise template: {noise_dir.name}/{audio_file.name}")

        # Check for speaker subdirectories
        for speaker_dir in template_path.iterdir():
            if speaker_dir.is_dir() and speaker_dir.name not in ['features', 'raw', 'cmd_templates', 'noise', 'record', 'src', 'temp', '__pycache__', '.git']:
                for audio_file in speaker_dir.glob('*.[mw][4a][av]'):
                    filename = audio_file.stem
                    
                    # Check for noise
                    if 'noise' in filename.lower() or '噪音' in filename:
                        audio = load_audio_file(str(audio_file))
                        self.add_noise_template(audio)
                        print(f"Loaded noise template: {speaker_dir.name}/{audio_file.name}")
                        continue

                    for cn_cmd, en_cmd in config.COMMAND_MAPPING.items():
                        if cn_cmd in filename:
                            audio = load_audio_file(str(audio_file))
                            self.add_template(en_cmd, audio, audio_file.name)
                            print(f"Loaded template: {speaker_dir.name}/{audio_file.name} -> {en_cmd}")
                            break
