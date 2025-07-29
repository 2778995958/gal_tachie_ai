import os
import json
from PIL import Image
import numpy as np
from typing import Dict, List, Tuple, Optional

# --- 基礎設定 ---
CGLIST_FILENAME = "cglist.lst"
OFFSET_FILENAME = "offset.json"
OUTPUT_DIR_NAME = "output"
EXCLUDE_DIRS = [OUTPUT_DIR_NAME, '.git', '__pycache__']

# --- 工具函式 ---

def ensure_dir(dir_path: str):
    """確保資料夾存在，如果不存在則建立。"""
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

def find_exact_folder(base_dir: str, folder_name: str) -> Optional[str]:
    """在指定目錄下遞迴尋找名稱完全相符的資料夾。"""
    for root, dirs, _ in os.walk(base_dir):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        if folder_name in dirs:
            return os.path.join(root, folder_name)
    return None

def parse_cglist_into_sections(lines: List[str]) -> Dict[str, List[str]]:
    """
    ★★★ 新增函式 ★★★
    將 cglist.lst 的內容解析成以 [section] 為單位的字典。
    """
    sections = {}
    current_section_name = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith('[') and line.endswith(']'):
            current_section_name = line[1:-1]
            sections[current_section_name] = []
        elif current_section_name and ',' in line:
            sections[current_section_name].append(line)
    return sections

def load_and_prepare_offsets(offset_path: str) -> Dict[str, Tuple[int, int]]:
    """載入 offset.json 並轉換成易於查詢的字典格式。"""
    offsets = {}
    if not os.path.exists(offset_path):
        print(f"  [警告] 座標檔不存在: {offset_path}")
        return offsets
    try:
        with open(offset_path, 'r', encoding='utf-8-sig') as f:
            data = json.load(f)
        prepared_offsets = {}
        if isinstance(data, list):
            for item in data:
                if 'Key' in item and 'Value' in item and isinstance(item['Value'], list) and len(item['Value']) >= 2:
                    prepared_offsets[item['Key'].lower()] = tuple(item['Value'][:2])
        elif isinstance(data, dict):
             for key, value in data.items():
                if isinstance(value, list) and len(value) >= 2:
                    prepared_offsets[key.lower()] = tuple(value[:2])
        return prepared_offsets
    except Exception as e:
        print(f"  [錯誤] 無法讀取或解析座標檔 {offset_path}: {e}")
        return {}

def composite_images_numpy(
    parts_to_composite: List[Tuple[str, Image.Image]],
    offset_data: Dict[str, Tuple[int, int]]
) -> Optional[Image.Image]:
    """使用 NumPy 陣列來高效率合成圖片。"""
    if not parts_to_composite: return None
    min_x, min_y, max_x, max_y = float('inf'), float('inf'), float('-inf'), float('-inf')

    for key, img in parts_to_composite:
        pos = offset_data.get(key.lower())
        if not pos:
            print(f"    [警告] 在 offset.json 中找不到鍵 '{key.lower()}' 的座標，跳過此部件。")
            continue
        x, y = pos
        w, h = img.size
        min_x, min_y = min(min_x, x), min(min_y, y)
        max_x, max_y = max(max_x, x + w), max(max_y, y + h)

    if any(v == float('inf') or v == float('-inf') for v in [min_x, min_y, max_x, max_y]):
        print("    [錯誤] 無法確定畫布尺寸。")
        return None

    canvas_width, canvas_height = max_x - min_x, max_y - min_y
    global_offset_x, global_offset_y = -min_x, -min_y
    base_canvas_np = np.zeros((canvas_height, canvas_width, 4), dtype=np.uint8)
    print(f"    > 建立畫布，尺寸: {canvas_width}x{canvas_height}，全局偏移: ({global_offset_x}, {global_offset_y})")

    for key, part_img in parts_to_composite:
        pos = offset_data.get(key.lower())
        if not pos: continue
        part_np = np.array(part_img.convert("RGBA"), dtype=np.uint8)
        part_h, part_w, _ = part_np.shape
        x, y = pos[0] + global_offset_x, pos[1] + global_offset_y
        x1, y1 = max(x, 0), max(y, 0)
        x2, y2 = min(x + part_w, canvas_width), min(y + part_h, canvas_height)
        part_x1, part_y1 = x1 - x, y1 - y
        part_x2, part_y2 = x2 - x, y2 - y
        if x1 >= x2 or y1 >= y2: continue
        base_region = base_canvas_np[y1:y2, x1:x2]
        part_region = part_np[part_y1:part_y2, part_x1:part_x2]
        part_alpha = (part_region[:, :, 3] / 255.0)[:, :, np.newaxis]
        blended_rgb = (part_region[:, :, :3] * part_alpha + base_region[:, :, :3] * (1 - part_alpha)).astype(np.uint8)
        new_alpha = (part_region[:, :, 3] + base_region[:, :, 3] * (1 - part_alpha.squeeze())).astype(np.uint8)
        base_canvas_np[y1:y2, x1:x2, :3] = blended_rgb
        base_canvas_np[y1:y2, x1:x2, 3] = new_alpha
    return Image.fromarray(base_canvas_np)

