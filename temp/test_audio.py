import pyaudio

p = pyaudio.PyAudio()
print(f"PyAudio 版本: {pyaudio.__version__}")

count = p.get_device_count()
print(f"偵測到的裝置總數: {count}")

if count == 0:
    print("❌ 錯誤: PyAudio 找不到任何裝置 (可能是驅動問題或權限完全被擋)")
else:
    print("=== 裝置列表 ===")
    for i in range(count):
        try:
            info = p.get_device_info_by_index(i)
            # 只顯示有「輸入」功能的裝置 (麥克風)
            if info['maxInputChannels'] > 0:
                print(f"ID {i}: {info['name']} (輸入聲道數: {info['maxInputChannels']})")
        except Exception as e:
            print(f"ID {i}: 讀取錯誤 - {e}")

p.terminate()