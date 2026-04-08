"""
YDG (YU-RIS engine) -> PNG 轉換工具

YDG 格式結構：
  0x00: "YDG\0"          (4 bytes magic)
  0x04: "YU-RIS\0\0"     (8 bytes engine tag)
  0x20: width, height     (2+2 bytes LE, full image dimensions)
  0x30: layer count       (4 bytes LE)
  0x34: layer table, each entry 16 bytes:
        - data offset (4 bytes LE)
        - data size   (4 bytes LE)
        - format      (2 bytes LE)
        - strip height(2 bytes LE)
        - reserved    (4 bytes)
  Data area: each layer is a WebP image (horizontal strip)
"""

import struct
import sys
import os
import io
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("錯誤：需要 Pillow。請執行 pip install Pillow")
    sys.exit(1)


SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_ROOT = SCRIPT_DIR / "output"


def extract_ydg(ydg_path, output_dir):
    ydg_path = Path(ydg_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(ydg_path, "rb") as f:
        data = f.read()

    if data[0:4] != b"YDG\x00":
        print(f"錯誤：不是 YDG 檔案")
        return

    full_w, full_h = struct.unpack_from("<HH", data, 0x20)
    layer_count = struct.unpack_from("<I", data, 0x30)[0]

    # 解析圖層索引表
    layers = []
    for i in range(layer_count):
        entry_off = 0x34 + i * 16
        offset, size = struct.unpack_from("<II", data, entry_off)
        layers.append((offset, size))

    # 讀取每個圖層（水平切片）
    images = []
    for i, (offset, size) in enumerate(layers):
        chunk = data[offset : offset + size]
        try:
            img = Image.open(io.BytesIO(chunk))
            img = img.convert("RGBA")
            images.append(img)
        except Exception as e:
            print(f"  圖層 {i} 讀取失敗: {e}")

    if not images:
        return

    # 垂直拼接所有切片
    total_w = max(img.size[0] for img in images)
    total_h = sum(img.size[1] for img in images)
    merged = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
    y = 0
    for img in images:
        merged.paste(img, (0, y))
        y += img.size[1]

    out_path = output_dir / f"{ydg_path.stem}.png"
    merged.save(str(out_path), "PNG")
    print(f"{ydg_path.name} -> {out_path.name} ({total_w}x{total_h})")
    return str(out_path)


def batch_convert(input_dir):
    input_dir = Path(input_dir).resolve()
    ydg_files = sorted(input_dir.rglob("*.ydg"))
    print(f"找到 {len(ydg_files)} 個 YDG 檔案\n")

    for ydg_file in ydg_files:
        # 以腳本目錄為基準保持來源結構
        try:
            rel = ydg_file.parent.relative_to(SCRIPT_DIR)
        except ValueError:
            rel = ydg_file.parent.relative_to(input_dir)
        out = OUTPUT_ROOT / rel
        extract_ydg(ydg_file, out)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print(f"  python {sys.argv[0]} <file.ydg>    # 轉換單一檔案")
        print(f"  python {sys.argv[0]} <directory>   # 批次轉換資料夾")
        print(f"\n輸出至腳本同目錄的 output/ 資料夾")
        sys.exit(1)

    target = sys.argv[1]

    if os.path.isdir(target):
        batch_convert(target)
    elif os.path.isfile(target):
        target = Path(target)
        out = OUTPUT_ROOT / target.parent.name
        extract_ydg(target, out)
    else:
        print(f"錯誤：找不到 {target}")
        sys.exit(1)
