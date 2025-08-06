import sys
import os
import struct
import csv
import glob
from PIL import Image

class S25Decoder:
    """
    一個用於解碼 ShiinaRio S25 圖片格式檔案的類別。
    """
    def __init__(self, filepath, image_output_dir):
        """
        初始化解碼器。
        :param filepath: S25 檔案的完整路徑。
        :param image_output_dir: 圖片輸出的目標資料夾。
        """
        self.filepath = filepath
        self.image_output_dir = image_output_dir
        self.file = open(filepath, 'rb')
        # 移除副檔名，取得基礎檔名
        self.base_name = os.path.splitext(os.path.basename(filepath))[0]

    def __del__(self):
        if hasattr(self, 'file') and self.file:
            self.file.close()

    def decode(self):
        """
        主解碼流程。讀取所有畫格，解碼圖片並返回元數據列表。
        """
        print(f"--- 開始處理檔案: {os.path.basename(self.filepath)} ---")
        
        sig = self.file.read(4)
        if sig != b'S25\0':
            print("  錯誤: 檔案簽名不符，跳過此檔案。")
            return []

        try:
            frame_count, = struct.unpack('<i', self.file.read(4))
            if not (0 < frame_count < 10000):
                print(f"  錯誤: 偵測到無效的畫格數量 ({frame_count})，跳過。")
                return []
            
            frame_offsets = list(struct.unpack(f'<{frame_count}I', self.file.read(4 * frame_count)))
            print(f"  找到 {len(frame_offsets)} 個畫格。")
        except struct.error:
            print("  錯誤: 讀取檔案標頭失敗，檔案可能已損壞。")
            return []

        all_frames_metadata = []
        for i, offset in enumerate(frame_offsets):
            if offset == 0:
                continue
            
            try:
                image, metadata = self._decode_frame(i, offset, frame_offsets)
                
                # 根據新規則產生圖片檔名
                png_filename = f"{self.base_name}_{i}.png"
                output_image_path = os.path.join(self.image_output_dir, png_filename)
                image.save(output_image_path, 'PNG')
                
                all_frames_metadata.append(metadata)
            except Exception as e:
                print(f"    錯誤: 解碼畫格 {i} 失敗: {e}")

        print(f"--- 完成檔案: {os.path.basename(self.filepath)} ---")
        return all_frames_metadata

    def _decode_frame(self, frame_index, frame_offset, all_frame_offsets):
        """ 解碼單一圖片畫格 """
        self.file.seek(frame_offset)
        width, height, offset_x, offset_y, flags = struct.unpack('<IIiiI', self.file.read(20))
        is_incremental = (flags & 0x80000000) != 0

        # *** 更新 metadata 的 'frame_index' 欄位 ***
        png_basename = f"{self.base_name}_{frame_index}"
        metadata = {
            'frame_index': png_basename, # 新規則: 使用 '檔名_索引'
            'width': width,
            'height': height,
            'offset_x': offset_x,
            'offset_y': offset_y,
        }
        
        row_offsets = list(struct.unpack(f'<{height}I', self.file.read(4 * height)))
        pixel_buffer = bytearray(width * height * 4)

        if not is_incremental:
            for y in range(height):
                row_pos = row_offsets[y]
                if row_pos == 0: continue
                self.file.seek(row_pos)
                row_length, = struct.unpack('<H', self.file.read(2))
                row_pos += 2
                if row_pos & 1:
                    self.file.read(1)
                    row_length -= 1
                compressed_data = self.file.read(row_length)
                decoded_row = self._unpack_line(compressed_data, width)
                start = y * width * 4
                pixel_buffer[start : start + len(decoded_row)] = decoded_row
        else:
            rows_count = {}
            for offset in row_offsets:
                rows_count[offset] = rows_count.get(offset, 0) + 1
            self._update_repeat_count(rows_count, frame_offset, all_frame_offsets)
            input_rows_cache = {}
            input_lines = [None] * height
            for y in range(height):
                row_pos = row_offsets[y]
                if row_pos in input_rows_cache:
                    input_lines[y] = input_rows_cache[row_pos]
                    continue
                repeat = rows_count.get(row_pos, 1)
                row = self._read_line(row_pos, repeat, width)
                input_rows_cache[row_pos] = row
                input_lines[y] = row
            for y, line in enumerate(input_lines):
                if line is None: continue
                decoded_row = self._unpack_line(line, width)
                start = y * width * 4
                pixel_buffer[start : start + len(decoded_row)] = decoded_row

        if any(pixel_buffer):
            bgra_image = Image.frombytes('RGBA', (width, height), bytes(pixel_buffer))
            b, g, r, a = bgra_image.split()
            image = Image.merge("RGBA", (r, g, b, a))
        else:
            image = Image.new('RGBA', (width, height), (0,0,0,0))
            
        return image, metadata
    
    # _unpack_line, _update_repeat_count, _read_line 函式與前一版相同
    # (此處省略以保持簡潔，實際使用時請保留這些函式)
    def _unpack_line(self, line_data, width):
        output_row = bytearray(width * 4)
        src_pos = 0
        dst_pixel_pos = 0
        while dst_pixel_pos < width and src_pos < len(line_data):
            if (src_pos & 1) != 0: src_pos += 1
            control, = struct.unpack_from('<H', line_data, src_pos)
            src_pos += 2
            method = control >> 13
            skip = (control >> 11) & 3
            count = control & 0x7FF
            src_pos += skip
            if count == 0:
                count, = struct.unpack_from('<I', line_data, src_pos)
                src_pos += 4
            if dst_pixel_pos + count > width: count = width - dst_pixel_pos
            dst_byte_pos = dst_pixel_pos * 4
            if method == 2:
                for _ in range(count):
                    output_row[dst_byte_pos:dst_byte_pos+3] = line_data[src_pos:src_pos+3]; output_row[dst_byte_pos+3] = 255
                    dst_byte_pos += 4; src_pos += 3
            elif method == 3:
                color = line_data[src_pos:src_pos+3]; src_pos += 3
                for _ in range(count):
                    output_row[dst_byte_pos:dst_byte_pos+3] = color; output_row[dst_byte_pos+3] = 255
                    dst_byte_pos += 4
            elif method == 4:
                for _ in range(count):
                    a = line_data[src_pos]; bgr = line_data[src_pos+1:src_pos+4]
                    output_row[dst_byte_pos:dst_byte_pos+3] = bgr; output_row[dst_byte_pos+3] = a
                    dst_byte_pos += 4; src_pos += 4
            elif method == 5:
                color = line_data[src_pos:src_pos+4]; a = color[0]; bgr = color[1:4]; src_pos += 4
                for _ in range(count):
                    output_row[dst_byte_pos:dst_byte_pos+3] = bgr; output_row[dst_byte_pos+3] = a
                    dst_byte_pos += 4
            dst_pixel_pos += count
        return output_row

    def _update_repeat_count(self, rows_count, current_frame_offset, all_frame_offsets):
        for offset in all_frame_offsets:
            if offset == 0 or offset == current_frame_offset: continue
            self.file.seek(offset + 4)
            try:
                height, = struct.unpack('<I', self.file.read(4))
                self.file.seek(offset + 20)
                for _ in range(height):
                    row_offset, = struct.unpack('<I', self.file.read(4))
                    if row_offset in rows_count:
                        rows_count[row_offset] += 1
            except struct.error: continue

    def _read_line(self, offset, repeat, width):
        self.file.seek(offset)
        try:
            row_length, = struct.unpack('<H', self.file.read(2))
            if (offset + 2) & 1:
                self.file.read(1); row_length -= 1
            row_data = bytearray(self.file.read(row_length))
        except struct.error: return bytes()
        src_pos = 0; pixel_pos = 0
        while pixel_pos < width and src_pos < len(row_data):
            if (src_pos & 1) != 0: src_pos += 1
            try:
                control, = struct.unpack_from('<H', row_data, src_pos)
            except struct.error: break
            pos_after_control = src_pos + 2
            method = control >> 13; skip = (control >> 11) & 3; count = control & 0x7FF
            pos_after_control += skip
            if count == 0:
                try:
                    count, = struct.unpack_from('<I', row_data, pos_after_control)
                    pos_after_control += 4
                except struct.error: break
            if pixel_pos + count > width: count = width - pixel_pos
            data_start_pos = pos_after_control
            if method == 2:
                for _ in range(repeat - 1):
                    for i in range(3, count * 3):
                        if data_start_pos+i < len(row_data) and data_start_pos+i-3 < len(row_data):
                            row_data[data_start_pos+i] = (row_data[data_start_pos+i] + row_data[data_start_pos+i-3]) & 0xFF
                src_pos = data_start_pos + count * 3
            elif method == 3: src_pos = data_start_pos + 3
            elif method == 4:
                for _ in range(repeat - 1):
                    for i in range(4, count * 4):
                        if data_start_pos+i < len(row_data) and data_start_pos+i-4 < len(row_data):
                            row_data[data_start_pos+i] = (row_data[data_start_pos+i] + row_data[data_start_pos+i-4]) & 0xFF
                src_pos = data_start_pos + count * 4
            elif method == 5: src_pos = data_start_pos + 4
            else: src_pos = data_start_pos
            pixel_pos += count
        return bytes(row_data)


