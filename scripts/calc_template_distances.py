import sys
import os
import glob
import numpy as np
import librosa
import itertools
from pathlib import Path

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src import config
from src.audio.vad import preprocess_audio
from src.audio.features import extract_mfcc
from src.audio.recognizers import dtw_distance_normalized

def load_and_extract_features(filepath):
    """Load wav file and extract MFCC features."""
    try:
        # Use librosa to load and resample automatically
        data, rate = librosa.load(filepath, sr=config.SAMPLE_RATE, mono=True)
        
        processed = preprocess_audio(data)
        features = extract_mfcc(processed)
        return features
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return None

def main():
    template_dir = config.TEMPLATE_DIR
    wav_files = glob.glob(os.path.join(template_dir, "*.wav"))
    
    if not wav_files:
        print(f"No .wav files found in {template_dir}")
        return

    print(f"Found {len(wav_files)} template files.")
    
    features_map = {}
    
    for fpath in wav_files:
        fname = os.path.basename(fpath)
        # Try to decode filename if it looks like bytes, though os.path usually handles it.
        # Just printing might be messy but processing should work.
        print(f"Processing {fname}...")
        feats = load_and_extract_features(fpath)
        if feats is not None:
            features_map[fname] = feats

    filenames = sorted(features_map.keys())
    pairs = list(itertools.combinations(filenames, 2))
    
    output_file = "template_distances.txt"
    print(f"Calculating distances for {len(pairs)} pairs...")
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("File1,File2,Distance\n")
        for name1, name2 in pairs:
            feat1 = features_map[name1]
            feat2 = features_map[name2]
            
            # distance is potentially asymmetric depending on implementation, 
            # but DTW is usually symmetric if seqs are swapped. 
            # dtw_distance_normalized calls fastdtw with euclidean.
            
            dist = dtw_distance_normalized(feat1, feat2, radius=config.DTW_RADIUS)
            f.write(f"{name1},{name2},{dist:.4f}\n")
            
    print(f"Done. Results written to {output_file}")

if __name__ == "__main__":
    main()