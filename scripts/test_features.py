"""Test script for feature extraction modules."""

import sys
import os

# Add src to path

# Ensure the project root is in the Python path for module imports
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_current_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src import config
from src.audio_io import load_audio_file
from src.vad import preprocess_audio
from src.features import extract_mfcc, extract_stats_features, extract_mel_template, extract_lpc_features


def test_features():
    """Test feature extraction on template files."""
    print("=" * 60)
    print("Feature Extraction Test")
    print("=" * 60)

    # Find audio files
    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cmd_templates')
    audio_files = []

    for ext in ['*.m4a', '*.wav', '*.mp3']:
        import glob
        audio_files.extend(glob.glob(os.path.join(base_dir, ext)))

    if not audio_files:
        print("No audio files found in current directory!")
        return False

    print(f"\nFound {len(audio_files)} audio files:")
    for f in audio_files:
        print(f"  - {os.path.basename(f)}")

    success = True

    for audio_path in audio_files:
        print(f"\n{'=' * 60}")
        print(f"Processing: {os.path.basename(audio_path)}")
        print("=" * 60)

        try:
            # Load audio
            audio = load_audio_file(audio_path)
            print(f"  Audio loaded: {len(audio)} samples ({len(audio)/config.SAMPLE_RATE:.2f}s)")

            # Preprocess
            processed = preprocess_audio(audio)
            print(f"  Preprocessed: {len(processed)} samples")

            # Test MFCC
            mfcc = extract_mfcc(processed)
            print(f"  MFCC shape: {mfcc.shape}")

            # Test Stats
            stats = extract_stats_features(processed)
            print(f"  Stats shape: {stats.shape}")

            # Test Mel
            mel = extract_mel_template(processed)
            print(f"  Mel shape: {mel.shape}")

            # Test LPC
            lpc = extract_lpc_features(processed)
            print(f"  LPC shape: {lpc.shape}")

            print("  [OK] All features extracted successfully")

        except Exception as e:
            print(f"  [ERROR] {e}")
            import traceback
            traceback.print_exc()
            success = False

    return success


def test_recognition():
    """Test recognition with template files."""
    print("\n" + "=" * 60)
    print("Recognition Test")
    print("=" * 60)

    from src.recognizers import MultiMethodMatcher

    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cmd_templates')

    # Create matcher and load templates
    matcher = MultiMethodMatcher()
    matcher.load_templates_from_dir(base_dir)

    # Check if templates were loaded
    total_templates = 0
    for method, m in matcher.matchers.items():
        for cmd, templates in m.templates.items():
            total_templates += len(templates)

    if total_templates == 0:
        print("No templates loaded!")
        return False

    print(f"\nTotal templates loaded: {total_templates}")

    # Test self-recognition (should match perfectly)
    print("\nSelf-recognition test (each file against itself):")

    import glob
    for ext in ['*.m4a', '*.wav']:
        for audio_path in glob.glob(os.path.join(base_dir, ext)):
            audio = load_audio_file(audio_path)
            result = matcher.recognize(audio, mode='all')

            filename = os.path.basename(audio_path)
            print(f"\n  {filename}:")
            for method, res in result['all_results'].items():
                status = "[MATCH]" if res['command'] != 'NONE' else "[NONE]"
                print(f"    {method:12s}: {res['command']:8s} dist={res['distance']:.2f} {status}")

    return True


if __name__ == '__main__':
    print("\nBio-Voice Commander - Feature Test\n")

    # Test 1: Feature extraction
    if test_features():
        print("\n[PASS] Feature extraction test passed!")
    else:
        print("\n[FAIL] Feature extraction test failed!")
        sys.exit(1)

    # Test 2: Recognition
    if test_recognition():
        print("\n[PASS] Recognition test passed!")
    else:
        print("\n[FAIL] Recognition test failed!")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)
