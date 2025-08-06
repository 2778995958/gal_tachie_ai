import sys
import os
import struct
import csv
import glob
from PIL import Image

class S25Decoder:
    def __init__(self, filepath, image_output_dir):
        self.filepath = filepath
        self.image_output_dir = image_output_dir
        self.file = open(filepath, 'rb')
        self.base_name = os.path.splitext(os.path.basename(filepath))[0]

    def __del__(self):
        if hasattr(self, 'file') and self.file:
            self.file.close()

    def decode(self):
        print(f"--- 開始處理檔案: {os.path.basename(self.filepath)} ---")
        sig = self.file.read(4)
        if sig != b'S25\0':
            print("  錯誤: 檔案簽名不符，跳過此檔案。")
            return [], []
        try:
            frame_count, = struct.unpack('<i', self.file.read(4))
            if not (0 <= frame_count < 10000): # 允許 0 個畫格
                print(f"  警告: 畫格數量為 {frame_count}。")
                if frame_count < 0: return [], []
            frame_offsets = list(struct.unpack(f'<{frame_count}I', self.file.read(4 * frame_count)))
            print(f"  找到 {len(frame_offsets)} 個畫格。")
        except struct.error:
            print("  錯誤: 讀取檔案標頭失敗，檔案可能已損壞。")
            return [], []

        all_frames_metadata = []
        decoded_frames = []
        for i, offset in enumerate(frame_offsets):
            if offset == 0:
                continue
            try:
                image, metadata = self._decode_frame(i, offset, frame_offsets)
                png_filename = f"{self.base_name}_{i}.png"
                output_image_path = os.path.join(self.image_output_dir, png_filename)
                image.save(output_image_path, 'PNG')
                all_frames_metadata.append(metadata)
                decoded_frames.append({'image': image, 'metadata': metadata})
            except Exception as e:
                print(f"    錯誤: 解碼畫格 {i} 失敗: {e}")
        print(f"--- 完成檔案: {os.path.basename(self.filepath)} ---")
        return all_frames_metadata, decoded_frames

    def _decode_frame(self, frame_index, frame_offset, all_frame_offsets):
        self.file.seek(frame_offset)
        width, height, offset_x, offset_y, flags = struct.unpack('<IIiiI', self.file.read(20))
        is_incremental = (flags & 0x80000000) != 0
        png_basename = f"{self.base_name}_{frame_index}"
        metadata = {'frame_index': png_basename, 'width': width, 'height': height, 'offset_x': offset_x, 'offset_y': offset_y}
        
        row_offsets = list(struct.unpack(f'<{height}I', self.file.read(4 * height)))
        pixel_buffer = bytearray(width * height * 4)

        if not is_incremental:
            # ===================================================================
            # === 重構部分：直接操作 pixel_buffer，與 C# 邏輯完全一致 ===
            # ===================================================================
            current_dst_pos = 0
            for y in range(height):
                row_pos_ptr = row_offsets[y]
                if row_pos_ptr == 0:
                    current_dst_pos += width * 4 # 如果行為空，則跳過整行
                    continue

                self.file.seek(row_pos_ptr)
                row_length, = struct.unpack('<H', self.file.read(2))
                row_pos_ptr += 2
                
                # C# 原始碼中沒有這個對齊，但在某些檔案中似乎是必要的
                # 為了保守起見，我們先移除它，因為原始碼中沒有
                # if row_pos_ptr & 1:
                #    self.file.read(1)
                #    row_length -=1

                compressed_data = self.file.read(row_length)
                self._unpack_line(compressed_data, width, pixel_buffer, current_dst_pos)
                current_dst_pos += width * 4
        else:
            # 增量解壓縮邏輯 (維持原樣，因為目前遇到的問題檔案非此類)
            rows_count = {}
            for offset in row_offsets: rows_count[offset] = rows_count.get(offset, 0) + 1
            self._update_repeat_count(rows_count, frame_offset, all_frame_offsets)
            input_rows_cache = {}; input_lines = [None] * height
            for y in range(height):
                row_pos = row_offsets[y]
                if row_pos in input_rows_cache: input_lines[y] = input_rows_cache[row_pos]; continue
                repeat = rows_count.get(row_pos, 1)
                row = self._read_line(row_pos, repeat, width)
                input_rows_cache[row_pos] = row; input_lines[y] = row
            
            current_dst_pos = 0
            for y, line in enumerate(input_lines):
                if line is None: 
                    current_dst_pos += width * 4
                    continue
                self._unpack_line(line, width, pixel_buffer, current_dst_pos)
                current_dst_pos += width * 4

        if any(pixel_buffer):
            bgra_image = Image.frombytes('RGBA', (width, height), bytes(pixel_buffer))
            b, g, r, a = bgra_image.split()
            image = Image.merge("RGBA", (r, g, b, a))
        else:
            image = Image.new('RGBA', (width, height), (0,0,0,0))
            
        return image, metadata

    def _unpack_line(self, line_data, width, output_buffer, dst_start_pos):
        # =====================================================================
        # === 重構部分：此函式現在直接修改 output_buffer，不再返回新物件 ===
        # =====================================================================
        src_pos = 0
        pixels_in_line = 0 # 當前行已處理的像素數
        dst_pos = dst_start_pos

        while pixels_in_line < width and src_pos < len(line_data):
            # C# 原始碼中，這個對齊檢查是在每一行壓縮塊的開頭
            if (src_pos & 1) != 0:
                src_pos += 1

            try:
                control, = struct.unpack_from('<H', line_data, src_pos)
            except struct.error:
                break # 壓縮資料提前結束
            src_pos += 2
            
            method = control >> 13
            skip = (control >> 11) & 3
            count = control & 0x7FF
            
            if skip > 0:
                src_pos += skip
            
            if count == 0:
                try:
                    # 使用有符號整數，與 C# 的 ToInt32 保持一致
                    count, = struct.unpack_from('<i', line_data, src_pos)
                except struct.error:
                    break
                src_pos += 4

            if count <= 0: # 如果 count 為 0 或負數，則跳過
                continue
            
            # 確保不會超出當前行的寬度
            if pixels_in_line + count > width:
                count = width - pixels_in_line
            
            if method == 2: # BGR
                for _ in range(count):
                    if src_pos + 3 > len(line_data): break
                    output_buffer[dst_pos:dst_pos+3] = line_data[src_pos:src_pos+3]
                    output_buffer[dst_pos+3] = 255
                    dst_pos += 4; src_pos += 3
            elif method == 3: # BGR RLE
                if src_pos + 3 > len(line_data): break
                color = line_data[src_pos:src_pos+3]; src_pos += 3
                for _ in range(count):
                    output_buffer[dst_pos:dst_pos+3] = color
                    output_buffer[dst_pos+3] = 255
                    dst_pos += 4
            elif method == 4: # BGRA
                for _ in range(count):
                    if src_pos + 4 > len(line_data): break
                    a = line_data[src_pos]; bgr = line_data[src_pos+1:src_pos+4]
                    output_buffer[dst_pos:dst_pos+3] = bgr
                    output_buffer[dst_pos+3] = a
                    dst_pos += 4; src_pos += 4
            elif method == 5: # BGRA RLE
                if src_pos + 4 > len(line_data): break
                a = line_data[src_pos]; bgr = line_data[src_pos+1:src_pos+4]; src_pos += 4
                for _ in range(count):
                    output_buffer[dst_pos:dst_pos+3] = bgr
                    output_buffer[dst_pos+3] = a
                    dst_pos += 4
            else: # 透明/跳過
                dst_pos += count * 4

            pixels_in_line += count

    def _update_repeat_count(self, rows_count, current_frame_offset, all_frame_offsets):
        for offset in all_frame_offsets:
            if offset == 0 or offset == current_frame_offset: continue
            self.file.seek(offset + 4)
            try:
                height, = struct.unpack('<I', self.file.read(4)); self.file.seek(offset + 20)
                for _ in range(height):
                    row_offset, = struct.unpack('<I', self.file.read(4))
                    if row_offset in rows_count: rows_count[row_offset] += 1
            except struct.error: continue
    def _read_line(self, offset, repeat, width):
        self.file.seek(offset)
        try:
            row_length, = struct.unpack('<H', self.file.read(2))
            if (offset + 2) & 1: self.file.read(1); row_length -= 1
            row_data = bytearray(self.file.read(row_length))
        except struct.error: return bytes()
        src_pos = 0; pixel_pos = 0
        while pixel_pos < width and src_pos < len(row_data):
            if (src_pos & 1) != 0: src_pos += 1
            try: control, = struct.unpack_from('<H', row_data, src_pos)
            except struct.error: break
            pos_after_control = src_pos + 2; method = control >> 13; skip = (control >> 11) & 3; count = control & 0x7FF; pos_after_control += skip
            if count == 0:
                try: count, = struct.unpack_from('<i', row_data, pos_after_control); pos_after_control += 4
                except struct.error: break
            if count <= 0: continue
            if pixel_pos + count > width: count = width - pixel_pos
            data_start_pos = pos_after_control
            if method == 2:
                for _ in range(repeat - 1):
                    for i in range(3, count * 3):
                        if data_start_pos+i < len(row_data) and data_start_pos+i-3 < len(row_data): row_data[data_start_pos+i] = (row_data[data_start_pos+i] + row_data[data_start_pos+i-3]) & 0xFF
                src_pos = data_start_pos + count * 3
            elif method == 3: src_pos = data_start_pos + 3
            elif method == 4:
                for _ in range(repeat - 1):
                    for i in range(4, count * 4):
                        if data_start_pos+i < len(row_data) and data_start_pos+i-4 < len(row_data): row_data[data_start_pos+i] = (row_data[data_start_pos+i] + row_data[data_start_pos+i-4]) & 0xFF
                src_pos = data_start_pos + count * 4
            elif method == 5: src_pos = data_start_pos + 4
            else: src_pos = data_start_pos
            pixel_pos += count
        return bytes(row_data)

