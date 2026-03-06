#!/usr/bin/env python3
import struct
import sys
from PIL import Image

def decode_qoi(data, pos, width, height):
    index = [(0, 0, 0, 0)] * 64
    px = (0, 0, 0, 255)
    pixels = []

    while len(pixels) < width * height and pos < len(data):
        b1 = data[pos]; pos += 1

        if b1 == 0xFE:
            px = (data[pos], data[pos+1], data[pos+2], px[3]); pos += 3
            count = 1
        elif b1 == 0xFF:
            px = (data[pos], data[pos+1], data[pos+2], data[pos+3]); pos += 4
            count = 1
        elif (b1 & 0xC0) == 0x00:
            px = index[b1 & 0x3F]
            count = 1
        elif (b1 & 0xC0) == 0x40:
            px = ((px[0]+((b1>>4)&3)-2)&0xFF, (px[1]+((b1>>2)&3)-2)&0xFF,
                  (px[2]+(b1&3)-2)&0xFF, px[3])
            count = 1
        elif (b1 & 0xC0) == 0x80:
            b2 = data[pos]; pos += 1
            dg = (b1 & 0x3F) - 32
            px = ((px[0]+dg+((b2>>4)&0xF)-8)&0xFF, (px[1]+dg)&0xFF,
                  (px[2]+dg+(b2&0xF)-8)&0xFF, px[3])
            count = 1
        else:
            count = (b1 & 0x3F) + 1

        index[(px[0]*3+px[1]*5+px[2]*7+px[3]*11) % 64] = px
        for _ in range(count):
            if len(pixels) < width * height:
                pixels.append(px)

    return pixels

def decode_tlg(filename):
    with open(filename, 'rb') as f:
        data = f.read()

    if data[:11] != b'TLGqoi\x00raw\x1a':
        print(f"錯誤：不是 TLGqoi 格式")
        return

    width = struct.unpack_from('<I', data, 12)[0]
    height = struct.unpack_from('<I', data, 16)[0]

    pixels = decode_qoi(data, 28, width, height)

    img_data = b''.join(bytes(p) for p in pixels)
    img = Image.frombytes('RGBA', (width, height), img_data)

    out = filename.rsplit('.', 1)[0] + '.png'
    img.save(out)
    print(f"已儲存：{out} ({width}x{height})")

if __name__ == '__main__':
    import glob
    if len(sys.argv) < 2:
        files = glob.glob('*.tlg')
        if not files:
            print("目錄中沒有 .tlg 檔案")
            input("按 Enter 結束...")
            sys.exit(1)
        print(f"找到 {len(files)} 個檔案")
        for f in files:
            try:
                decode_tlg(f)
            except Exception as e:
                print(f"失敗：{f} - {e}")
        input("完成！按 Enter 結束...")
    else:
        for f in sys.argv[1:]:
            decode_tlg(f)
