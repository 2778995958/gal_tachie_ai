import os
import csv
import re
from PIL import Image
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# --- 設定 ---
COORDS_FILE = 'hg3_coordinates.txt'
COMMAND_FILE = 'cst_export.csv'
IMAGE_SOURCE_DIR = 'images'
OUTPUT_DIR = 'output'

# --- 核心功能函式 ---

def composite_high_quality(background_img, foreground_img, position):
    """高精度圖片合成函式"""
    base_np = np.array(background_img, dtype=np.float64) / 255.0
    part_np = np.array(foreground_img, dtype=np.float64) / 255.0
    fg_layer = np.zeros_like(base_np)
    dx, dy = position
    part_h, part_w = part_np.shape[:2]
    base_h, base_w = base_np.shape[:2]
    x1_canvas, y1_canvas = max(dx, 0), max(dy, 0)
    x2_canvas, y2_canvas = min(dx + part_w, base_w), min(dy + part_h, base_h)
    x1_part, y1_part = x1_canvas - dx, y1_canvas - dy
    x2_part, y2_part = x2_canvas - dx, y2_canvas - dy
    if x1_canvas < x2_canvas and y1_canvas < y2_canvas:
        fg_layer[y1_canvas:y2_canvas, x1_canvas:x2_canvas] = part_np[y1_part:y2_part, x1_part:x2_part]
    bg_a = base_np[:, :, 3:4]
    fg_a = fg_layer[:, :, 3:4]
    bg_rgb_prem = base_np[:, :, :3] * bg_a
    fg_rgb_prem = fg_layer[:, :, :3] * fg_a
    out_rgb_prem = fg_rgb_prem + bg_rgb_prem * (1.0 - fg_a)
    out_a = fg_a + bg_a * (1.0 - fg_a)
    out_rgb = np.zeros_like(out_rgb_prem)
    mask = out_a > 1e-6
    np.divide(out_rgb_prem, out_a, where=mask, out=out_rgb)
    final_np_float = np.concatenate([out_rgb, out_a], axis=2)
    final_np_uint8 = (np.clip(final_np_float, 0.0, 1.0) * 255).round().astype(np.uint8)
    return Image.fromarray(final_np_uint8, 'RGBA')

def load_coordinates(filepath):
    """從座標檔載入資訊"""
    # ... (此函式內容不變) ...
    coords = {}
    print(f"正在從 {filepath} 讀取座標...")
    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                base_name = os.path.splitext(row['FileName'])[0].lower()
                coords[base_name] = {
                    'OffsetX': int(row['OffsetX']),
                    'OffsetY': int(row['OffsetY']),
                    'CanvasWidth': int(row['CanvasWidth']),
                    'CanvasHeight': int(row['CanvasHeight']),
                    'FragmentWidth': int(row['FragmentWidth']),
                    'FragmentHeight': int(row['FragmentHeight'])
                }
        print(f"成功載入 {len(coords)} 筆座標。")
        return coords
    except Exception as e:
        print(f"讀取座標檔時發生錯誤：{e}")
        return None

def find_largest_base_name(original_base_name, all_coords):
    """使用固定的字串切片邏輯來尋找最大版本"""
    # ... (此函式內容不變) ...
    version_chars = ('l', 'm', 's', 'x')
    if not original_base_name.lower().endswith(version_chars):
        return original_base_name
    original_prefix_cased = original_base_name[:-1]
    search_prefix_lower = original_prefix_cased.lower()
    max_area = -1
    best_effective_base = original_base_name
    for name_key, data in all_coords.items():
        if name_key.startswith(search_prefix_lower):
            area = data['FragmentWidth'] * data['FragmentHeight']
            if area > max_area:
                max_area = area
                temp_base_name = '_'.join(name_key.split('_')[:-1])
                if temp_base_name.lower().endswith(version_chars):
                    new_version_char = temp_base_name[-1]
                    best_effective_base = original_prefix_cased + new_version_char
    return best_effective_base

