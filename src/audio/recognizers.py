"""Template matching recognizers with DTW."""

import numpy as np
from typing import Dict, List, Tuple
from pathlib import Path
from fastdtw import fastdtw
from scipy.spatial.distance import euclidean
from scipy.ndimage import zoom

from .. import config
from .vad import preprocess_audio
from .features import extract_mfcc, extract_stats_features, extract_mel_template, extract_lpc_features, extract_rasta_plp, mel_distance, estimate_snr


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
    if len(seq1) == 0 or len(seq2) == 0:
        return float('inf')

    distance, path = fastdtw(seq1, seq2, radius=radius, dist=euclidean)
    path_length = len(path)
    return distance / path_length if path_length > 0 else float('inf')


# =============================================================================
# Template Matcher
# =============================================================================

class TemplateMatcher:
    """Base template matcher for a single method."""

    def __init__(self, method: str = 'mfcc_dtw', threshold: float = None, mfcc_first_delta_only: bool = False):
        """
        Args:
            method: 'mfcc_dtw', 'stats', 'mel', 'lpc', 'rasta_plp', 'raw_dtw'
            threshold: Recognition threshold (None for default)
            mfcc_first_delta_only: If True, uses only 1st order delta for MFCC.
        """
        self.method = method
        self.mfcc_first_delta_only = mfcc_first_delta_only
        self.templates: Dict[str, List[np.ndarray]] = {}
        self.template_names: Dict[str, List[str]] = {}  # Track template filenames
        self.noise_templates: List[np.ndarray] = []  # Noise templates for rejection

        if threshold is None:
            threshold_map = {
                'mfcc_dtw': config.THRESHOLD_MFCC_DTW,
                'stats': config.THRESHOLD_STATS,
                'mel': config.THRESHOLD_MEL,
                'lpc': config.THRESHOLD_LPC,
                'rasta_plp': config.THRESHOLD_RASTA_PLP,
                'raw_dtw': config.THRESHOLD_RAW_DTW
            }
            threshold = threshold_map.get(method, 50.0)
        self.threshold = threshold

    def _extract_features(self, audio: np.ndarray) -> np.ndarray:
        """Extract features based on method."""
        processed = preprocess_audio(audio)

        if self.method == 'mfcc_dtw':
            return extract_mfcc(processed, first_delta_only=self.mfcc_first_delta_only)
        elif self.method == 'stats':
            return extract_stats_features(processed)
        elif self.method == 'mel':
            return extract_mel_template(processed)
        elif self.method == 'lpc':
            return extract_lpc_features(processed)
        elif self.method == 'rasta_plp':
            return extract_rasta_plp(processed)
        elif self.method == 'raw_dtw':
            # Downsample by factor of 16 to speed up DTW (16kHz -> 1kHz)
            # This reduces computation dramatically while preserving waveform shape
            # At 1kHz, we still capture the fundamental frequency of speech (80-300Hz)
            downsample_factor = 16
            downsampled = processed[::downsample_factor]
            # Return raw audio as 2D array for DTW (n_samples, 1)
            return downsampled.reshape(-1, 1).astype(np.float32)
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
        if self.method == 'mfcc_dtw' or self.method == 'rasta_plp' or self.method == 'raw_dtw':
            return dtw_distance_normalized(feat1, feat2, radius=config.DTW_RADIUS)
        elif self.method == 'mel':
            return mel_distance(feat1, feat2, metric='cosine')
        elif self.method == 'lpc':
            # Use DTW for LPCC sequence
            return dtw_distance_normalized(feat1, feat2, radius=config.DTW_RADIUS)
        else:
            return np.sqrt(np.sum((feat1 - feat2) ** 2))

    def recognize(self, audio: np.ndarray, features: np.ndarray = None) -> Tuple[str, float, str, List[Tuple[str, str, float]], float]:
        """
        Recognize command from audio.

        Args:
            audio: Raw audio samples (used if features not provided)
            features: Pre-computed features (optional optimization)

        Returns:
            (command, distance, best_template_name, all_distances, noise_distance)
            all_distances: List of (command, template_name, distance) sorted by distance
            noise_distance: Distance to closest noise template (inf if no noise templates)
        """
        if not self.templates:
            return ('NONE', float('inf'), '', [], float('inf'))

        if features is None:
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
# Fast LPC Matcher (Optimized)
# =============================================================================

