from ecg_reader import ECGProcessor
import time

proc = ECGProcessor(port="COM4")

while True:
    bpm, ecg = proc.process()

   # if ecg is not None:
        #print("Filtered:", ecg[-1])  # 最新一筆值

    if bpm is not None:
        print("BPM:", bpm)

    time.sleep(0.01)
