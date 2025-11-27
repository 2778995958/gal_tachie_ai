import os
import struct
import io
import glob
from PIL import Image

# ================= 設定區 =================
# 輸出資料夾名稱
OUTPUT_DIR = "merged_results"
# =========================================

# --- 基礎二進位讀取函式 ---
def read_u8(stream): return struct.unpack('B', stream.read(1))[0]
def read_u16(stream): return struct.unpack('<H', stream.read(2))[0]
def read_s16(stream): return struct.unpack('<h', stream.read(2))[0]
def read_u32(stream): return struct.unpack('<I', stream.read(4))[0]
def read_s32(stream): return struct.unpack('<i', stream.read(4))[0]

# --- LZ 解壓縮算法 (移植自 C#) ---
def lz_decompress(stream, min_count=2, bytes_pp=1):
    packed_size = read_s32(stream) - 8
    output_size = read_s32(stream)
    output = bytearray()
    
    bits = 2
    while len(output) < output_size and packed_size > 0:
        bits >>= 1
        if bits == 1:
            bits = read_u8(stream) | 0x100
            packed_size -= 1
        
        if (bits & 1) != 0:
            output.extend(stream.read(bytes_pp))
            packed_size -= bytes_pp
        else:
            if packed_size < 2: break
            offset = read_u16(stream)
            packed_size -= 2
            count = (offset & 0xF) + min_count
            offset >>= 4
            offset *= bytes_pp
            count *= bytes_pp
            
            current_pos = len(output)
            src_pos = current_pos - offset
            for _ in range(count):
                if src_pos < 0 or src_pos >= len(output):
                    output.append(0)
                else:
                    output.append(output[src_pos])
                src_pos += 1
    return bytes(output)

# --- G00 檔案讀取器 (回傳圖片列表) ---
def load_images_from_g00(filepath):
    """
    讀取一個 g00 檔案，並回傳該檔案包含的所有差分圖片物件列表。
    格式: [{'name': 'base11_000', 'img': PIL.Image}, ...]
    """
    images = []
    filename = os.path.basename(filepath)
    base_name_no_ext = os.path.splitext(filename)[0]
    
    with open(filepath, 'rb') as f:
        # 檢查 Header
        if read_u8(f) != 2: return [] # 只支援 Type 2
        width = read_u16(f)
        height = read_u16(f)
        count = read_s16(f)
        
        # 讀取 Entries 目錄
        f.seek(9)
        entries = []
        for i in range(count):
            ex = read_s32(f)
            ey = read_s32(f)
            f.seek(16, 1)
            entries.append({'id': i, 'x': ex, 'y': ey})
            
        # 解壓縮數據
        data_start = 9 + (count * 24)
        f.seek(data_start)
        try:
            decompressed = lz_decompress(f)
        except:
            print(f"  [Error] 解壓失敗: {filename}")
            return []

        # 解析與繪圖
        with io.BytesIO(decompressed) as mem:
            if read_s32(mem) != count: return []
            
            # 讀取內部 Offset
            for i in range(count):
                entries[i]['offset'] = read_u32(mem)
                entries[i]['size'] = read_u32(mem)
                
            # 構建圖片
            for entry in entries:
                if entry['size'] == 0: continue
                
                # 建立全尺寸透明畫布
                img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
                mem.seek(entry['offset'])
                
                try:
                    tile_type = read_u16(mem)
                    tile_count = read_u16(mem)
                    if tile_type != 1: continue
                    mem.seek(0x70, 1)
                    
                    for _ in range(tile_count):
                        tx = read_u16(mem)
                        ty = read_u16(mem)
                        read_s16(mem)
                        tw = read_u16(mem)
                        th = read_u16(mem)
                        mem.seek(0x52, 1)
                        
                        final_x = tx + entry['x']
                        final_y = ty + entry['y']
                        
                        pixel_data = mem.read(tw * th * 4)
                        if len(pixel_data) != tw * th * 4: break
                        
                        tile = Image.frombytes('RGBA', (tw, th), pixel_data, 'raw', 'BGRA')
                        img.paste(tile, (final_x, final_y))
                    
                    # 將構建好的圖片存入列表
                    img_name = f"{base_name_no_ext}_{entry['id']:03d}"
                    images.append({'name': img_name, 'img': img})
                    
                except Exception as e:
                    print(f"  [Error] 處理圖片錯誤: {e}")
                    
    return images

# --- 主邏輯：分組與合成 ---
def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    # 1. 掃描與分組
    # groups[prefix] = {'bases': [files], 'faces': [files]}
    groups = {}
    g00_files = glob.glob("*.g00")
    
    print(f"找到 {len(g00_files)} 個 .g00 檔案，開始分析...")

    for path in g00_files:
        fname = os.path.basename(path)
        parts = fname.split('_')
        if len(parts) < 3: continue
        
        # 識別碼: bs1_mk1
        prefix = f"{parts[0]}_{parts[1]}"
        if prefix not in groups:
            groups[prefix] = {'bases': [], 'faces': []}
            
        if 'base' in fname.lower():
            groups[prefix]['bases'].append(path)
        elif 'face' in fname.lower():
            groups[prefix]['faces'].append(path)

    # 2. 執行處理
    for prefix, data in groups.items():
        base_files = data['bases']
        face_files = data['faces']
        
        if not base_files or not face_files:
            continue
            
        print(f"\n正在處理群組: [{prefix}] (身體: {len(base_files)} 檔, 表情: {len(face_files)} 檔)")
        
        # 預先載入該群組的所有表情到記憶體 (因為表情通常較小且重複使用)
        print("  正在載入表情差分...")
        loaded_faces = []
        for f_path in face_files:
            loaded_faces.extend(load_images_from_g00(f_path))
            
        if not loaded_faces:
            print("  沒有讀取到任何表情圖片，跳過。")
            continue

        # 逐一處理身體檔案
        for b_path in base_files:
            print(f"  正在處理身體檔案: {os.path.basename(b_path)}")
            # 載入當前身體檔案的所有差分
            loaded_bases = load_images_from_g00(b_path)
            
            # === 矩陣合成 ===
            for b_item in loaded_bases:
                base_img = b_item['img']
                base_name = b_item['name']
                
                for f_item in loaded_faces:
                    face_img = f_item['img']
                    face_name = f_item['name']
                    
                    # 檢查尺寸 (理論上 G00 格式解出來的都是全畫布尺寸，所以應該相同)
                    if base_img.size != face_img.size:
                        continue
                        
                    # 合成 (Alpha Composite 對於臉紅/半透明至關重要)
                    # 這裡使用 Image.alpha_composite 必須確保兩張圖都是 RGBA 且一樣大
                    try:
                        merged = Image.alpha_composite(base_img, face_img)
                        
                        # 儲存
                        save_name = f"{prefix}__{base_name}__{face_name}.png"
                        # 簡化檔名邏輯: 去除重複的前綴，讓檔名短一點 (選擇性)
                        # save_name = f"{base_name}__{face_name.split('_')[-1]}.png" 
                        
                        save_path = os.path.join(OUTPUT_DIR, save_name)
                        merged.save(save_path)
                    except Exception as e:
                        print(f"合成錯誤: {e}")

            # 處理完一個身體檔後，釋放該身體圖片記憶體
            del loaded_bases

        # 處理完該群組後，釋放表情記憶體
        del loaded_faces
        print(f"  [{prefix}] 完成。")

    print("\n所有作業結束。結果已存於 merged_results 資料夾。")

if __name__ == "__main__":
    main()