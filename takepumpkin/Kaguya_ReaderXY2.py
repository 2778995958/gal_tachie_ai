import struct
import os
import csv
import argparse
import io
from PIL import Image, ImageOps

# -----------------------------------------------------------------------------
# 核心解碼與處理函式 (這部分保持不變)
# -----------------------------------------------------------------------------
def save_image_from_pixels(pixel_data, width, height, bpp, flip, output_path, filename):
    """從像素資料建立並儲存圖片的通用函式，並提供執行回饋。"""
    print(f"DEBUG: 準備儲存圖片 '{filename}'，尺寸 W={width}, H={height}, BPP={bpp}")
    if width <= 0 or height <= 0 or not pixel_data:
        print(f"警告: 圖像 '{filename}' 的尺寸或資料無效，儲存被取消。")
        return
    try:
        if bpp == 32: pil_mode, raw_mode = 'RGBA', 'BGRA'
        elif bpp == 24: pil_mode, raw_mode = 'RGB', 'BGR'
        elif bpp == 8: pil_mode, raw_mode = 'L', 'L'
        else:
            print(f"警告: 圖像 '{filename}' 的 BPP ({bpp}) 不支援，儲存被取消。")
            return
        img = Image.frombytes(pil_mode, (width, height), pixel_data, 'raw', raw_mode)
        if flip:
            img = ImageOps.flip(img)
        full_path = os.path.join(output_path, filename)
        img.save(full_path)
        print(f"成功儲存圖片: {full_path}")
    except Exception as e:
        print(f"儲存圖片 '{filename}' 時發生嚴重錯誤: {e}")

def decompress_rle(input_stream, unpacked_size, rle_step):
    """解壓縮交錯式 RLE 數據。"""
    # ... (此函式內容與前一版完全相同，為求簡潔故省略) ...
    output = bytearray(unpacked_size)
    for i in range(rle_step):
        if input_stream.tell() >= len(input_stream.getbuffer()): break
        v1 = int.from_bytes(input_stream.read(1), 'little')
        if i < len(output): output[i] = v1
        dst = i + rle_step
        while dst < unpacked_size:
            if input_stream.tell() >= len(input_stream.getbuffer()): break
            v2 = int.from_bytes(input_stream.read(1), 'little')
            output[dst] = v2
            dst += rle_step
            if v2 == v1:
                if input_stream.tell() >= len(input_stream.getbuffer()): break
                count = int.from_bytes(input_stream.read(1), 'little')
                if (count & 0x80) != 0:
                    if input_stream.tell() >= len(input_stream.getbuffer()): break
                    count = int.from_bytes(input_stream.read(1), 'little') + ((count & 0x7F) << 8) + 128
                for _ in range(count):
                    if dst >= unpacked_size: break
                    output[dst] = v2
                    dst += rle_step
                if dst < unpacked_size:
                    if input_stream.tell() >= len(input_stream.getbuffer()): break
                    v2 = int.from_bytes(input_stream.read(1), 'little')
                    output[dst] = v2
                    dst += rle_step
            v1 = v2
    return output