# 主函式和批次處理邏輯不變 (此處省略以保持簡潔)
def write_master_csv(csv_path, metadata_list):
    if not metadata_list: print("沒有找到任何可寫入 CSV 的資訊。"); return
    print(f"\n正在寫入主座標檔: {csv_path}")
    fieldnames = ['frame_index', 'width', 'height', 'offset_x', 'offset_y']
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader(); writer.writerows(metadata_list)
    print("CSV 檔案寫入完成。")

def test_composite_file(s25_file_path, images_output_dir):
    print(f"=== 進入測試合成模式: {s25_file_path} ===")
    decoder = S25Decoder(s25_file_path, images_output_dir)
    _, decoded_frames = decoder.decode()
    if not decoded_frames: print("沒有成功解碼的畫格，無法進行合成。"); return
    min_x, max_x, min_y, max_y = float('inf'), float('-inf'), float('inf'), float('-inf')
    for frame in decoded_frames:
        m = frame['metadata']; w, h, ox, oy = m['width'], m['height'], m['offset_x'], m['offset_y']
        half_w, half_h = w / 2, h / 2
        top_left_x = ox - half_w; top_left_y = oy - half_h; bottom_right_x = ox + half_w; bottom_right_y = oy + half_h
        if top_left_x < min_x: min_x = top_left_x
        if top_left_y < min_y: min_y = top_left_y
        if bottom_right_x > max_x: max_x = bottom_right_x
        if bottom_right_y > max_y: max_y = bottom_right_y
    canvas_width = int(max_x - min_x); canvas_height = int(max_y - min_y)
    if canvas_width <= 0 or canvas_height <= 0: print("計算出的畫布大小無效，無法合成。"); return
    print(f"計算出畫布大小: {canvas_width} x {canvas_height}")
    composite_image = Image.new('RGBA', (canvas_width, canvas_height), (0, 0, 0, 0))
    for frame in decoded_frames:
        img = frame['image']; m = frame['metadata']; w, h, ox, oy = m['width'], m['height'], m['offset_x'], m['offset_y']
        paste_x = int((ox - w / 2) - min_x); paste_y = int((oy - h / 2) - min_y)
        composite_image.paste(img, (paste_x, paste_y), img)
    composite_filename = f"{decoder.base_name}_composite.png"
    composite_path = os.path.join(images_output_dir, composite_filename)
    composite_image.save(composite_path)
    print(f"測試合成圖已儲存至: {composite_path}")

