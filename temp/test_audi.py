import pyaudio
import wave

pa = pyaudio.PyAudio()

print("=== 列出所有輸入裝置 ===")
target_index = None
target_info = None

for i in range(pa.get_device_count()):
    info = pa.get_device_info_by_index(i)
    if info["maxInputChannels"] > 0:
        print(f"Index {i}: {info['name']} | maxInputChannels={info['maxInputChannels']} | defaultRate={info['defaultSampleRate']}")
        # 只要名稱裡含有「麥克風排列」就當候選
        if "麥克風排列" in info["name"]:
            # 挑第一個符合的就好，你之後如果要更精細再改
            if target_index is None:
                target_index = i
                target_info = info

if target_index is None:
    print("沒有找到名稱含『麥克風排列』的輸入裝置 QQ")
    pa.terminate()
    raise SystemExit

print("\n✅ 準備使用的麥克風排列裝置：")
print(f"Index {target_index}: {target_info['name']}")
print(f"maxInputChannels={target_info['maxInputChannels']}, defaultRate={target_info['defaultSampleRate']}")

# 這裡我們用裝置自己的 default sample rate & 至多 2 聲道
RATE = int(target_info["defaultSampleRate"])
CHANNELS = min(2, int(target_info["maxInputChannels"]))  # 4 聲道就先用 2 聲道
FORMAT = pyaudio.paInt16
SECONDS = 3
OUTPUT_FILE = "mic_array_test.wav"

print(f"\n開啟 Stream... (rate={RATE}, channels={CHANNELS})")
stream = pa.open(
    format=FORMAT,
    channels=CHANNELS,
    rate=RATE,
    input=True,
    input_device_index=target_index,
    frames_per_buffer=1024,
)

print("開始錄音 3 秒，對麥克風講話...")
frames = []
for _ in range(0, int(RATE / 1024 * SECONDS)):
    data = stream.read(1024, exception_on_overflow=False)
    frames.append(data)

print("錄音結束，關閉裝置...")
stream.stop_stream()
stream.close()
pa.terminate()

wf = wave.open(OUTPUT_FILE, 'wb')
wf.setnchannels(CHANNELS)
wf.setsampwidth(2)  # paInt16 -> 2 bytes
wf.setframerate(RATE)
wf.writeframes(b"".join(frames))
wf.close()

print(f"✅ 已儲存為 {OUTPUT_FILE}，用播放器打開聽聽看。")
