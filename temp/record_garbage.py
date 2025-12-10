import os
import time
import soundfile as sf
from src.audio_io import AudioStream, find_suitable_device
from src import config

def record_garbage():
    print("="*60)
    print("Human Noise Recorder (Garbage Class Collector)")
    print("="*60)
    print("This tool helps you record human sounds that should be IGNORED.")
    print("Examples: Coughs, Laughs, 'Uhh', 'Bruh', Sighs, Claps")
    print("-" * 60)

    # Setup Audio
    device_info = find_suitable_device(config.SAMPLE_RATE, verbose=False)
    if device_info is None:
        print("No microphone found.")
        return
    
    idx, rate = device_info
    stream = AudioStream(idx, rate, config.SAMPLE_RATE)
    stream.start()

    # Ensure directory exists
    os.makedirs('cmd_templates', exist_ok=True)

    try:
        count = 1
        while True:
            name = input(f"\n[{count}] Label for this noise (e.g. 'laugh', 'cough') [Press Enter to skip/quit]: ").strip()
            if not name:
                break
            
            filename = f"noise_human_{name}_{int(time.time())}.wav"
            filepath = os.path.join('cmd_templates', filename)
            
            print(f"   Recording '{name}' in 3 seconds... Get ready!")
            time.sleep(1)
            print("   2...")
            time.sleep(1)
            print("   1...")
            time.sleep(1)
            print("   >>> RECORDING (1.5s) <<<")
            
            # Record 1.5 seconds
            stream.get_chunk() # clear buffer
            frames = []
            rec_start = time.time()
            while time.time() - rec_start < 1.5:
                chunk = stream.get_chunk()
                if len(chunk) > 0:
                    frames.extend(chunk)
            
            # Save
            import numpy as np
            audio_data = np.array(frames, dtype=np.int16)
            sf.write(filepath, audio_data, config.SAMPLE_RATE)
            print(f"   Saved: {filepath}")
            count += 1

    except KeyboardInterrupt:
        pass
    finally:
        stream.stop()
        print("\nDone. These files will now be loaded as NOISE templates.")

if __name__ == "__main__":
    record_garbage()