# -----------------------------------------------------------------------------
# 各版本檔案的處理器 (這部分保持不變)
# -----------------------------------------------------------------------------
def handle_an00_an10_pl00(f, output_path, base_name, signature, source_filename):
    """處理 AN00, AN10, 和 PL00 格式。"""
    # ... (此函式內容與前一版完全相同，為求簡潔故省略) ...
    print(f"DEBUG: 進入 {signature.decode()} 格式處理器。")
    coords_list = []
    if signature == b'AN00':
        f.seek(4); base_x, base_y = struct.unpack('<ii', f.read(8))
    else:
        f.seek(0x06 if signature == b'PL00' else 0x04); base_x, base_y, _, _ = struct.unpack('<iiII', f.read(16))
    if signature == b'PL00':
        f.seek(4); image_count = struct.unpack('<h', f.read(2))[0]; current_offset = 0x16
    else:
        f.seek(20); table_count = struct.unpack('<h', f.read(2))[0]; image_count_offset = 0x18 + table_count * 4
        f.seek(image_count_offset); image_count = struct.unpack('<h', f.read(2))[0]; current_offset = image_count_offset + 2
    if image_count <= 0: return []
    for i in range(image_count):
        f.seek(current_offset)
        header_format = '<iiII' if signature == b'AN00' else '<iiIII'
        header_size = struct.calcsize(header_format); header_bytes = f.read(header_size)
        if len(header_bytes) < header_size: break
        frame_header = struct.unpack(header_format, header_bytes)
        frame_offset_x, frame_offset_y, width, height = frame_header[0:4]
        channels = 4 if signature == b'AN00' else frame_header[4]
        bpp = channels * 8; final_x = base_x + frame_offset_x; final_y = base_y + frame_offset_y
        coords_list.append({'source_file': source_filename, 'frame': i, 'x': final_x, 'y': final_y, 'width': width, 'height': height, 'bpp': bpp})
        pixel_data_offset = current_offset + header_size; bytes_to_read = width * height * channels
        f.seek(pixel_data_offset); pixel_data = f.read(bytes_to_read)
        save_image_from_pixels(pixel_data, width, height, bpp, True, output_path, f"{base_name}_{i:03d}.png")
        current_offset = pixel_data_offset + len(pixel_data)
    return coords_list

def handle_an20(f, output_path, base_name, signature, source_filename):
    """專門處理 AN20 動畫格式。"""
    # ... (此函式內容與前一版完全相同，為求簡潔故省略) ...
    coords_list = []; f.seek(0); data = f.read(); f.seek(4); table_count = struct.unpack('<h', f.read(2))[0]; pos = 8
    for _ in range(table_count):
        byte_val = data[pos]; pos += 1
        if byte_val == 1: pos += 8
        elif byte_val in [2, 3, 4, 5]: pos += 4
    count = struct.unpack('<H', data[pos:pos+2])[0]; pos += 2; pos += count * 8; f.seek(pos + 2)
    base_x, base_y, _, _ = struct.unpack('<iiII', f.read(16)); f.seek(pos); image_count = struct.unpack('<h', f.read(2))[0]
    if image_count <= 0: return []
    current_offset = f.tell() + 0x10; header_format = '<iiIII'; header_size = struct.calcsize(header_format)
    for i in range(image_count):
        f.seek(current_offset); header_bytes = f.read(header_size)
        if len(header_bytes) < header_size: break
        frame_offset_x, frame_offset_y, width, height, channels = struct.unpack(header_format, header_bytes)
        bpp = channels * 8; final_x = base_x + frame_offset_x; final_y = base_y + frame_offset_y
        coords_list.append({'source_file': source_filename, 'frame': i, 'x': final_x, 'y': final_y, 'width': width, 'height': height, 'bpp': bpp})
        pixel_data_offset = current_offset + header_size; f.seek(pixel_data_offset); pixel_data = f.read(width * height * channels)
        save_image_from_pixels(pixel_data, width, height, bpp, True, output_path, f"{base_name}_{i:03d}.png")
        current_offset = pixel_data_offset + len(pixel_data)
    return coords_list

