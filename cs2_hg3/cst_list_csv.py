import os
import struct
import zlib
import csv

# --- 設定 ---
CST_FOLDER = 'cst' # <<< 修改點：設定要讀取的資料夾名稱
OUTPUT_CSV_FILE = 'cst_export.csv' # 輸出的 CSV 檔名

def find_cst_files_in_cst_folder():
    """在指定的 CST_FOLDER 資料夾中尋找所有 .cst 檔案"""
    # <<< 修改點：整個函式更新
    cst_files = []
    
    # 檢查 cst 資料夾是否存在
    if not os.path.isdir(CST_FOLDER):
        print(f"錯誤：找不到名為 '{CST_FOLDER}' 的資料夾。請在腳本同目錄下建立此資料夾。")
        return cst_files # 返回空的 list

    # 遍歷資料夾中的所有檔案
    for f in os.listdir(CST_FOLDER):
        if f.lower().endswith('.cst'):
            # 使用 os.path.join 來建立完整的檔案路徑 (例如: "cst/file1.cst")
            # 這樣後續處理才能正確找到檔案
            full_path = os.path.join(CST_FOLDER, f)
            cst_files.append(full_path)
            
    return cst_files

def process_cst_to_rows(filepath):
    """
    處理單一的 .cst 檔案，將其內容解析成準備寫入 CSV 的多行資料。
    返回一個包含多個 list 的列表，每個 list 就是 CSV 的一列。
    """
    rows = []
    print(f"正在讀取檔案: {filepath}...")
    try:
        with open(filepath, 'rb') as f:
            # 1. 讀取並解析 CSTHDR1
            # '<' 代表小端序 (little-endian)
            # 8s: 8位元組的字串, I: 4位元組的無號整數
            header_data = f.read(16)
            if len(header_data) < 16:
                print(f"  -> 錯誤: 檔案 {filepath} 太小，無法讀取檔頭。")
                return []

            sig, length, original_length = struct.unpack('<8sII', header_data)
            if sig != b'CatScene':
                print(f"  -> 錯誤: {filepath} 不是有效的 CatScene 檔案。")
                return []

            # 2. 讀取並解壓縮資料
            compressed_data = f.read(length)
            uncompressed_data = zlib.decompress(compressed_data)

            if len(uncompressed_data) != original_length:
                print(f"  -> 警告: {filepath} 解壓縮後長度與檔頭不符。")

            # 3. 解析 CSTHDR2
            hdr2_size = 16 # 4 * uint32_t
            hdr2_data = uncompressed_data[:hdr2_size]
            # 第1個欄位是檔頭長度，這裡用 _ 忽略
            _, entry_count, table2_offset, data_offset = struct.unpack('<IIII', hdr2_data)

            # 4. 解析索引表和資料區
            sections_start = hdr2_size
            entries_start = hdr2_size + table2_offset
            data_start = hdr2_size + data_offset
            
            # 遍歷所有區塊 (sections)
            for j in range(entry_count):
                section_offset = sections_start + j * 8 # CSTENTRY1 size = 8 bytes
                s_entry_count, s_start_index = struct.unpack('<II', uncompressed_data[section_offset : section_offset + 8])

                # 遍歷區塊中的所有條目 (entries)
                for k in range(s_entry_count):
                    entry_offset = entries_start + (s_start_index + k) * 4 # CSTENTRY2 size = 4 bytes
                    str_offset_in_data, = struct.unpack('<I', uncompressed_data[entry_offset : entry_offset + 4])
                    
                    # 從資料區讀取以 null 結尾的字串
                    full_str_bytes = uncompressed_data[data_start + str_offset_in_data:]
                    null_term_pos = full_str_bytes.find(b'\x00')
                    
                    # 使用 'sjis' (Shift-JIS) 編碼，這是日系遊戲常用編碼
                    # errors='ignore' 可以避免因解碼錯誤而中斷
                    command_string = full_str_bytes[:null_term_pos].decode('sjis', errors='ignore')

                    # 準備要寫入 CSV 的一列資料
                    row = [
                        filepath,             # 來源檔案
                        j,                    # 區塊索引 (Section Index)
                        k,                    # 區塊內條目索引 (Entry Index)
                        command_string        # 提取出的指令字串
                    ]
                    rows.append(row)
    
    except FileNotFoundError:
        print(f"  -> 錯誤: 找不到檔案 {filepath}")
    except zlib.error as e:
        print(f"  -> 錯誤: 解壓縮 {filepath} 失敗: {e}")
    except Exception as e:
        print(f"  -> 處理檔案 {filepath} 時發生未知錯誤: {e}")
        
    return rows


def main():
    """主執行函式"""
    # <<< 修改點：呼叫新的函式
    cst_files = find_cst_files_in_cst_folder()
    
    if not cst_files:
        # 錯誤訊息已在 find_cst_files_in_cst_folder 中印出
        print("程式已結束。")
        return

    print(f"在 '{CST_FOLDER}' 資料夾中找到 {len(cst_files)} 個 .cst 檔案，準備匯出至 {OUTPUT_CSV_FILE}...")

    # 使用 'w' 模式寫入 CSV，newline='' 是官方建議的用法，避免多餘的空行
    # encoding='utf-8-sig' 可以確保 Excel 等軟體能正確讀取包含中文的 CSV
    with open(OUTPUT_CSV_FILE, 'w', newline='', encoding='utf-8-sig') as csvfile:
        csv_writer = csv.writer(csvfile)
        
        # 寫入 CSV 檔頭
        header = ['source_file', 'section_index', 'entry_index_in_section', 'command_string']
        csv_writer.writerow(header)
        
        total_rows = 0
        # 遍歷所有找到的 .cst 檔案
        for filename in cst_files:
            rows_from_file = process_cst_to_rows(filename)
            if rows_from_file:
                csv_writer.writerows(rows_from_file)
                total_rows += len(rows_from_file)
                print(f"  -> 從 {filename} 成功匯出 {len(rows_from_file)} 筆資料。")

    print("\n--------------------------------------------------")
    print(f"匯出完成！總共 {total_rows} 筆資料已儲存至 {OUTPUT_CSV_FILE}")
    print("--------------------------------------------------")


if __name__ == '__main__':
    main()