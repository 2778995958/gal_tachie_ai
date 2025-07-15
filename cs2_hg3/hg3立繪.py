import os
import csv
import re
from PIL import Image
from collections import defaultdict
import numpy as np
import time
from functools import lru_cache
import gc
from numba import jit
import concurrent.futures
from tqdm import tqdm


# --- 主要設定 ---
MAX_CONCURRENT_WORKERS = 12
CACHE_MAX_SIZE = 64 # LRU 快取大小

CHARLIST_FILENAME = "CharList.cl"
COORDS_FILENAME = "hg3_coordinates.txt"
IMAGES_DIR = "images"
OUTPUT_DIR = "output_sprites"

# --- 工人程序內部使用的全域變數 ---
worker_coords_data = None

# --- 被 LRU 快取裝飾的圖片讀取函式 ---
@lru_cache(maxsize=CACHE_MAX_SIZE)
def load_image_from_disk(layer_key):
    """從硬碟讀取單張圖片，並由 LRU 自動快取。"""
    global worker_coords_data
    if layer_key in worker_coords_data:
        part_info = worker_coords_data[layer_key]
        original_filename = part_info['OriginalFileName']
        img_path = os.path.join(IMAGES_DIR, f"{original_filename}.png")
        if os.path.exists(img_path):
            try:
                with Image.open(img_path) as img:
                    return np.array(img.convert("RGBA"))
            except Exception: return None
    return None

def init_worker():
    """工人初始化：只載入座標檔，並清空快取。"""
    global worker_coords_data
    lines = _read_lines_with_fallback(COORDS_FILENAME)
    if lines is None: return
    worker_coords_data = {}
    reader = csv.DictReader(lines, delimiter='\t')
    for row in reader:
        filename = row['FileName']
        key = os.path.splitext(filename)[0].lower()
        row['OriginalFileName'] = os.path.splitext(filename)[0]
        for col in ['FragmentWidth', 'FragmentHeight', 'OffsetX', 'OffsetY', 'CanvasWidth', 'CanvasHeight']:
            value = row.get(col, '0').strip(); row[col] = int(value if value else '0')
        worker_coords_data[key] = row
    load_image_from_disk.cache_clear()

def process_single_image(args):
    """工人函式，處理單一圖片的合成與儲存。"""
    global worker_coords_data
    if worker_coords_data is None: return (args[1], "失敗：工人未初始化。")
    layers_to_draw, final_filename = args
    canvas_info = None
    for layer_name in layers_to_draw:
        layer_key = layer_name.lower()
        if layer_key in worker_coords_data:
            canvas_info = worker_coords_data[layer_key]
            break
    if canvas_info is None: return (final_filename, "失敗：找不到畫布基準。")
    canvas = np.zeros((canvas_info['CanvasHeight'], canvas_info['CanvasWidth'], 4), dtype=np.uint8)
    for layer_name in layers_to_draw:
        layer_key = layer_name.lower()
        part_np = load_image_from_disk(layer_key)
        if part_np is not None:
            part_info = worker_coords_data[layer_key]
            canvas = numpy_paste_numba(canvas, part_np, part_info['OffsetX'], part_info['OffsetY'])
    try:
        final_image = Image.fromarray(canvas)
        output_path = os.path.join(OUTPUT_DIR, final_filename)
        final_image.save(output_path)
        return (final_filename, "成功")
    except Exception as e:
        return (final_filename, f"失敗：儲存時發生錯誤 - {e}")