def write_master_csv(csv_path, metadata_list):
    """
    將所有畫格的元數據寫入一個主 CSV 檔案。
    """
    if not metadata_list:
        print("沒有找到任何可寫入 CSV 的資訊。")
        return
        
    print(f"\n正在寫入主座標檔: {csv_path}")
    # 確保 'frame_index' 是第一欄
    fieldnames = ['frame_index', 'width', 'height', 'offset_x', 'offset_y']
    
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(metadata_list)
    print("CSV 檔案寫入完成。")

def main():
    """
    批次處理的主函式。
    """
    # 獲取腳本所在目錄
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 設定輸入和輸出資料夾路徑
    s25_input_dir = os.path.join(script_dir, 's25')
    images_output_dir = os.path.join(script_dir, 'images')
    
    # 建立輸出資料夾 (如果不存在)
    os.makedirs(images_output_dir, exist_ok=True)
    
    # 檢查輸入資料夾是否存在
    if not os.path.isdir(s25_input_dir):
        print(f"錯誤: 輸入資料夾 '{s25_input_dir}' 不存在！")
        print("請建立一個名為 's25' 的資料夾，並將 S25 檔案放入其中。")
        sys.exit(1)
        
    # 搜尋所有 .S25 檔案 (不分大小寫)
    s25_files = glob.glob(os.path.join(s25_input_dir, '*.S25'))
    s25_files.extend(glob.glob(os.path.join(s25_input_dir, '*.s25')))
    
    if not s25_files:
        print(f"在 '{s25_input_dir}' 資料夾中沒有找到任何 .S25 檔案。")
        sys.exit(0)
    
    master_metadata_list = []
    
    # 遍歷所有找到的 S25 檔案並進行處理
    for s25_file_path in sorted(list(set(s25_files))): # set()避免重複
        decoder = S25Decoder(s25_file_path, images_output_dir)
        file_metadata = decoder.decode()
        if file_metadata:
            master_metadata_list.extend(file_metadata)
            
    # 將所有結果寫入一個 CSV 檔案
    csv_output_path = os.path.join(script_dir, 'coordinates.csv')
    write_master_csv(csv_output_path, master_metadata_list)
    
    print("\n所有處理已完成！")

if __name__ == "__main__":
    main()