def handle_rle_animation(f, output_path, base_name, signature, source_filename):
    """處理 AN21 (RLE) 和 PL10 (RLE) 動畫格式。"""
    # ... (此函式內容與前一版完全相同，為求簡潔故省略) ...
    coords_list = []
    if signature == b'AN21':
        try:
            f.seek(4); table_count = struct.unpack('<H', f.read(2))[0]; f.seek(2, 1)
            for _ in range(table_count):
                command = f.read(1)[0]
                if command == 1: f.seek(8, 1)
                else: f.seek(4, 1)
            count2 = struct.unpack('<H', f.read(2))[0]
            if count2 == 1: f.seek(8, 1)
            if f.read(7) != b'[PIC]10': raise ValueError("無效的 AN21 簽名, 未找到 [PIC]10")
            frame_count = struct.unpack('<h', f.read(2))[0]
            global_l, global_t, _, _ = struct.unpack('<iiii', f.read(16))
            frame_l, frame_t, w, h, channels = struct.unpack('<iiIIi', f.read(20))
            is_special_file = '乳' in source_filename or '胸' in source_filename
            if is_special_file: final_x, final_y = global_l, global_t
            else: final_x, final_y = global_l + frame_l, global_t + frame_t
            bpp = channels * 8; previous_frame_pixels = None; unpacked_size = w * h * channels
            for i in range(frame_count):
                coords_list.append({'source_file': source_filename, 'frame': i, 'x': final_x, 'y': final_y, 'width': w, 'height': h, 'bpp': bpp})
                if i == 0: pixels = f.read(unpacked_size)
                else:
                    rle_step = f.read(1)[0]; packed_size = struct.unpack('<I', f.read(4))[0]
                    compressed_data = f.read(packed_size); delta_pixels = decompress_rle(io.BytesIO(compressed_data), unpacked_size, rle_step)
                    pixels = bytes((p + d) & 0xFF for p, d in zip(previous_frame_pixels, delta_pixels))
                previous_frame_pixels = pixels
                save_image_from_pixels(pixels, w, h, bpp, True, output_path, f"{base_name}_{i:03d}.png")
            return coords_list
        except Exception as e:
            print(f"處理 AN21 檔案 '{source_filename}' 時發生嚴重錯誤: {e}"); return []
    else: print(f"警告: PL10 處理邏輯在此版本中未完整實現。"); return []

def handle_ap_formats(f, output_path, base_name, signature, source_filename):
    """處理 AP, AP-0, AP-2, AP-3 靜態圖片格式。"""
    # ... (此函式內容與前一版完全相同，為求簡潔故省略) ...
    offset_x, offset_y = 0, 0
    flip = True
    if signature == b'AP':
        f.seek(2); width, height, _ = struct.unpack('<IIh', f.read(10)); bpp = 32
        print(f"DEBUG: AP 格式，強制使用 32 BPP。")
    elif signature == b'AP-0':
        f.seek(4); width, height = struct.unpack('<II', f.read(8)); bpp = 8; f.seek(12)
    elif signature == b'AP-2':
        f.seek(4); offset_x, offset_y, width, height = struct.unpack('<iiII', f.read(16)); bpp = 32; f.seek(0x18)
    elif signature == b'AP-3':
        f.seek(4); offset_x, offset_y, width, height = struct.unpack('<iiII', f.read(16)); bpp = struct.unpack('<i', f.read(4))[0]; f.seek(0x18)
    else:
        print(f"警告: 在 handle_ap_formats 中遇到未知的簽名 '{signature}'"); return []
    bytes_per_pixel = bpp // 8
    if bytes_per_pixel <= 0:
        print(f"警告: BPP 值 ({bpp}) 無效，無法讀取像素。"); return []
    pixel_data = f.read(width * height * bytes_per_pixel)
    save_image_from_pixels(pixel_data, width, height, bpp, flip, output_path, f"{base_name}.png")
    return [{'source_file': source_filename, 'frame': 0, 'x': offset_x, 'y': offset_y, 'width': width, 'height': height, 'bpp': bpp}]

