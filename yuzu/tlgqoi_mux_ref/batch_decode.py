#!/usr/bin/env python3
import struct
import glob
import os
from multiprocessing import Pool, cpu_count
from PIL import Image

def decode_qoi_data(data, width, height):
    pixels = []
    index = [bytes([0, 0, 0, 0])] * 64
    px = bytes([0, 0, 0, 255])
    run = 0
    pos = 0

    while len(pixels) < width * height and pos < len(data):
        if run > 0:
            pixels.append(px)
            run -= 1
            continue
        if pos >= len(data): break
        b1 = data[pos]
        pos += 1
        if b1 == 0xfe:
            if pos + 3 > len(data): break
            r, g, b = data[pos:pos+3]
            pos += 3
            px = bytes([r, g, b, px[3]])
        elif b1 == 0xff:
            if pos + 4 > len(data): break
            r, g, b, a = data[pos:pos+4]
            pos += 4
            px = bytes([r, g, b, a])
        elif (b1 & 0xc0) == 0x00:
            px = index[b1]
        elif (b1 & 0xc0) == 0x40:
            dr = ((b1 >> 4) & 0x03) - 2
            dg = ((b1 >> 2) & 0x03) - 2
            db = (b1 & 0x03) - 2
            px = bytes([(px[0] + dr) & 0xff, (px[1] + dg) & 0xff, (px[2] + db) & 0xff, px[3]])
        elif (b1 & 0xc0) == 0x80:
            if pos >= len(data): break
            b2 = data[pos]
            pos += 1
            dg = (b1 & 0x3f) - 32
            dr = dg + ((b2 >> 4) & 0x0f) - 8
            db = dg + (b2 & 0x0f) - 8
            px = bytes([(px[0] + dr) & 0xff, (px[1] + dg) & 0xff, (px[2] + db) & 0xff, px[3]])
        elif (b1 & 0xc0) == 0xc0:
            run = (b1 & 0x3f)
        index[(px[0] * 3 + px[1] * 5 + px[2] * 7 + px[3] * 11) % 64] = px
        pixels.append(px)
    while len(pixels) < width * height:
        pixels.append(px)
    return b''.join(pixels)

def process_file(filename):
    try:
        with open(filename, 'rb') as f:
            data = f.read()

        pos = 19 + 1
        pos += 4
        entry_size = struct.unpack('<I', data[pos:pos+4])[0]
        pos += 4
        entry_count = struct.unpack('<I', data[pos:pos+4])[0]
        pos += 4

        # Find the base offset where tile data starts (first TLGqoi marker)
        base_offset = data.find(b'TLGqoi\x00raw\x1a')
        if base_offset == -1:
            return f"FAIL {os.path.basename(filename)}: No TLGqoi data found"

        entries = []
        for i in range(entry_count):
            entry = data[pos:pos+24]
            x = struct.unpack('<I', entry[0:4])[0]
            y = struct.unpack('<I', entry[4:8])[0]
            w = struct.unpack('<I', entry[8:12])[0]
            h = struct.unpack('<I', entry[12:16])[0]
            tile_offset = struct.unpack('<I', entry[16:20])[0]
            entries.append((x, y, w, h, tile_offset))
            pos += 24

        max_x = max(x + w for x, y, w, h, _ in entries)
        max_y = max(y + h for x, y, w, h, _ in entries)

        canvas = Image.new('RGBA', (max_x, max_y), (0, 0, 0, 0))

        for i, (x, y, w, h, tile_offset) in enumerate(entries):
            tile_start = base_offset + tile_offset
            if tile_start + 28 > len(data): continue
            if data[tile_start:tile_start+11] != b'TLGqoi\x00raw\x1a': continue

            qoi_data = data[tile_start + 28:]
            pixels = decode_qoi_data(qoi_data, w, h)
            tile_img = Image.frombytes('RGBA', (w, h), pixels)
            canvas.paste(tile_img, (x, y))

        out_dir = os.path.join(os.path.dirname(filename), 'output')
        os.makedirs(out_dir, exist_ok=True)
        output = os.path.join(out_dir, os.path.basename(filename).replace('.tlg', '.png'))
        canvas.save(output)
        return f"OK {os.path.basename(filename)}"
    except Exception as e:
        return f"FAIL {os.path.basename(filename)}: {e}"

if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')

    # Auto-detect: use argv[1] as directory, or current working directory
    if len(sys.argv) > 1 and os.path.isdir(sys.argv[1]):
        work_dir = sys.argv[1]
    else:
        work_dir = os.getcwd()

    files = glob.glob(os.path.join(glob.escape(work_dir), "*.tlg"))
    # Filter: only TLGmux files (skip TLGref, TLGqoi+QHDR)
    mux_files = []
    for fn in files:
        with open(fn, 'rb') as f:
            sig = f.read(6)
        if sig == b'TLGmux':
            mux_files.append(fn)

    print(f"找到 {len(mux_files)} 個 TLGmux 檔案 (in {work_dir})")

    with Pool(cpu_count()) as pool:
        results = pool.map(process_file, mux_files)

    for result in results:
        print(result)

    input("按 Enter 結束...")
