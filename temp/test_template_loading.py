"""
測試 test_live.py 的模板載入功能
"""
import sys
import os
from pathlib import Path

# Add project root to path
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_current_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.audio.io import load_audio_file
from src.audio.recognizers import MultiMethodMatcher
from src import config


def test_template_loading_modes():
    """測試三種模板載入模式"""
    base_dir = os.path.join(_project_root, "cmd_templates")
    augmented_dir = os.path.join(base_dir, "augmented")

    print("=" * 80)
    print("模板載入測試")
    print("=" * 80)

    # Helper function (same as in test_live.py)
    def load_templates_from_path(matcher, path, description=""):
        """Load templates from a specific path."""
        if not os.path.exists(path):
            print(f"[WARN] Directory not found: {path}")
            return 0

        count = 0
        for audio_file in sorted(Path(path).glob("*.wav")):
            # Skip noise files
            if "noise" in audio_file.stem.lower() or "噪音" in audio_file.stem:
                continue

            try:
                audio_data = load_audio_file(str(audio_file))
                # Determine command from filename
                matched = False
                for cn_cmd, en_cmd in config.COMMAND_MAPPING.items():
                    if audio_file.stem.startswith(cn_cmd) or cn_cmd in audio_file.stem:
                        matcher.add_template(en_cmd, audio_data, audio_file.name)
                        count += 1
                        matched = True
                        break
            except Exception as e:
                print(f"  [ERROR] Failed to load {audio_file.name}: {e}")
        return count

    # Test 1: Original only (default)
    print("\n[測試 1] 預設模式：只載入原始模板")
    print("-" * 80)
    matcher1 = MultiMethodMatcher(methods=['mfcc_dtw'])
    count1 = load_templates_from_path(matcher1, base_dir, "Original")
    print(f"結果: 載入 {count1} 個原始模板")

    # Print template summary
    for method, m in matcher1.matchers.items():
        if m.templates:
            print(f"\n  {method} 模板:")
            for cmd, templates in m.templates.items():
                tpl_names = m.template_names.get(cmd, [])
                print(f"    - {cmd}: {len(templates)} 個 ({', '.join(tpl_names[:3])}...)" if len(tpl_names) > 3 else f"    - {cmd}: {len(templates)} 個 ({', '.join(tpl_names)})")

    # Test 2: Include augmented
    print("\n[測試 2] 包含增強模板")
    print("-" * 80)
    matcher2 = MultiMethodMatcher(methods=['mfcc_dtw'])
    orig_count = load_templates_from_path(matcher2, base_dir, "Original")
    aug_count = load_templates_from_path(matcher2, augmented_dir, "Augmented")
    print(f"結果: {orig_count} 個原始 + {aug_count} 個增強 = {orig_count + aug_count} 個總模板")

    # Print template summary
    for method, m in matcher2.matchers.items():
        if m.templates:
            print(f"\n  {method} 模板:")
            for cmd, templates in m.templates.items():
                tpl_names = m.template_names.get(cmd, [])
                aug_tpl_count = sum(1 for name in tpl_names if 'aug' in name)
                orig_tpl_count = len(templates) - aug_tpl_count
                print(f"    - {cmd}: {len(templates)} 個 (原始: {orig_tpl_count}, 增強: {aug_tpl_count})")

    # Test 3: Augmented only
    print("\n[測試 3] 只載入增強模板")
    print("-" * 80)
    matcher3 = MultiMethodMatcher(methods=['mfcc_dtw'])
    count3 = load_templates_from_path(matcher3, augmented_dir, "Augmented")
    print(f"結果: 載入 {count3} 個增強模板")

    # Print template summary
    for method, m in matcher3.matchers.items():
        if m.templates:
            print(f"\n  {method} 模板:")
            for cmd, templates in m.templates.items():
                tpl_names = m.template_names.get(cmd, [])
                print(f"    - {cmd}: {len(templates)} 個")
                # Show some examples
                if len(tpl_names) > 0:
                    print(f"      範例: {tpl_names[0]}, {tpl_names[1] if len(tpl_names) > 1 else ''}")

    print("\n" + "=" * 80)
    print("測試完成！")
    print("=" * 80)


if __name__ == "__main__":
    test_template_loading_modes()
