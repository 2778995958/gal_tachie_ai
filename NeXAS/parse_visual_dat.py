import sys
import struct
import csv
import os

def read_null_terminated_string(data, offset):
    """
    從給定的 byte data 和 offset 開始讀取一個以 null (0x00) 結尾的字串。
    
    Args:
        data (bytes): 來源 byte 資料。
        offset (int): 開始讀取的索引位置。

    Returns:
        tuple: (解碼後的字串, 讀取結束後的新 offset)。
    """
    end_offset = data.find(b'\x00', offset)
    if end_offset == -1:
        # 如果找不到 null 結尾，可能檔案格式有誤或已到檔尾
        return "", len(data)
        
    # 嘗試用 'shift_jis' 解碼，因為這在日系遊戲中很常見。
    # 如果出現亂碼，可以嘗試 'utf-8' 或其他編碼。
    try:
        text = data[offset:end_offset].decode('shift_jis')
    except UnicodeDecodeError:
        text = str(data[offset:end_offset]) # 解碼失敗則顯示原始 byte 字串

    new_offset = end_offset + 1 # 跳過結尾的 null 字元
    return text, new_offset

def parse_visual_dat(dat_filepath):
    """
    解析 visual.dat 檔案並將其內容轉換為 CSV 檔案。
    """
    # 檢查輸入檔案是否存在
    if not os.path.exists(dat_filepath):
        print(f"錯誤：檔案 '{dat_filepath}' 不存在。")
        return

    # 產生輸出的 CSV 檔名
    output_csv_path = os.path.splitext(dat_filepath)[0] + '.csv'

    try:
        # 以二進位模式讀取整個檔案
        with open(dat_filepath, 'rb') as f:
            file_content = f.read()
    except IOError as e:
        print(f"讀取檔案時發生錯誤：{e}")
        return

    file_size = len(file_content)
    if file_size < 4:
        print("錯誤：檔案太小，無法解析。")
        return

    # 1. 解析檔案標頭 (Header)
    # 根據 C++ 程式碼，檔案開頭是一個 uint32_t，代表一個計數
    # '<I' 表示 little-endian (小端序) 的 unsigned int (32-bit)
    unknown_count = struct.unpack_from('<I', file_content, 0)[0]
    
    # C++ 程式碼跳過了 (unknown_count + 1) 個 uint32_t
    # 所以我們的起始偏移量 (offset) 就是 4 * (unknown_count + 1)
    offset = 4 * (unknown_count + 1)
    
    parsed_records = []

    # 2. 迴圈讀取每一筆資料紀錄
    while offset < file_size:
        # 確保有足夠的資料可以讀取 DATENTRY1 (32 bytes)
        if offset + 32 > file_size:
            break

        # 讀取 DATENTRY1 (8 個 uint32_t)
        # C++: struct DATENTRY1 { uint32_t unknown1 ... unknown8; };
        dat_entry1 = struct.unpack_from('<8I', file_content, offset)
        offset += 32 # 8 * 4 bytes

        # 讀取 base_filename (null-terminated string)
        base_filename, offset = read_null_terminated_string(file_content, offset)

        # 讀取 delta_filename (null-terminated string)
        delta_filename, offset = read_null_terminated_string(file_content, offset)
        
        # 確保有足夠的資料可以讀取 DATENTRY2 (16 bytes)
        if offset + 16 > file_size:
            break

        # 讀取 DATENTRY2 (4 個 uint32_t)
        # C++: struct DATENTRY2 { uint32_t offset_x, offset_y, width, height; };
        offset_x, offset_y, width, height = struct.unpack_from('<4I', file_content, offset)
        offset += 16 # 4 * 4 bytes

        # 將解析出的資料存成一個 dictionary，方便寫入 CSV
        record = {
            'base_filename': base_filename,
            'delta_filename': delta_filename,
            'offset_x': offset_x,
            'offset_y': offset_y,
            'width': width,
            'height': height,
            # 也把 DATENTRY1 的未知數據加進來
            'unknown1': dat_entry1[0], 'unknown2': dat_entry1[1],
            'unknown3': dat_entry1[2], 'unknown4': dat_entry1[3],
            'unknown5': dat_entry1[4], 'unknown6': dat_entry1[5],
            'unknown7': dat_entry1[6], 'unknown8': dat_entry1[7]
        }
        parsed_records.append(record)

    # 3. 將結果寫入 CSV 檔案
    if not parsed_records:
        print("檔案中沒有找到任何可解析的紀錄。")
        return

    # 定義 CSV 檔案的欄位標頭
    fieldnames = [
        'base_filename', 'delta_filename', 'offset_x', 'offset_y', 'width', 'height',
        'unknown1', 'unknown2', 'unknown3', 'unknown4', 'unknown5', 'unknown6',
        'unknown7', 'unknown8'
    ]

    try:
        with open(output_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader() # 寫入標頭
            writer.writerows(parsed_records) # 寫入所有紀錄
        print(f"成功將資料轉換並儲存至 '{output_csv_path}'")
    except IOError as e:
        print(f"寫入 CSV 檔案時發生錯誤: {e}")

if __name__ == '__main__':
    # 檢查命令行參數
    if len(sys.argv) != 2:
        print(f"用法: python {sys.argv[0]} <visual.dat>")
        sys.exit(1)
        
    dat_filename = sys.argv[1]
    parse_visual_dat(dat_filename)