import os
import shutil
import glob

def swap_templates():
    template_dir = 'cmd_templates'
    
    # 1. Handle START (開始)
    # Find the file that is likely "開始.wav" (Start)
    # Based on previous ls, it was ~368718 bytes
    start_candidates = glob.glob(os.path.join(template_dir, '**.wav')) # Heuristic matching for mojibake
    # Or better, find files that do NOT have a number at the end, but match the start pattern
    
    # Let's rely on the file sizes we saw earlier to identify them safely
    # Start (bad): 368718
    # Start1 (good): 361004
    
    # Pause (bad): 393294
    # Pause1 (good): 391724
    
    files = glob.glob(os.path.join(template_dir, '*.wav'))
    
    start_bad = None
    start_good = None
    pause_bad = None
    pause_good = None
    
    for f in files:
        size = os.path.getsize(f)
        if size == 368718:
            start_bad = f
        elif size == 361004:
            start_good = f
        elif size == 393294:
            pause_bad = f
        elif size == 391724:
            pause_good = f
            
    if start_bad and start_good:
        print(f"Swapping Start: {start_bad} <-> {start_good}")
        # Backup bad
        shutil.copy2(start_bad, start_bad + ".bak")
        # Overwrite bad with good
        shutil.copy2(start_good, start_bad)
        print("Start swapped.")
    else:
        print(f"Could not find exact Start files. Found: Bad={start_bad}, Good={start_good}")

    if pause_bad and pause_good:
        print(f"Swapping Pause: {pause_bad} <-> {pause_good}")
        # Backup bad
        shutil.copy2(pause_bad, pause_bad + ".bak")
        # Overwrite bad with good
        shutil.copy2(pause_good, pause_bad)
        print("Pause swapped.")
    else:
        print(f"Could not find exact Pause files. Found: Bad={pause_bad}, Good={pause_good}")

if __name__ == '__main__':
    swap_templates()