def process_command(task):
    """
    工人函式：處理單一合成任務。
    task 是一個包含 command_str 和 output_path 的字典。
    """
    command_str = task['command_str']
    output_path = task['output_path']
    # 這裡的 all_coords, IMAGE_SOURCE_DIR 是從外部傳入或作為全域變數，為了簡化，我們讓它在函式內可見
    
    try:
        command_pattern = re.compile(r'(?:cg|bg)\s+\d+\s+([^\s]+)')
        match = command_pattern.search(command_str)
        if not match: return None

        variants_str = match.group(1)
        variants_list = variants_str.split(',')
        original_base_name = variants_list[0]
        variants = variants_list[1:]

        effective_base_name = find_largest_base_name(original_base_name, all_coords)

        potential_layers = []
        for i, variant in enumerate(variants):
            if variant == '0': continue
            padding = '0' * i
            layer_filename = f"{effective_base_name}_{padding}{variant}.png"
            potential_layers.append(layer_filename)
        
        existing_layers = [f for f in potential_layers if os.path.exists(os.path.join(IMAGE_SOURCE_DIR, f))]
        if not existing_layers: return None

        first_layer_name_no_ext = os.path.splitext(existing_layers[0])[0].lower()
        if first_layer_name_no_ext not in all_coords: return None

        first_layer_info = all_coords[first_layer_name_no_ext]
        canvas = Image.new('RGBA', (first_layer_info['CanvasWidth'], first_layer_info['CanvasHeight']), (0, 0, 0, 0))

        final_image = canvas
        for layer_filename in existing_layers:
            layer_name_no_ext = os.path.splitext(layer_filename)[0].lower()
            if layer_name_no_ext not in all_coords: continue

            layer_info = all_coords[layer_name_no_ext]
            offset = (layer_info['OffsetX'], layer_info['OffsetY'])
            image_path = os.path.join(IMAGE_SOURCE_DIR, layer_filename)
            layer_img = Image.open(image_path).convert("RGBA")
            final_image = composite_high_quality(final_image, layer_img, offset)

        final_image.save(output_path)
        return output_path
    except Exception as e:
        print(f"處理指令 '{command_str}' 時發生錯誤: {e}")
        return None

def main():
    """主執行函式 (工頭)"""
    global all_coords # 讓工人函式可以存取
    all_coords = load_coordinates(COORDS_FILE)
    if not all_coords:
        return

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"已建立輸出資料夾: {OUTPUT_DIR}")
        
    # 1. 預先掃描已存在的檔案
    existing_files = set(os.listdir(OUTPUT_DIR))
    print(f"掃描到 {len(existing_files)} 個已存在的檔案。")

    # 2. 讀取所有指令，並過濾掉會產生重複檔名的任務
    tasks = []
    processed_or_queued = existing_files.copy() # 已存在或已在佇列中的
    command_pattern = re.compile(r'(?:cg|bg)\s+\d+\s+([^\s]+)')

    print(f"正在從 {COMMAND_FILE} 準備任務清單...")
    with open(COMMAND_FILE, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            command_str = row.get('command_string', '')
            if '$' in command_str or not command_str.strip():
                continue
            
            match = command_pattern.search(command_str)
            if not match: continue
            
            variants_str = match.group(1)
            variants_list = variants_str.split(',')
            original_base_name = variants_list[0]
            variants = variants_list[1:]
            
            # 這裡的檔名生成需要與 process_command 內部邏輯一致
            effective_base_name = find_largest_base_name(original_base_name, all_coords)
            output_parts = [effective_base_name]
            for i, variant in enumerate(variants):
                if variant == '0': continue
                padding = '0' * i
                padded_variant = f"{padding}{variant}"
                output_parts.append(padded_variant)
            output_filename = "_".join(output_parts) + ".png"
            
            if output_filename not in processed_or_queued:
                tasks.append({
                    'command_str': command_str,
                    'output_path': os.path.join(OUTPUT_DIR, output_filename)
                })
                processed_or_queued.add(output_filename)
    
    if not tasks:
        print("沒有新的圖片需要合成。")
        return

    print(f"準備開始合成 {len(tasks)} 個新圖片...")
    start_time = time.time()
    success_count = 0
    
    # 3. 建立線程池並分發任務
    # os.cpu_count() 會取得你電腦的 CPU 核心數，作為工人數量
    with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        # 提交所有任務
        future_to_task = {executor.submit(process_command, task): task for task in tasks}
        
        # 當任務完成時，取得結果
        for future in as_completed(future_to_task):
            result_path = future.result()
            if result_path:
                print(f"✅ 任務成功: {os.path.basename(result_path)}")
                success_count += 1
    
    end_time = time.time()
    print("\n--------------------------------------------------")
    print(f"全部處理完成！")
    print(f"成功合成 {success_count} 張新圖片。")
    print(f"總耗時: {end_time - start_time:.2f} 秒。")
    print("--------------------------------------------------")


if __name__ == '__main__':
    main()