def _read_lines_with_fallback(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f: return f.readlines()
    except UnicodeDecodeError:
        try:
            with open(file_path, 'r', encoding='shift_jis') as f: return f.readlines()
        except Exception: return None
    except Exception: return None

@jit(nopython=True)
def numpy_paste_numba(base_canvas_np, part_np, x_offset, y_offset):
    part_h, part_w, _ = part_np.shape
    canvas_h, canvas_w, _ = base_canvas_np.shape
    y1, y2 = max(0, y_offset), min(canvas_h, y_offset + part_h)
    x1, x2 = max(0, x_offset), min(canvas_w, x_offset + part_w)
    part_y1, part_y2 = max(0, -y_offset), min(part_h, canvas_h - y_offset)
    part_x1, part_x2 = max(0, -x_offset), min(part_w, canvas_w - x_offset)
    if y1 >= y2 or x1 >= x2: return base_canvas_np
    for r_canvas in range(y1, y2):
        for c_canvas in range(x1, x2):
            r_part = r_canvas - y_offset + part_y1
            c_part = c_canvas - x_offset + part_x1
            part_r, part_g, part_b, part_a = part_np[r_part, c_part]
            if part_a == 0: continue
            base_r, base_g, base_b, base_a = base_canvas_np[r_canvas, c_canvas]
            part_alpha_norm = part_a / 255.0
            inv_alpha_norm = 1.0 - part_alpha_norm
            final_r = int(part_r * part_alpha_norm + base_r * inv_alpha_norm)
            final_g = int(part_g * part_alpha_norm + base_g * inv_alpha_norm)
            final_b = int(part_b * part_alpha_norm + base_b * inv_alpha_norm)
            final_a = int(part_a + base_a * inv_alpha_norm)
            base_canvas_np[r_canvas, c_canvas] = (final_r, final_g, final_b, final_a)
    return base_canvas_np

def get_sort_key(layer_name):
    """用於排序圖層的輔助函式，確保合成順序正確。"""
    parts = layer_name.split('_', 1)
    if len(parts) < 2: return 0
    return len(parts[1])

def find_all_combinations_recursive(section_key, base_prefix, current_layers, current_filename_parts, cl_data):
    """
    遞迴函式，同時產生用於合成的圖層列表和用於命名的部件列表。
    """
    if section_key not in cl_data or not cl_data[section_key]:
        yield list(current_layers), list(current_filename_parts)
        return

    for line in cl_data[section_key]:
        last_space_index = line.rfind(' ')
        rule_string, next_section_key = line, None
        if last_space_index != -1:
            rule_string, next_section_key = line[:last_space_index], line[last_space_index + 1:]
        
        parts = [p.strip() for p in rule_string.split(',')]
        new_layers = list(current_layers)
        new_filename_parts = list(current_filename_parts)
        
        for i, part in enumerate(parts):
            if part == '@':
                continue # @不作任何紀錄

            # 為圖層列表添加新圖層 (用於合成)
            # 無論是數字還是字母，都使用相同的補零規則
            layer_suffix = "_0" if part == '0' else f"_{'0'*(i-1)}{part}"
            new_layers.append(f"{base_prefix}{layer_suffix}")
            
            # --- 核心修改：統一檔名部件的生成規則 ---
            # 為檔名列表添加新部件 (用於命名)
            filename_suffix = ""
            if part == '0':
                filename_suffix = "_0"
            else: # 對所有其他部件 (包括字母和數字)，都使用補零規則
                filename_suffix = f"_{'0'*(i-1)}{part}"
            
            new_filename_parts.append(filename_suffix)
        
        yield from find_all_combinations_recursive(next_section_key, base_prefix, new_layers, new_filename_parts, cl_data)

def main():
    start_time = time.time()
    print("--- 開始執行立繪生成程式 (最終命名修正版) ---")
    print(f"[*] 最大並行工人數量設定為: {MAX_CONCURRENT_WORKERS}")
    
    print("[*] 主程序正在解析規則以計算任務清單...")
    lines = _read_lines_with_fallback(CHARLIST_FILENAME)
    if not lines: print(f"[!] 找不到或無法讀取規則檔案 {CHARLIST_FILENAME}"); return
    cl_data = {}
    current_section = None
    for line in lines:
        line = line.strip()
        if not line: continue
        if line.startswith('#'):
            current_section = line[1:]
            cl_data[current_section] = []
        elif current_section: cl_data[current_section].append(line)

    tasks_to_process = []
    top_key = "_TOP_"
    if top_key not in cl_data:
        print(f"\n[!] 錯誤: 規則檔案中找不到 '#{top_key}'。"); return
    
    for entry in cl_data[top_key]:
        parts = entry.split()
        if len(parts) < 2: continue
        pose_key = parts[1]
        if pose_key not in cl_data: continue
        for pose_line in cl_data[pose_key]:
            last_space_index = pose_line.rfind(' ')
            if last_space_index == -1: continue
            start_section_key = pose_line[last_space_index + 1:]
            rule_and_prefix_part = pose_line[:last_space_index].strip()
            inline_parts = [p.strip() for p in rule_and_prefix_part.split(',')]
            base_prefix = inline_parts[0]
            
            initial_layers = [base_prefix]
            initial_filename_parts = [base_prefix]
            
            for i, part in enumerate(inline_parts):
                if i == 0 or part == '@': continue
                
                layer_suffix = "_0" if part == '0' else f"_{'0'*(i-1)}{part}"
                initial_layers.append(f"{base_prefix}{layer_suffix}")

                # --- 核心修改：統一檔名部件的生成規則 ---
                filename_suffix = ""
                if part == '0':
                    filename_suffix = "_0"
                else: # 對所有其他部件 (包括字母和數字)，都使用補零規則
                    filename_suffix = f"_{'0'*(i-1)}{part}"

                initial_filename_parts.append(filename_suffix)

            all_combinations = find_all_combinations_recursive(
                start_section_key, base_prefix, initial_layers, initial_filename_parts, cl_data
            )
            
            for unsorted_layers, filename_parts in all_combinations:
                sorted_layers = sorted(unsorted_layers, key=get_sort_key)
                
                custom_filename = "".join(filename_parts) + ".png"
                
                tasks_to_process.append((sorted_layers, custom_filename))

    total_combinations = len(tasks_to_process)
    if total_combinations == 0:
        print("\n[!] 找不到任何可生成的組合。"); return
        
    print(f"    - 計算完成，需生成 {total_combinations} 張圖片。")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print(f"\n[*] 正在啟動 {MAX_CONCURRENT_WORKERS} 個工人程序...")
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=MAX_CONCURRENT_WORKERS, 
        initializer=init_worker
    ) as executor:
        results = list(tqdm(executor.map(process_single_image, tasks_to_process), total=total_combinations, desc="生成進度"))

    success_count = sum(1 for _, status in results if status == "成功")
    fail_count = total_combinations - success_count
    
    print(f"\n{'='*40}")
    print(f"[✓] 所有任務處理完畢！")
    print(f"    - 成功生成: {success_count} 張圖片。")
    if fail_count > 0:
        print(f"    - 生成失敗: {fail_count} 張圖片。")
    print(f"    - 總耗時: {time.time() - start_time:.2f} 秒。")
    print(f"{'='*40}")

if __name__ == '__main__':
    main()