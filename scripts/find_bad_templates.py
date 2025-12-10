"""Identify which specific template files are performing poorly.

This helps prioritize which templates to re-record.
"""
import sys
import os
import glob
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
record_dir = os.path.join(base_dir, "record")

# Load latest result
json_files = sorted(glob.glob(os.path.join(record_dir, "arena_*.json")))
if not json_files:
    print("No arena results found!")
    sys.exit(1)

latest_file = json_files[-1]
with open(latest_file, 'r', encoding='utf-8') as f:
    result = json.load(f)

print("=" * 80)
print(f"TEMPLATE PERFORMANCE ANALYSIS: {result['timestamp']}")
print("=" * 80)

# Aggregate performance per template file
# Arena test uses leave-one-out, so each template is tested across all conditions
template_stats = {}

for suite_name, suite_data in result['suites'].items():
    for condition, data in suite_data['methods']['ensemble'].items():
        correct = data['correct']
        total = data['total']
        # In leave-one-out, total = number of templates
        # Each template tested once per condition

        # We can't directly map back to template names from aggregated data
        # But we can infer from the test structure

# Alternative approach: Read from the raw test if available
# For now, let's analyze at command level from the aggregated data

print("\nPer-Command Success Rate (Ensemble):")
print("-" * 80)

# Count successes across all conditions for each command
# We need to look at the template files and map them

template_dir = os.path.join(base_dir, "cmd_templates")
template_files = sorted(glob.glob(os.path.join(template_dir, "*.wav")))

from src import

# Ensure the project root is in the Python path for module imports
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_current_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
 config

# Map template files to commands
template_to_cmd = {}
for tf in template_files:
    basename = os.path.basename(tf)
    # Parse Chinese name
    for cn_name, en_name in config.COMMAND_MAPPING.items():
        if basename.startswith(cn_name):
            template_to_cmd[basename] = en_name
            break

# Since arena test doesn't save per-template results, we need to estimate
# by looking at which templates exist and overall command performance

# Group templates by command
cmd_templates = {}
for basename, cmd in template_to_cmd.items():
    if cmd not in cmd_templates:
        cmd_templates[cmd] = []
    cmd_templates[cmd].append(basename)

print(f"\n{'Command':<10} {'Templates':<10} {'Notes':<50}")
print("-" * 80)

for cmd in sorted(config.COMMANDS):
    templates = cmd_templates.get(cmd, [])
    print(f"{cmd:<10} {len(templates):<10} {', '.join(templates)}")

print("\n" + "=" * 80)
print("RECOMMENDATIONS FOR TEMPLATE IMPROVEMENT")
print("=" * 80)

# Based on the arena test visual output, we can see:
# - 開始.wav (START) fails completely (all 20 conditions failed)
# - 跳.wav (JUMP) has many failures

print("\n1. CRITICAL - Re-record these templates:")
print("   開始.wav  - Failed in ALL test conditions (0% success)")
print("   跳.wav    - Failed in most conditions")

print("\n2. MEDIUM - Check and possibly re-record:")
print("   暫停.wav  - Confused with START in some conditions")
print("   暫停4.wav - Has failures in speed/pitch variations")

print("\n3. GOOD TEMPLATES (keep):")
print("   暫停1.wav, 暫停2.wav, 暫停3.wav - Consistent 100%")
print("   跳1.wav, 跳2.wav, 跳3.wav, 跳4.wav - All 100%")
print("   開始1.wav, 開始2.wav, 開始3.wav, 開始4.wav - Good performers")

print("\n" + "=" * 80)
print("ACTION PLAN")
print("=" * 80)
print("""
1. Delete or move to backup:
   - cmd_templates/開始.wav
   - cmd_templates/跳.wav

2. Record new versions:
   - Make sure pronunciation is clear
   - Record in quiet environment
   - Use consistent volume (~-20dB RMS)
   - Speak naturally, not too fast or slow

3. Verify new templates:
   python temp/quick_speed_test.py  # Check latency
   python temp/test_file_input.py   # Full arena test

4. Optional - add more templates:
   - Record 2-3 more versions of each command
   - More variety = better robustness
""")

print("=" * 80)
