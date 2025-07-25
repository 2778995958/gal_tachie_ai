import os
import struct
import io
from PIL import Image

def un_premultiply_alpha(image: Image.Image) -> Image.Image:
    """對 PIL.Image 物件進行 Alpha Un-premultiplication 處理。"""
    if image.mode != 'RGBA':
        return image

    pixels = image.load()
    width, height = image.size

    for x in range(width):
        for y in range(height):
            r, g, b, a = pixels[x, y]
            if a != 0 and a != 255:
                r = (r * 255) // a
                g = (g * 255) // a
                b = (b * 255) // a
                pixels[x, y] = (r, g, b, a)
                
    return image

def extract_pna_data(pna_filepath: str, image_output_dir: str):
    """
    從單一 PNA 檔案提取圖片和數據。
    這個函數現在會回傳數據，而不是直接寫入檔案。
    """
    print(f"\n[+] 正在處理檔案: {os.path.basename(pna_filepath)}")
    base_name = os.path.splitext(os.path.basename(pna_filepath))[0]
    
    individual_frames_dir = os.path.join(image_output_dir, 'individual_frames', base_name)
    os.makedirs(individual_frames_dir, exist_ok=True)

    try:
        with open(pna_filepath, 'rb') as f:
            if f.read(4) != b'PNAP':
                print(f"  [!] 錯誤: 這不是一個有效的 PNA 檔案。")
                return None, None

            f.seek(0x10)
            count = struct.unpack('<I', f.read(4))[0]
            if count <= 0 or count > 10000:
                print(f"  [!] 錯誤: 檔案中的幀數 ({count}) 無效。")
                return None, None

            print(f"  [*] 發現 {count} 個圖像幀。正在讀取索引...")
            
            index_offset = 0x14
            current_data_offset = index_offset + count * 0x28

            entries = []
            for i in range(count):
                f.seek(index_offset + 8)
                offset_x = struct.unpack('<i', f.read(4))[0]
                offset_y = struct.unpack('<i', f.read(4))[0]
                width = struct.unpack('<I', f.read(4))[0]
                height = struct.unpack('<I', f.read(4))[0]
                
                f.seek(index_offset + 0x24)
                size = struct.unpack('<I', f.read(4))[0]
                
                if size > 0:
                    entries.append({
                        'id': i, 'offset': current_data_offset, 'size': size,
                        'x': offset_x, 'y': offset_y, 'width': width, 'height': height
                    })
                    current_data_offset += size
                index_offset += 0x28

            if not entries:
                print("  [!] 此 PNA 檔案中沒有可提取的有效數據。")
                return None, None

            total_width = max(e['x'] + e['width'] for e in entries)
            total_height = max(e['y'] + e['height'] for e in entries)
            
            print(f"  [*] 正在建立拼合畫布，尺寸: {total_width}x{total_height}")
            composite_image = Image.new('RGBA', (total_width, total_height), (0, 0, 0, 0))

            for entry in entries:
                f.seek(entry['offset'])
                image_data = f.read(entry['size'])
                
                try:
                    image_stream = io.BytesIO(image_data)
                    frame_image = Image.open(image_stream).convert("RGBA")
                    frame_image = un_premultiply_alpha(frame_image)
                    
                    individual_frame_path = os.path.join(individual_frames_dir, f"{base_name}_{entry['id']:03d}.png")
                    frame_image.save(individual_frame_path, 'PNG')

                    composite_image.paste(frame_image, (entry['x'], entry['y']), frame_image)
                except Exception as e:
                    print(f"  [!] 處理第 {entry['id']} 幀時失敗: {e}")
            
            composite_path = os.path.join(image_output_dir, f"{base_name}_COMPOSITE.png")
            composite_image.save(composite_path, 'PNG')
            print(f"  [✔] 成功提取 {len(entries)} 個單獨幀並生成拼合圖。")

            # 回傳解析出的數據列表和檔案基本名
            return entries, base_name

    except Exception as e:
        print(f"  [!] 處理檔案時發生未知錯誤: {e}")
        return None, None

def batch_process_all(input_dir: str, image_output_dir: str, master_txt_path: str):
    """
    批量處理所有 PNA 檔案，並將所有數據寫入單一的 master TXT 檔案。
    """
    os.makedirs(image_output_dir, exist_ok=True)
    
    print(f"--- 開始批量提取 (合併數據模式) ---")
    print(f"來源資料夾: {input_dir}")
    print(f"圖片輸出到: {image_output_dir}")
    print(f"所有數據將合併到: {master_txt_path}")
    
    # 在循環外打開主文件，以便追加寫入
    with open(master_txt_path, 'w', encoding='utf-8') as master_file:
        # 寫入標頭，新增一欄 PnaFile
        master_file.write("PnaFile,FrameID,FileName,X,Y,Width,Height\n")
        
        found_pna_files = False
        for filename in os.listdir(input_dir):
            if filename.lower().endswith('.pna'):
                found_pna_files = True
                pna_filepath = os.path.join(input_dir, filename)
                
                # 獲取從單個 PNA 文件中解析出的數據
                entries, base_name = extract_pna_data(pna_filepath, image_output_dir)
                
                # 如果成功獲取數據，就寫入主文件
                if entries and base_name:
                    for entry in entries:
                        frame_filename = f"{base_name}_{entry['id']:03d}.png"
                        # 格式化每一行，並在開頭加入來源文件名
                        line = f"{base_name},{entry['id']},{frame_filename},{entry['x']},{entry['y']},{entry['width']},{entry['height']}\n"
                        master_file.write(line)
        
        if not found_pna_files:
            print("\n在來源資料夾中沒有找到任何 .pna 檔案。")
    
    print(f"\n--- 批量提取完成 ---")
    print(f"[✔] 所有座標數據已成功寫入到 {master_txt_path}")

if __name__ == '__main__':
    # --- 使用者設定 ---
    INPUT_DIRECTORY = 'pna_files'
    IMAGE_OUTPUT_DIRECTORY = 'output'
    
    # 所有數據合併後的檔名
    MASTER_TXT_PATH = 'master_coordinates.txt'
    # ------------------
    
    if not os.path.isdir(INPUT_DIRECTORY):
        print(f"錯誤！輸入資料夾 '{INPUT_DIRECTORY}' 不存在。")
    else:
        batch_process_all(INPUT_DIRECTORY, IMAGE_OUTPUT_DIRECTORY, MASTER_TXT_PATH)