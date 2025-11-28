import os
import struct
import io
import glob
import re  # 新增: 用於處理檔名正則
from PIL import Image

# ================= 設定區 =================
# 輸出資料夾名稱
OUTPUT_DIR = "merged_results"
# =========================================

# --- 基礎二進位讀取函式 (保持不變) ---
def read_u8(stream): return struct.unpack('B', stream.read(1))[0]
def read_u16(stream): return struct.unpack('<H', stream.read(2))[0]
def read_s16(stream): return struct.unpack('<h', stream.read(2))[0]
def read_u32(stream): return struct.unpack('<I', stream.read(4))[0]
def read_s32(stream): return struct.unpack('<i', stream.read(4))[0]

# --- LZ 解壓縮算法 (保持不變) ---
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

# --- G00 檔案讀取器 (保持不變) ---
def load_images_from_g00(filepath):
    images = []
    filename = os.path.basename(filepath)
    base_name_no_ext = os.path.splitext(filename)[0]
    
    with open(filepath, 'rb') as f:
        if read_u8(f) != 2: return [] 
        width = read_u16(f)
        height = read_u16(f)
        count = read_s16(f)
        
        f.seek(9)
        entries = []
        for i in range(count):
            ex = read_s32(f)
            ey = read_s32(f)
            f.seek(16, 1)
            entries.append({'id': i, 'x': ex, 'y': ey})
            
        data_start = 9 + (count * 24)
        f.seek(data_start)
        try:
            decompressed = lz_decompress(f)
        except:
            print(f"  [Error] 解壓失敗: {filename}")
            return []

        with io.BytesIO(decompressed) as mem:
            if read_s32(mem) != count: return []
            
            for i in range(count):
                entries[i]['offset'] = read_u32(mem)
                entries[i]['size'] = read_u32(mem)
                
            for entry in entries:
                if entry['size'] == 0: continue
                
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
                    
                    img_name = f"{base_name_no_ext}_{entry['id']:03d}"
                    images.append({'name': img_name, 'img': img})
                    
                except Exception as e:
                    print(f"  [Error] 處理圖片錯誤: {e}")
                    
    return images

# --- 主邏輯：分組與合成 (已修改) ---
def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    # 1. 掃描與分組
    groups = {}
    g00_files = glob.glob("*.g00")
    
    print(f"找到 {len(g00_files)} 個 .g00 檔案，開始智慧分析...")

    for path in g00_files:
        fname = os.path.basename(path)
        fname_lower = fname.lower()
        
        parts = fname_lower.split('_')
        if len(parts) < 2: continue # 至少要有 bs1_hl 這樣的結構
        
        # --- 智慧解析 Key ---
        # 假設結構是：角色_服裝... (bs1_hl01... 或 bs1_hl...)
        char_id = parts[0]   # bs1
        costume_part = parts[1] # hl01 或 hl
        
        # 使用正則表達式提取純字母部分 (將 hl01 變成 hl)
        # 這樣 bs1_hl01 和 bs1_hl 就會變成同一個 Key
        match = re.match(r"([a-zA-Z]+)", costume_part)
        if match:
            costume_root = match.group(1) # 取出 hl
        else:
            costume_root = costume_part # 如果沒有字母就保持原樣

        group_key = f"{char_id}_{costume_root}" # Key 變成 bs1_hl

        # 初始化群組
        if group_key not in groups:
            groups[group_key] = {'bases': [], 'faces': []}
            
        # --- 判斷類型 (Base vs Face) ---
        # 判斷 Base: 檔名中有 'base'
        if 'base' in fname_lower:
            groups[group_key]['bases'].append(path)
            
        # 判斷 Face: 檔名中有 '_f' 接數字 (例如 _f01)
        elif re.search(r"_f\d+", fname_lower):
            groups[group_key]['faces'].append(path)
        
        else:
            # 沒標示 base 也沒 _f01，暫時跳過或你可以決定預設值
            # print(f"  [Info] 未知類型的檔案 (跳過): {fname}")
            pass

    # 2. 執行處理
    for prefix, data in groups.items():
        base_files = data['bases']
        face_files = data['faces']
        
        # 排序檔案，讓處理順序比較好讀
        base_files.sort()
        face_files.sort()

        if not base_files:
            continue
        
        # 如果有身體檔案，但沒有對應的表情檔案，還是可以單獨輸出身體 (選用)
        # 這裡的邏輯是：如果沒表情檔，就只會跳過合成，不會報錯
        if not face_files:
            print(f"群組 [{prefix}] 只有身體，沒有找到對應表情 (bs1_hl_f... )，跳過合成。")
            continue
            
        print(f"\n正在處理群組: [{prefix}]")
        print(f"  - 身體檔 ({len(base_files)}個): {[os.path.basename(b) for b in base_files]}")
        print(f"  - 表情檔 ({len(face_files)}個): {[os.path.basename(f) for f in face_files]}")
        
        # 載入表情 (因為表情通常通用，所以先載入)
        print("  正在載入表情差分...")
        loaded_faces = []
        for f_path in face_files:
            loaded_faces.extend(load_images_from_g00(f_path))
            
        if not loaded_faces:
            print("  [警報] 表情檔案讀取後為空，跳過此群組。")
            continue

        # 逐一處理身體
        for b_path in base_files:
            b_fname = os.path.basename(b_path)
            print(f"  正在處理身體檔案: {b_fname}")
            loaded_bases = load_images_from_g00(b_path)
            
            # === 矩陣合成 ===
            for b_item in loaded_bases:
                base_img = b_item['img']
                base_name = b_item['name'] # 這裡會是 bs1_hl01_base01_000
                
                for f_item in loaded_faces:
                    face_img = f_item['img']
                    face_name = f_item['name'] # 這裡會是 bs1_hl_f01_01_000
                    
                    if base_img.size != face_img.size:
                        continue
                        
                    try:
                        merged = Image.alpha_composite(base_img, face_img)
                        
                        # 檔名優化: 
                        # 組合出身體與表情的唯一名稱
                        # 範例結果: bs1_hl01_base01_000__f01_01_000.png
                        
                        # 簡化表情名稱，只取後面的編號部分以免檔名太長
                        # 從 bs1_hl_f01_01_000 取出 f01_01_000
                        short_face_name = "_".join(face_name.split('_')[2:]) 
                        
                        save_name = f"{base_name}__{short_face_name}.png"
                        save_path = os.path.join(OUTPUT_DIR, save_name)
                        
                        merged.save(save_path)
                    except Exception as e:
                        print(f"合成錯誤: {e}")

            del loaded_bases
        del loaded_faces
        print(f"  [{prefix}] 群組完成。")

    print("\n所有作業結束。結果已存於 merged_results 資料夾。")

if __name__ == "__main__":
    main()
