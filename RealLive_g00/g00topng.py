import os
import struct
import io
import glob
from PIL import Image

def read_u8(stream): return struct.unpack('B', stream.read(1))[0]
def read_u16(stream): return struct.unpack('<H', stream.read(2))[0]
def read_s16(stream): return struct.unpack('<h', stream.read(2))[0]
def read_u32(stream): return struct.unpack('<I', stream.read(4))[0]
def read_s32(stream): return struct.unpack('<i', stream.read(4))[0]

def lz_decompress(stream, min_count=2, bytes_pp=1):
    """
    移植自 C# G00Reader.LzDecompress
    """
    packed_size = read_s32(stream) - 8
    output_size = read_s32(stream)
    
    output = bytearray()
    # 預先分配空間可以優化效能，但在 Python 中動態 append 對於邏輯移植比較簡單直觀
    # 為了準確性和模擬 C# 行為，這裡使用 bytearray 的操作
    
    bits = 2
    while len(output) < output_size and packed_size > 0:
        bits >>= 1
        if bits == 1:
            bits = read_u8(stream) | 0x100
            packed_size -= 1
        
        if (bits & 1) != 0:
            data = stream.read(bytes_pp)
            output.extend(data)
            packed_size -= bytes_pp
        else:
            if packed_size < 2:
                break
            offset = read_u16(stream)
            packed_size -= 2
            
            count = (offset & 0xF) + min_count
            offset >>= 4
            offset *= bytes_pp
            count *= bytes_pp
            
            # 處理重疊複製 (CopyOverlapped)
            # 在 Python 中不能直接切片過去，因為來源和目標可能重疊
            # 例如: dst=10, offset=1 (複製前一個字節), count=5 -> 會重複該字節5次
            current_pos = len(output)
            src_pos = current_pos - offset
            
            for _ in range(count):
                if src_pos < 0 or src_pos >= len(output):
                    # 防禦性編程，防止錯誤數據導致崩潰
                    output.append(0) 
                else:
                    output.append(output[src_pos])
                src_pos += 1

    return bytes(output)

def extract_g00_file(filepath):
    filename = os.path.basename(filepath)
    base_name = os.path.splitext(filename)[0]
    output_dir = os.path.join("output", base_name)
    
    print(f"正在處理: {filename} ...")
    
    with open(filepath, 'rb') as f:
        # 1. 讀取檔頭
        file_type = read_u8(f)
        if file_type != 2:
            print(f"  [跳過] 僅支援 Type 2 (多圖層) 格式，此檔案為 Type {file_type}")
            return

        width = read_u16(f)
        height = read_u16(f)
        count = read_s16(f) # 包含的圖片數量
        
        if count <= 0:
            print("  [錯誤] 圖片數量無效")
            return

        print(f"  尺寸: {width}x{height}, 包含 {count} 張差分")
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # 2. 讀取目錄 (Entries)
        # C# 中是從 offset 9 開始讀取 Entry 的 X, Y
        f.seek(9) 
        entries = []
        for i in range(count):
            entry_x = read_s32(f)
            entry_y = read_s32(f)
            # 跳過 C# 中 index_offset += 0x18 的剩餘部分 (4+4=8 bytes read, need skip 16)
            f.seek(16, 1) 
            entries.append({'id': i, 'x': entry_x, 'y': entry_y})
            
        # 3. 解壓縮主要數據區塊
        # 數據區塊接在目錄之後。目錄大小計算: count * (4+4+16) = count * 24
        # header 9 bytes + directory size
        data_start_offset = 9 + (count * 24)
        f.seek(data_start_offset)
        
        try:
            decompressed_data = lz_decompress(f, min_count=2, bytes_pp=1)
        except Exception as e:
            print(f"  [錯誤] 解壓縮失敗: {e}")
            return

        # 4. 解析解壓縮後的數據結構
        # 這裡包含每個 Entry 的 Offset 和 Size
        with io.BytesIO(decompressed_data) as mem_stream:
            check_count = read_s32(mem_stream)
            if check_count != count:
                print("  [警告] 解壓縮後的數據計數不匹配")
            
            for i in range(count):
                entries[i]['offset'] = read_u32(mem_stream)
                entries[i]['size'] = read_u32(mem_stream)

            # 5. 逐一提取圖片
            for entry in entries:
                if entry['size'] == 0:
                    continue
                
                # 建立全透明畫布
                img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
                
                # 跳轉到該圖片的數據位置
                mem_stream.seek(entry['offset'])
                
                try:
                    tile_type = read_u16(mem_stream) # 應該是 1
                    tile_count = read_u16(mem_stream)
                    
                    if tile_type != 1:
                        print(f"  Skipping entry {entry['id']}, unknown tile type")
                        continue
                        
                    mem_stream.seek(0x70, 1) # Skip unknown header part
                    
                    # 處理每個圖塊 (Tile)
                    for _ in range(tile_count):
                        tx = read_u16(mem_stream)
                        ty = read_u16(mem_stream)
                        read_s16(mem_stream) # unknown
                        tw = read_u16(mem_stream)
                        th = read_u16(mem_stream)
                        mem_stream.seek(0x52, 1) # Skip unknown tile header
                        
                        # 計算絕對座標
                        final_x = tx + entry['x']
                        final_y = ty + entry['y']
                        
                        # 讀取像素數據 (BGRA)
                        pixel_data_size = tw * th * 4
                        pixel_data = mem_stream.read(pixel_data_size)
                        
                        if len(pixel_data) != pixel_data_size:
                            break
                            
                        # 創建 Tile 圖片
                        # 注意: C# 代碼說是 Bgra32，Pillow 讀取時要用 'BGRA'
                        tile_img = Image.frombytes('RGBA', (tw, th), pixel_data, 'raw', 'BGRA')
                        
                        # 貼上到主畫布
                        # img.paste 不支援 Alpha 通道混合貼上，需使用 alpha_composite 或 mask
                        # 但這裡是拼圖，通常不重疊，直接 paste 即可。
                        # 如果需要透明度正確混合，最好用 alpha_composite (需相同大小) 或 paste with mask
                        img.paste(tile_img, (final_x, final_y))
                    
                    # 存檔
                    save_path = os.path.join(output_dir, f"{base_name}_{entry['id']:03d}.png")
                    img.save(save_path)
                    
                except Exception as e:
                    print(f"  [錯誤] 處理圖片 #{entry['id']} 時發生錯誤: {e}")

    print("  完成。")

def main():
    # 搜尋當前目錄下的所有 .g00 檔案
    files = glob.glob("*.g00")
    
    if not files:
        print("找不到 .g00 檔案。請將此腳本放在 .g00 檔案所在的資料夾中。")
        return

    for file in files:
        extract_g00_file(file)

if __name__ == "__main__":
    main()