def batch_process_all(s25_input_dir, images_output_dir, csv_output_path):
    print("=== 進入批次處理模式 ===")
    s25_files = glob.glob(os.path.join(s25_input_dir, '*.S25'))
    s25_files.extend(glob.glob(os.path.join(s25_input_dir, '*.s25')))
    if not s25_files: print(f"在 '{s25_input_dir}' 資料夾中沒有找到任何 .S25 檔案。"); return
    master_metadata_list = []
    for s25_file_path in sorted(list(set(s25_files))):
        decoder = S25Decoder(s25_file_path, images_output_dir)
        file_metadata, _ = decoder.decode()
        if file_metadata: master_metadata_list.extend(file_metadata)
    write_master_csv(csv_output_path, master_metadata_list)

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    s25_input_dir = os.path.join(script_dir, 's25')
    images_output_dir = os.path.join(script_dir, 'images')
    csv_output_path = os.path.join(script_dir, 'coordinates.csv')
    os.makedirs(images_output_dir, exist_ok=True)
    if not os.path.isdir(s25_input_dir): print(f"錯誤: 輸入資料夾 '{s25_input_dir}' 不存在！"); sys.exit(1)
    if len(sys.argv) > 2 and sys.argv[1] == '--test-composite':
        test_file = sys.argv[2]
        if not os.path.exists(test_file): print(f"錯誤: 找不到指定的測試檔案: {test_file}"); sys.exit(1)
        test_composite_file(test_file, images_output_dir)
    else: batch_process_all(s25_input_dir, images_output_dir, csv_output_path)
    print("\n所有處理已完成！")

if __name__ == "__main__":
    main()
