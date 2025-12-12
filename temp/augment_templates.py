"""
音訊模板資料增強腳本
根據 test/arena 的方法對音訊模板進行增強，產生訓練用的變化版本
"""
import os
import numpy as np
import librosa
import soundfile as sf
from pathlib import Path
from typing import List, Tuple, Dict

# 增強參數設定（中量版本，每個模板約 4-6 個變化）
AUGMENTATION_CONFIGS = {
    'speed': [0.85, 1.15],  # 速度變化：稍慢、稍快
    'pitch': [-1.5, 1.5],   # 音高偏移：降低、提高 1.5 半音
    'snr_db': [20, 25],     # 噪音等級：中度噪音、輕度噪音
}

# 組合策略：避免產生過多檔案，選擇有代表性的組合
AUGMENTATION_COMBINATIONS = [
    # (speed, pitch, snr) - None 表示不套用該增強
    {'speed': 0.85, 'pitch': None, 'snr': None},      # 1. 只降速
    {'speed': 1.15, 'pitch': None, 'snr': None},      # 2. 只加速
    {'speed': None, 'pitch': -1.5, 'snr': None},      # 3. 只降音高
    {'speed': None, 'pitch': 1.5, 'snr': None},       # 4. 只升音高
    {'speed': None, 'pitch': None, 'snr': 20},        # 5. 只加中度噪音
    {'speed': 1.0, 'pitch': 1.0, 'snr': 25},          # 6. 輕微組合：稍快+升音高+輕度噪音
]


def apply_speed_change(audio: np.ndarray, rate: float) -> np.ndarray:
    """
    改變音訊速度（使用 librosa time_stretch）

    Args:
        audio: 音訊信號 (float32, [-1, 1])
        rate: 速度倍率 (>1 加快, <1 變慢)

    Returns:
        速度調整後的音訊
    """
    return librosa.effects.time_stretch(audio, rate=rate)


def apply_pitch_shift(audio: np.ndarray, sr: int, n_steps: float) -> np.ndarray:
    """
    改變音訊音高（使用 librosa pitch_shift）

    Args:
        audio: 音訊信號 (float32, [-1, 1])
        sr: 採樣率
        n_steps: 音高偏移量（半音）

    Returns:
        音高調整後的音訊
    """
    return librosa.effects.pitch_shift(audio, sr=sr, n_steps=n_steps)


def add_noise(audio: np.ndarray, snr_db: float) -> np.ndarray:
    """
    添加高斯白噪音

    Args:
        audio: 音訊信號 (float32, [-1, 1])
        snr_db: 信噪比 (dB)，越高表示噪音越小

    Returns:
        添加噪音後的音訊
    """
    # 計算音訊功率
    signal_power = np.mean(audio ** 2)

    # 根據 SNR 計算所需的噪音功率
    # SNR(dB) = 10 * log10(P_signal / P_noise)
    # P_noise = P_signal / 10^(SNR/10)
    noise_power = signal_power / (10 ** (snr_db / 10))

    # 生成高斯噪音
    noise = np.random.normal(0, np.sqrt(noise_power), audio.shape)

    # 添加噪音並限制範圍
    noisy_audio = audio + noise
    return np.clip(noisy_audio, -1.0, 1.0)


def augment_audio(
    audio: np.ndarray,
    sr: int,
    config: Dict[str, float]
) -> Tuple[np.ndarray, str]:
    """
    對音訊套用一組增強操作

    Args:
        audio: 原始音訊信號
        sr: 採樣率
        config: 增強配置 {'speed': float, 'pitch': float, 'snr': float}

    Returns:
        (增強後的音訊, 描述字串)
    """
    augmented = audio.copy()
    description_parts = []

    # 1. 音高偏移（先做，避免影響其他處理）
    if config.get('pitch') is not None:
        pitch = config['pitch']
        augmented = apply_pitch_shift(augmented, sr, pitch)
        description_parts.append(f"pitch{pitch:+.1f}st")

    # 2. 速度調整
    if config.get('speed') is not None:
        speed = config['speed']
        augmented = apply_speed_change(augmented, speed)
        description_parts.append(f"speed{speed:.2f}x")

    # 3. 添加噪音（最後做，模擬真實環境）
    if config.get('snr') is not None:
        snr = config['snr']
        augmented = add_noise(augmented, snr)
        description_parts.append(f"snr{snr}db")

    description = "_".join(description_parts) if description_parts else "original"
    return augmented, description


