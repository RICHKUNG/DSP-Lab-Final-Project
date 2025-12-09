import os
import numpy as np
import librosa
import soundfile as sf

def extract_noise(input_file, output_file, duration=0.5):
    try:
        y, sr = librosa.load(input_file, sr=None)
        
        # Frame size for energy calculation (e.g., 50ms)
        frame_length = int(sr * 0.05)
        hop_length = int(sr * 0.025)
        
        rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
        
        # Find the window of 'duration' with minimum average energy
        window_frames = int(duration / 0.025)
        if len(rms) < window_frames:
            print(f"File {input_file} too short for noise extraction.")
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
        print(f"Generated {output_file} from {input_file} (Energy: {min_energy:.6f})")
        
    except Exception as e:
        print(f"Error processing {input_file}: {e}")

def main():
    source_dir = 'cmd_templates'
    if not os.path.exists(source_dir):
        print(f"Directory {source_dir} not found.")
        return

    # Files to extract noise from
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
