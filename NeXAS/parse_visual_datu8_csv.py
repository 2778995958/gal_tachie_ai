import sys
import struct
import csv
import os

# 設定你想要的 CSV 標題 (共 14 個欄位)
CSV_HEADERS = [
    "unknown1", "unknown2", "unknown3", "unknown4", 
    "unknown5", "unknown6", "unknown7", "unknown8", 
    "base_filename", "delta_filename", 
    "offset_x", "offset_y", "width", "height"
]

def read_string(f):
    """
    讀取 Nexas 格式的字串 (長度 + 內容)
    """
    length_bytes = f.read(4)
    if not length_bytes:
        return ""
    
    # Little-endian unsigned int 讀取字串長度
    length = struct.unpack("<I", length_bytes)[0]
    
    content = f.read(length)
    if len(content) < length:
        # 如果檔案突然結束，回傳目前讀到的部分
        return content.decode('utf-8', errors='replace').rstrip('\0')
        
    s = content.decode('utf-8', errors='replace')
    return s.rstrip('\0')

def parse_nexas_dat(filepath):
    """
    解析 datu8 檔案並轉為 CSV
    """
    if not os.path.exists(filepath):
        print(f"❌ 錯誤：找不到檔案 {filepath}")
        return

    # 準備輸出檔案路徑
    output_csv_path = os.path.splitext(filepath)[0] + '.csv'
    file_size = os.path.getsize(filepath)

    print(f"正在處理: {os.path.basename(filepath)}...")

    try:
        with open(filepath, "rb") as f:
            # 1. 讀取欄位定義數量 (Column Count)
            count_bytes = f.read(4)
            if not count_bytes:
                print("❌ 檔案是空的")
                return
            col_count = struct.unpack("<I", count_bytes)[0]
            
            # 檢查欄位數量是否與標題相符
            if col_count != len(CSV_HEADERS):
                print(f"⚠️ 警告：檔案內的欄位數量 ({col_count}) 與設定的標題數量 ({len(CSV_HEADERS)}) 不符！")
                # 程式仍會繼續執行，但 CSV 標題可能會對不上
            
            # 2. 讀取欄位類型 (Column Types)
            # 類型 ID: 1=String, 2=Dword(i32), 3=Byte(i8), 5=Word(i16), 6=LString
            types = []
            for _ in range(col_count):
                type_id_bytes = f.read(4)
                if len(type_id_bytes) < 4:
                    break
                type_id = struct.unpack("<I", type_id_bytes)[0]
                types.append(type_id)

            # 3. 準備寫入 CSV
            with open(output_csv_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
                # 寫入標題
                writer = csv.writer(csvfile)
                writer.writerow(CSV_HEADERS)
                
                rows_processed = 0
                
                # 4. 循環讀取資料直到檔尾
                while f.tell() < file_size:
                    row_values = []
                    
                    for t in types:
                        if t == 1 or t == 6: # String or LString
                            val = read_string(f)
                            row_values.append(val)
                            
                        elif t == 2: # Dword (i32)
                            bytes_val = f.read(4)
                            val = struct.unpack("<i", bytes_val)[0]
                            row_values.append(val)
                            
                        elif t == 3: # Byte (i8)
                            bytes_val = f.read(1)
                            val = struct.unpack("<b", bytes_val)[0]
                            row_values.append(val)
                            
                        elif t == 5: # Word (i16)
                            bytes_val = f.read(2)
                            val = struct.unpack("<h", bytes_val)[0]
                            row_values.append(val)
                        
                        else:
                            # 未知類型，嘗試跳過 4 bytes 避免死回圈，但資料可能已錯位
                            f.read(4)
                            row_values.append("ERR")

                    # 寫入這一行
                    writer.writerow(row_values)
                    rows_processed += 1

        print(f"✅ 成功！已轉換 {rows_processed} 筆資料至: {output_csv_path}")

    except Exception as e:
        print(f"❌ 發生錯誤: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # 支援拖曳檔案 (Drag & Drop)
    # sys.argv[0] 是程式本身，sys.argv[1:] 是拖進來的檔案路徑列表
    if len(sys.argv) < 2:
        print("💡 請將 .datu8 檔案拖曳到這個程式上來執行。")
        input("按 Enter 鍵離開...") # 讓視窗停留
    else:
        for file_path in sys.argv[1:]:
            parse_nexas_dat(file_path)
        
        # 處理完所有檔案後暫停，讓你看到結果
        input("\n所有檔案處理完畢。按 Enter 鍵離開...")