class FastLPCMatcher:
    """LPC matcher using fixed-size Euclidean distance instead of DTW.

    This optimization reduces LPC matching latency by ~20x while maintaining
    100% accuracy in both clean and noisy conditions.

    Strategy:
    - Resize LPC features to fixed 30 frames
    - Flatten to 1D vector
    - Use Euclidean distance (~2.5μs vs 32ms for DTW)
    """

    def __init__(self, fixed_frames: int = 30, threshold: float = None):
        """
        Args:
            fixed_frames: Target number of frames for resizing
            threshold: Recognition threshold (default 100.0)
        """
        self.fixed_frames = fixed_frames
        self.templates: Dict[str, List[np.ndarray]] = {}
        self.template_names: Dict[str, List[str]] = {}
        self.noise_templates: List[np.ndarray] = []
        self.threshold = threshold or 100.0
        self.method = 'lpc'  # For compatibility

    def _extract_features(self, audio: np.ndarray) -> np.ndarray:
        """Extract fixed-size LPC features."""
        processed = preprocess_audio(audio)
        lpc = extract_lpc_features(processed)

        # Resize to fixed size if needed
        if lpc.shape[0] != self.fixed_frames:
            zoom_factor = self.fixed_frames / lpc.shape[0]
            lpc = zoom(lpc, (zoom_factor, 1), order=1)

        # Flatten to 1D for fast Euclidean distance
        return lpc.flatten().astype(np.float32)

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

    def recognize(self, audio: np.ndarray, features: np.ndarray = None) -> Tuple[str, float, str, List[Tuple[str, str, float]], float]:
        """
        Recognize command from audio.

        Args:
            audio: Raw audio samples (used if features not provided)
            features: Pre-computed features (optional)

        Returns:
            (command, distance, best_template_name, all_distances, noise_distance)
        """
        if not self.templates:
            return ('NONE', float('inf'), '', [], float('inf'))

        if features is None:
            features = self._extract_features(audio)

        best_command = 'NONE'
        best_distance = float('inf')
        best_template = ''
        all_distances = []

        # Compare with all command templates
        for command, templates in self.templates.items():
            for i, template in enumerate(templates):
                # Fast Euclidean distance
                dist = np.sqrt(np.sum((features - template) ** 2))
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
                dist = np.sqrt(np.sum((features - noise_feat) ** 2))
                if dist < noise_distance:
                    noise_distance = dist

        # Sort by distance
        all_distances.sort(key=lambda x: x[2])

        # Check if noise is closer than best command match
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

    def __init__(self, methods: List[str] = None, mfcc_first_delta_only: bool = False):
        """
        Args:
            methods: List of methods to use (default: all)
            mfcc_first_delta_only: If True, MFCC extraction uses only 1st order delta.
        """
        self.mfcc_first_delta_only = mfcc_first_delta_only
        if methods is None:
            methods = ['mfcc_dtw', 'lpc']

        # Use FastLPCMatcher for LPC, standard TemplateMatcher for others
        self.matchers = {}
        for m in methods:
            if m == 'lpc':
                self.matchers[m] = FastLPCMatcher(fixed_frames=30, threshold=100.0)
            else:
                self.matchers[m] = TemplateMatcher(method=m, mfcc_first_delta_only=self.mfcc_first_delta_only)

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

    def recognize(self, audio: np.ndarray, mode: str = 'best', adaptive: bool = False, methods: List[str] = None, known_snr: float = None) -> Dict:
        """
        Recognize using all methods.

        Args:
            audio: Audio samples
            mode: 'best' returns only best result, 'all' returns all results
            adaptive: Whether to use SNR-adaptive weighting
            methods: Optional subset of matcher names to evaluate (default: all)
            known_snr: Optional known SNR to use instead of estimating it

        Returns:
            Dict with recognition results
        """
        # Limit active methods if requested
        active_methods = methods or list(self.matchers.keys())
        active_methods = [m for m in active_methods if m in self.matchers]
        if not active_methods:
            active_methods = list(self.matchers.keys())

        # Allow legacy mode flag to force MFCC-only fast path
        if mode == 'mfcc_dtw':
            active_methods = ['mfcc_dtw']
            mode = 'best'

        # 1. Preprocess audio ONCE
        processed_audio = preprocess_audio(audio)
        
        # 2. Extract features ONCE for each needed type
        feature_cache = {}
        
        # We know we need MFCC, MEL, LPC. Stats is disabled.
        # But to be safe with the 'methods' list, we check.
        
        if 'mfcc_dtw' in active_methods:
            feature_cache['mfcc_dtw'] = extract_mfcc(processed_audio, first_delta_only=self.mfcc_first_delta_only)

        if 'mel' in active_methods:
            feature_cache['mel'] = extract_mel_template(processed_audio)

        if 'rasta_plp' in active_methods:
            feature_cache['rasta_plp'] = extract_rasta_plp(processed_audio)

        # For LPC with FastLPCMatcher, let it handle feature extraction internally
        # (it needs to resize and flatten, which is specific to FastLPCMatcher)
        # So we don't pre-cache LPC features
            
        # Skip 'stats' feature extraction entirely (saving time)
        
        results = {}
        for method in active_methods:
            matcher = self.matchers.get(method)
            if matcher is None:
                continue
            # Skip stats execution
            if method == 'stats':
                results[method] = {
                    'command': 'NONE',
                    'distance': float('inf'),
                    'best_template': '',
                    'all_distances': [],
                    'noise_distance': float('inf')
                }
                continue
                
            # Use pre-computed features (except for LPC which handles its own)
            feats = feature_cache.get(method)
            # For LPC (FastLPCMatcher), pass None to let it extract internally
            if method == 'lpc':
                feats = None
            cmd, dist, best_tpl, all_dists, noise_dist = matcher.recognize(audio, features=feats)
            results[method] = {
                'command': cmd,
                'distance': dist,
                'best_template': best_tpl,
                'all_distances': all_dists,
                'noise_distance': noise_dist
            }

        # Adaptive Weighting Logic
        snr = 50.0  # Default to clean
        if adaptive:
            if known_snr is not None:
                snr = known_snr
            else:
                snr = estimate_snr(audio)
            weights = get_adaptive_weights(snr)
        else:
             # Default Ensemble Weights
             weights = {
                'mfcc_dtw': 4.0,  # MVP: High accuracy
                'mel': 3.5,       # Increased: Very stable in noise
                'stats': 0.0,     # Disabled: Poor performance
                'lpc': 0.5        # Decreased: Fragile in high noise
            }

        command_scores = {}
        total_weight = 0.0

        for method, result in results.items():
            cmd = result['command']
            weight = weights.get(method, 1.0)
            
            # Confidence calculation
            threshold = getattr(self.matchers.get(method), 'threshold', 1.0)
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
            if weight > 0:
                total_weight += weight

        # Find best command
        best_command = 'NONE'
        max_score = -1.0
        
        for cmd, score in command_scores.items():
            if score > max_score:
                max_score = score
                best_command = cmd

        # Fallback for method reporting
        best_method = 'ensemble' 
        best_confidence = max_score / total_weight if total_weight > 0 else 0.0 # Approximate normalized confidence
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
            'all_results': results,
            'snr': snr # Debug info
        }

        if mode == 'all':
            return response
        
        if mode == 'best':
             del response['all_results']
        
        return response

    def recognize_voting(self, audio: np.ndarray, adaptive: bool = True, known_snr: float = None) -> Dict:
        """
        Recognize using Weighted Majority Voting (Hard Voting).
        
        Unlike standard recognize() which sums confidence scores (Soft Voting),
        this method counts discrete votes from each classifier.
        
        Args:
            audio: Audio samples
            adaptive: Whether to use SNR-adaptive voting weights
            known_snr: Optional known SNR to use instead of estimating it
        """
        # 1. Standard extraction
        processed_audio = preprocess_audio(audio)
        feature_cache = {}
        
        if 'mfcc_dtw' in self.matchers:
            feature_cache['mfcc_dtw'] = extract_mfcc(processed_audio, first_delta_only=self.mfcc_first_delta_only)
        if 'mel' in self.matchers:
            feature_cache['mel'] = extract_mel_template(processed_audio)
        if 'rasta_plp' in self.matchers:
            feature_cache['rasta_plp'] = extract_rasta_plp(processed_audio)

        # 2. Get individual results
        results = {}
        for method, matcher in self.matchers.items():
            if method == 'stats': continue
            
            feats = feature_cache.get(method)
            if method == 'lpc': feats = None
            
            cmd, dist, best_tpl, all_dists, noise_dist = matcher.recognize(audio, features=feats)
            results[method] = {
                'command': cmd,
                'distance': dist,
                'best_template': best_tpl
            }

        # 3. Determine Weights
        snr = 50.0
        if adaptive:
             if known_snr is not None:
                 snr = known_snr
             else:
                 snr = estimate_snr(audio)
             weights = get_adaptive_weights(snr)
        else:
             weights = {'mfcc_dtw': 5.0, 'lpc': 1.0, 'stats': 0.0}

        # 4. Voting Logic
        votes = {}
        
        for method, res in results.items():
            cmd = res['command']
            weight = weights.get(method, 0.0)
            
            # Veto logic: If Mel says NOISE, and MFCC is weak, treat as NOISE
            if method == 'mel' and cmd == 'NOISE':
                mfcc_res = results.get('mfcc_dtw')
                if mfcc_res:
                    # Check MFCC confidence
                    mfcc_thresh = getattr(self.matchers['mfcc_dtw'], 'threshold', 140.0)
                    mfcc_conf = max(0, 1 - (mfcc_res['distance'] / mfcc_thresh))
                    if mfcc_conf < 0.6: # If MFCC is unsure
                        votes['NOISE'] = votes.get('NOISE', 0) + 5.0 # Super Vote for Noise
            
            if cmd != 'NONE':
                votes[cmd] = votes.get(cmd, 0) + weight

        # 5. Winner
        best_command = 'NONE'
        max_votes = -1.0
        total_possible_votes = 0.0
        
        for method, weight in weights.items():
            if method in results:
                total_possible_votes += weight

        for cmd, vote_count in votes.items():
            if vote_count > max_votes:
                max_votes = vote_count
                best_command = cmd
        
        # Calculate Vote Confidence
        confidence = 0.0
        if total_possible_votes > 0:
            confidence = max_votes / total_possible_votes

        return {
            'command': best_command,
            'confidence': confidence,
            'method': 'voting',
            'snr': snr,
            'all_results': results
        }

    def load_templates_from_dir(self, template_dir: str):
        """Delegate to shared template loader."""
        from . import load_templates_from_dir as _load_templates_from_dir
        _load_templates_from_dir(
            template_dir=template_dir,
            add_template=self.add_template,
            add_noise=self.add_noise_template,
            command_mapping=config.COMMAND_MAPPING,
        )

def get_adaptive_weights(snr_db: float) -> Dict[str, float]:
    """
    Get weights based on SNR.
    
    Strategy:
    - Clean (>30dB): Favor mfcc_dtw (fast, accurate)
    - Moderate (15-30dB): Balanced
    - Noisy (<15dB): Favor mfcc_dtw as mel is removed
    """
    if snr_db > 30:
        return {'mfcc_dtw': 6.0, 'lpc': 0.5, 'stats': 0.0}
    elif snr_db > 15:
        return {'mfcc_dtw': 5.0, 'lpc': 0.5, 'stats': 0.0}
    else:
        return {'mfcc_dtw': 4.0, 'lpc': 0.5, 'stats': 0.0}