# -----------------------------------------------------------------------------
# 主程式
# -----------------------------------------------------------------------------
def process_file(filepath, output_dir):
    """處理單一檔案，並返回其座標資訊。"""
    # ... (此函式內容與前一版完全相同，為求簡潔故省略) ...
    base_name = os.path.splitext(os.path.basename(filepath))[0]
    source_filename = os.path.basename(filepath)
    handlers = {
        b'AN00': handle_an00_an10_pl00, b'AN10': handle_an00_an10_pl00, b'PL00': handle_an00_an10_pl00,
        b'AN20': handle_an20,
        b'AN21': handle_rle_animation, b'PL10': handle_rle_animation,
        b'AP-0': handle_ap_formats, b'AP-2': handle_ap_formats, b'AP-3': handle_ap_formats,
        b'AP': handle_ap_formats,
    }
    try:
        with open(filepath, 'rb') as f:
            sig_bytes = f.read(4)
            f.seek(0)
            sig_to_use = None
            if sig_bytes in handlers: sig_to_use = sig_bytes
            elif sig_bytes[:3] in handlers: sig_to_use = sig_bytes[:3]
            elif sig_bytes[:2] in handlers: sig_to_use = sig_bytes[:2]
            handler = handlers.get(sig_to_use)
            if handler:
                print(f"處理中: {source_filename} (偵測到格式: {sig_to_use.decode(errors='ignore')})")
                return handler(f, output_dir, base_name, sig_to_use, source_filename)
            else:
                return []
    except IOError as e:
        print(f"錯誤: 無法讀取檔案 {source_filename}: {e}"); return []
    except Exception as e:
        print(f"處理檔案 {source_filename} 時發生未預期的錯誤: {e}"); return []


# 【修改】main 函式已更新，將輸出路徑與 py 檔綁定
def main():
    """主程式入口"""
    parser = argparse.ArgumentParser(description="[整合修正版 v7] 轉換 Kaguya 引擎資源檔為 PNG 和單一 CSV。", formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("input_path", help="輸入的資源檔案，或包含這些檔案的目錄路徑。")
    args = parser.parse_args()

    # --- 1. 獲取腳本所在的目錄 ---
    # `__file__` 是 Python 的一個特殊變數，代表當前腳本的路徑。
    # `os.path.abspath` 將其轉為絕對路徑，`os.path.dirname` 提取目錄部分。
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        # 如果在某些互動式環境中執行，__file__ 可能未定義，則使用當前工作目錄
        script_dir = os.getcwd()

    # --- 2. 將輸出資料夾的路徑設定在腳本目錄下 ---
    output_dir = os.path.join(script_dir, "output")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    print(f"所有圖片將輸出到: {output_dir}")

    # --- 輸入檔案路徑處理 ---
    if not os.path.exists(args.input_path):
        print(f"錯誤: 找不到輸入路徑 '{args.input_path}'"); return

    if os.path.isdir(args.input_path):
        input_dir_path = args.input_path
        files_to_process = [os.path.join(input_dir_path, f) for f in sorted(os.listdir(input_dir_path)) if os.path.isfile(os.path.join(input_dir_path, f))]
    else:
        files_to_process = [args.input_path]
        
    if not files_to_process:
        print("在指定路徑中找不到任何檔案。"); return

    # --- 處理與寫入 CSV ---
    master_coords_list = []
    total = len(files_to_process)
    print(f"找到 {total} 個檔案進行處理。")
    processed_count = 0
    for i, filepath in enumerate(files_to_process):
        try:
            coords = process_file(filepath, output_dir)
            if coords:
                processed_count += 1
                master_coords_list.extend(coords)
        except Exception as e:
            print(f"處理檔案 {os.path.basename(filepath)} 時發生嚴重錯誤: {e}")

    print(f"\n--- 處理完畢 ---")
    print(f"成功處理 {processed_count} 個支援的檔案。")

    if master_coords_list:
        # --- 3. 將 CSV 檔案的路徑也設定在腳本目錄下 ---
        csv_path = os.path.join(script_dir, "master_coordinates.csv")
        try:
            fieldnames = ['source_file', 'frame', 'x', 'y', 'width', 'height', 'bpp']
            with open(csv_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(master_coords_list)
            print(f"成功將所有座標資訊寫入: {csv_path}")
        except Exception as e:
            print(f"寫入主 CSV 檔案時發生錯誤: {e}")

if __name__ == "__main__":
    main()