def process_template_file(
    input_path: Path,
    output_dir: Path,
    sr: int = 16000,
    dry_run: bool = False
) -> List[str]:
    """
    處理單個音訊模板，產生多個增強版本

    Args:
        input_path: 輸入音訊檔案路徑
        output_dir: 輸出目錄
        sr: 目標採樣率
        dry_run: 是否只顯示要產生的檔案而不實際寫入

    Returns:
        產生的檔案列表
    """
    # 讀取原始音訊
    audio, orig_sr = librosa.load(input_path, sr=sr, mono=True)

    # 準備輸出檔名（去除副檔名）
    base_name = input_path.stem  # 例如 "開始" 或 "開始1"

    generated_files = []

    # 對每個增強組合產生檔案
    for i, config in enumerate(AUGMENTATION_COMBINATIONS, 1):
        # 套用增強
        augmented_audio, description = augment_audio(audio, sr, config)

        # 產生輸出檔名
        output_filename = f"{base_name}_aug{i}_{description}.wav"
        output_path = output_dir / output_filename

        if not dry_run:
            # 儲存音訊（轉回 int16 格式）
            sf.write(
                output_path,
                augmented_audio,
                sr,
                subtype='PCM_16'
            )
            generated_files.append(output_filename)
            print(f"[OK] 已產生: {output_filename}")
        else:
            print(f"  [預覽] 將產生: {output_filename}")
            generated_files.append(output_filename)

    return generated_files


def augment_all_templates(
    template_dir: str = "cmd_templates",
    output_subdir: str = "augmented",
    dry_run: bool = False
) -> Dict[str, List[str]]:
    """
    批次處理所有音訊模板

    Args:
        template_dir: 模板目錄路徑
        output_subdir: 輸出子目錄名稱（在 template_dir 下建立）
        dry_run: 預覽模式，不實際寫入檔案

    Returns:
        每個模板產生的檔案清單
    """
    # 準備路徑
    template_path = Path(template_dir)
    output_path = template_path / output_subdir

    if not template_path.exists():
        raise FileNotFoundError(f"模板目錄不存在: {template_path}")

    # 建立輸出目錄
    if not dry_run:
        output_path.mkdir(exist_ok=True)
        print(f"輸出目錄: {output_path}\n")
    else:
        print(f"[預覽模式] 輸出目錄: {output_path}\n")

    # 找出所有 wav 檔案（排除子目錄）
    wav_files = sorted([
        f for f in template_path.glob("*.wav")
        if f.is_file() and "noise" not in f.name.lower()
    ])

    if not wav_files:
        print(f"警告: 在 {template_path} 中找不到 .wav 檔案")
        return {}

    print(f"找到 {len(wav_files)} 個模板檔案\n")
    print("=" * 60)

    # 處理每個模板
    results = {}
    for wav_file in wav_files:
        print(f"\n處理模板: {wav_file.name}")
        print("-" * 60)

        generated = process_template_file(
            wav_file,
            output_path,
            dry_run=dry_run
        )
        results[wav_file.name] = generated

    print("\n" + "=" * 60)
    print(f"完成！共處理 {len(wav_files)} 個模板，產生 {sum(len(v) for v in results.values())} 個增強檔案")

    if dry_run:
        print("\n這是預覽模式。若確認無誤，請執行:")
        print("  python temp/augment_templates.py --execute")

    return results


def main():
    import argparse

    parser = argparse.ArgumentParser(description="音訊模板資料增強工具")
    parser.add_argument(
        '--template-dir',
        default='cmd_templates',
        help='模板目錄路徑 (預設: cmd_templates)'
    )
    parser.add_argument(
        '--output-subdir',
        default='augmented',
        help='輸出子目錄名稱 (預設: augmented)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='預覽模式，不實際產生檔案'
    )
    parser.add_argument(
        '--execute',
        action='store_true',
        help='執行模式，實際產生檔案'
    )

    args = parser.parse_args()

    # 預設為預覽模式，除非指定 --execute
    dry_run = not args.execute

    if dry_run:
        print("\n" + "=" * 60)
        print("預覽模式 - 將顯示要產生的檔案但不實際寫入")
        print("=" * 60 + "\n")

    try:
        augment_all_templates(
            template_dir=args.template_dir,
            output_subdir=args.output_subdir,
            dry_run=dry_run
        )
    except Exception as e:
        print(f"\n錯誤: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
