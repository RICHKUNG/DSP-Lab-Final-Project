import os
import numpy as np
import soundfile as sf

print("Starting noise extraction...")

def extract_noise(input_file, output_file, duration=0.5):
    try:
        y, sr = sf.read(input_file)
        if len(y.shape) > 1:
            y = y.mean(axis=1) # Convert to mono if needed
            
        # Frame size for energy calculation (e.g., 50ms)
        frame_length = int(sr * 0.05)
        hop_length = int(sr * 0.025)
        
        rms = []
        for i in range(0, len(y) - frame_length, hop_length):
            frame = y[i:i+frame_length]
            rms.append(np.sqrt(np.mean(frame**2)))
        
        rms = np.array(rms)
        
        # Find the window of 'duration' with minimum average energy
        window_frames = int(duration / 0.025)
        if len(rms) < window_frames:
            print(f"File {input_file} too short.")
            return

        min_energy = float('inf')
        best_start_frame = 0
        
        for i in range(len(rms) - window_frames):
            current_energy = np.mean(rms[i:i+window_frames])
            if current_energy < min_energy:
                min_energy = current_energy
                best_start_frame = i
        
        # Convert frame index back to samples
        start_sample = best_start_frame * hop_length
        end_sample = start_sample + int(duration * sr)
        
        noise_segment = y[start_sample:end_sample]
        
        sf.write(output_file, noise_segment, sr)
        print(f"Generated {output_file} (Energy: {min_energy:.6f})")
        
    except Exception as e:
        print(f"Error processing {input_file}: {e}")

def main():
    source_dir = 'cmd_templates'
    sources = [
        '開始1.wav', '開始2.wav', 
        '跳1.wav', '跳2.wav',
        '暫停1.wav', '暫停2.wav'
    ]
    
    for i, filename in enumerate(sources):
        input_path = os.path.join(source_dir, filename)
        if os.path.exists(input_path):
            output_filename = f"noise_gen_{i+1}.wav"
            output_path = os.path.join(source_dir, output_filename)
            extract_noise(input_path, output_path)

if __name__ == "__main__":
    main()