# --- 核心處理邏輯 ---

def process_cglist(file_path: str):
    """處理單一 cglist.lst 檔案。"""
    base_dir = os.path.dirname(file_path)
    print(f"\n{'='*25} 開始處理檔案: {os.path.basename(file_path)} {'='*25}")

    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"  [錯誤] 無法讀取 {file_path}: {e}")
        return

    # ★★★ 關鍵修改 1: 將檔案內容解析成區塊 ★★★
    sections = parse_cglist_into_sections(lines)
    if not sections:
        print("  [警告] 在檔案中沒有找到任何有效的 `[section]` 區塊。")
        return

    # ★★★ 關鍵修改 2: 遍歷每個區塊，而不是整個檔案 ★★★
    for section_name, lines_in_section in sections.items():
        print(f"\n--- 正在處理區塊: [{section_name}] (共 {len(lines_in_section)} 行) ---")

        # ★★★ 關鍵修改 3: 使用 enumerate 來獲取每個區塊內的流水號 (idx) ★★★
        for idx, line in enumerate(lines_in_section):
            # 流水號從 1 開始
            counter = idx + 1
            formatted_counter = f"{counter:02d}"

            parts = [p.strip() for p in line.split(',')]
            if len(parts) < 2:
                continue

            folder_base = parts[0]
            folder_suffix = parts[1]
            target_folder_name = folder_base + folder_suffix
            
            print(f"\n  [行 {idx+1}/{len(lines_in_section)}] 處理: {line} (流水號: {formatted_counter})")
            
            image_folder = find_exact_folder(base_dir, target_folder_name)
            if not image_folder:
                print(f"    [警告] 找不到資源資料夾 '{target_folder_name}'，跳過此行。")
                continue
            
            offset_path = os.path.join(image_folder, OFFSET_FILENAME)
            offset_data = load_and_prepare_offsets(offset_path)
            if not offset_data:
                print(f"    [警告] 座標檔為空或讀取失敗，跳過此行。")
                continue

            parts_to_composite = []
            for part_idx, code in enumerate(parts[1:]):
                if not code or code == '0' or code == '@':
                    continue
                
                key_for_filename = f"{part_idx}_{code.lower()}"
                key_for_offset = f"{part_idx}_{code}" # 保留原始大小寫給 offset
                filename = f"{key_for_filename}.png"
                filepath = os.path.join(image_folder, filename)

                if os.path.exists(filepath):
                    try:
                        img = Image.open(filepath)
                        parts_to_composite.append((key_for_offset, img))
                    except Exception as e:
                        print(f"    [警告] 無法開啟圖片檔 {filename}: {e}")
                else:
                    print(f"    [警告] 找不到部件檔案: {filename}")

            if not parts_to_composite:
                print("    [資訊] 沒有找到任何有效的圖片部件來合成，跳過。")
                continue
                
            final_image = composite_images_numpy(parts_to_composite, offset_data)
            for _, img in parts_to_composite:
                img.close()

            if final_image:
                output_dir = os.path.join(base_dir, OUTPUT_DIR_NAME, section_name)
                ensure_dir(output_dir)
                
                # ★★★ 關鍵修改 4: 使用新的流水號規則建立檔名 ★★★
                filename_suffix = '_'.join(parts[1:])
                output_filename = f"{folder_base}_{formatted_counter}_{filename_suffix}.png"
                output_path = os.path.join(output_dir, output_filename)
                
                try:
                    final_image.save(output_path)
                    print(f"    > √ 合成成功！已儲存至: {os.path.relpath(output_path, base_dir)}")
                except Exception as e:
                    print(f"    > X 儲存失敗: {e}")
            else:
                print("    > X 合成失敗！")

# --- 主程式入口 ---
def main():
    script_dir = os.getcwd()
    print(f"開始掃描目標資料夾於: {script_dir}")
    
    cl_files_to_process = []
    for root, dirs, files in os.walk(script_dir):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        if CGLIST_FILENAME in files:
            cl_files_to_process.append(os.path.join(root, CGLIST_FILENAME))
            
    if not cl_files_to_process:
        print(f"\n在當前目錄及子目錄中，未找到任何可處理的 '{CGLIST_FILENAME}' 檔案。")
        return
        
    print(f"\n找到 {len(cl_files_to_process)} 個 '{CGLIST_FILENAME}' 檔案，準備處理...")
    
    for cl_path in cl_files_to_process:
        process_cglist(cl_path)
        
    print(f"\n{'='*60}\n所有檔案處理完畢！\n{'='*60}")

if __name__ == '__main__':
    main()