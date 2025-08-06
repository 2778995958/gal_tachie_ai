import struct
import csv
import os
import glob # 匯入 glob 模組來尋找檔案

# --- 設定 ---
# 遊戲文字的編碼，日文遊戲通常是 'cp932' (Shift_JIS)
TEXT_ENCODING = 'cp932'

def clean_frame_names(byte_string):
    """
    模仿 C++ 程式碼中對 frame_names 的清理邏輯。
    (此函式與前一版本相同)
    """
    buffer = bytearray(byte_string)
    
    # 1. 清理結尾引號
    for i in range(len(buffer) - 1, -1, -1):
        if buffer[i] != 0x22 and buffer[i] != 0x00:
            break
        buffer[i] = 0x00
        
    # 2. 清理第一個空格
    try:
        first_space_index = buffer.index(b' ')
        buffer = buffer[:first_space_index]
    except ValueError:
        pass
        
    return buffer

def process_dat_file(dat_filepath):
    """
    處理單一的 .dat 檔案，並將其轉換為 .csv 檔案。
    """
    # 根據輸入的 dat 檔名，產生對應的 csv 檔名
    # 例如：'cglist.dat' -> 'cglist.csv'
    csv_filepath = os.path.splitext(dat_filepath)[0] + '.csv'
    
    print(f"--- 開始處理 '{dat_filepath}' ---")

    try:
        with open(dat_filepath, 'rb') as f_dat, \
             open(csv_filepath, 'w', newline='', encoding='utf-8') as f_csv:
            
            csv_writer = csv.writer(f_csv)
            csv_writer.writerow(['entry_index', 'entry_name', 'subentry_index', 'frame_names_cleaned'])
            
            # 1. 讀取 DATHDR
            header_data = f_dat.read(12)
            if len(header_data) < 12:
                print(f"錯誤：'{dat_filepath}' 檔案格式無效 (檔案頭太短)。")
                return # 跳過這個檔案
                
            _, _, entry_count = struct.unpack('<LLL', header_data)
            
            # 2. 遍歷所有 DATENTRY
            for i in range(entry_count):
                entry_data = f_dat.read(72)
                if len(entry_data) < 72:
                    print(f"警告：在讀取第 {i+1} 個 Entry 時檔案提前結束。")
                    break
                
                _, name_bytes, subentry_count = struct.unpack('<L64sL', entry_data)
                entry_name = name_bytes.strip(b'\x00').decode(TEXT_ENCODING, errors='ignore')

                # 3. 遍歷所有 DATSUBENTRY
                for j in range(subentry_count):
                    subentry_data = f_dat.read(64)
                    if len(subentry_data) < 64:
                        print(f"警告：在讀取 {entry_name} 的第 {j+1} 個 SubEntry 時檔案提前結束。")
                        break

                    frame_names_bytes, = struct.unpack('<64s', subentry_data)
                    cleaned_bytes = clean_frame_names(frame_names_bytes)
                    frame_names_str = cleaned_bytes.strip(b'\x00').decode(TEXT_ENCODING, errors='ignore')
                    
                    csv_writer.writerow([i, entry_name, j, frame_names_str])

        print(f"成功：資料已匯出至 '{csv_filepath}'")

    except FileNotFoundError:
        print(f"錯誤：找不到檔案 '{dat_filepath}'。")
    except Exception as e:
        print(f"處理 '{dat_filepath}' 時發生未知錯誤: {e}")


def main():
    """
    主函式，尋找所有 .dat 檔案並呼叫處理函式。
    """
    # 使用 glob.glob('*.dat') 尋找當前資料夾中所有符合模式的檔案
    dat_files = glob.glob('*.dat')
    
    if not dat_files:
        print("在當前資料夾中找不到任何 .dat 檔案。")
        return
        
    print(f"找到了 {len(dat_files)} 個 .dat 檔案，準備開始處理...")
    print("\n")

    for dat_file in dat_files:
        process_dat_file(dat_file)
        print("\n") # 增加一個換行，讓輸出更清晰

    print("--- 所有檔案處理完畢 ---")

if __name__ == '__main__':
    main()