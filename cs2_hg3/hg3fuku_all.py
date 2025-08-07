import os
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
import itertools
import re
import csv
import numpy as np
import shutil

# --- 核心輔助函式 ---
def ensure_dir(dir_path):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

def get_files_safely(dir_name):
    if not os.path.isdir(dir_name):
        return []
    return sorted([os.path.join(dir_name, f) for f in os.listdir(dir_name) if f.endswith('.png')])

# 【新增】用於提取檔名最後一個底線後綴的輔助函式
def get_last_suffix(file_path):
    if not file_path:
        return ""
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    if '_' in base_name:
        return base_name.rsplit('_', 1)[-1]
    return base_name

# --- 高精度合成函式 ---
def composite_images(base, part_img_path, fuku_base_image_origin_coords, coords_dict):
    try:
        base_img = base if isinstance(base, Image.Image) else Image.open(base).convert('RGBA')
    except Exception as e:
        print(f"警告：讀取基礎圖片 {os.path.basename(str(base))} 時發生錯誤：{e}")
        return None
    try:
        part_img = Image.open(part_img_path).convert("RGBA")
        part_base_name = os.path.splitext(os.path.basename(part_img_path))[0]
        part_x_original, part_y_original = find_coords_for_part(part_base_name, coords_dict)
        dx = part_x_original - fuku_base_image_origin_coords[0]
        dy = part_y_original - fuku_base_image_origin_coords[1]
    except Exception as e:
        print(f"警告：讀取部件圖片 {os.path.basename(part_img_path)} 或獲取座標時發生錯誤：{e}")
        return None
    base_np = np.array(base_img, dtype=np.float64) / 255.0
    part_np = np.array(part_img, dtype=np.float64) / 255.0
    fg_layer = np.zeros_like(base_np)
    part_h, part_w = part_np.shape[:2]
    x1, y1 = max(dx, 0), max(dy, 0)
    x2, y2 = min(dx + part_w, base_np.shape[1]), min(dy + part_h, base_np.shape[0])
    part_x1, part_y1 = x1 - dx, y1 - dy
    part_x2, part_y2 = x2 - dx, y2 - dy
    if x1 < x2 and y1 < y2:
        fg_layer[y1:y2, x1:x2] = part_np[part_y1:part_y2, part_x1:part_x2]
    bg_a = base_np[:, :, 3:4]; fg_a = fg_layer[:, :, 3:4]
    bg_rgb_prem = base_np[:, :, :3] * bg_a; fg_rgb_prem = fg_layer[:, :, :3] * fg_a
    out_rgb_prem = fg_rgb_prem + bg_rgb_prem * (1.0 - fg_a)
    out_a = fg_a + bg_a * (1.0 - fg_a)
    out_rgb = np.zeros_like(out_rgb_prem)
    mask = out_a > 1e-6
    np.divide(out_rgb_prem, out_a, where=mask, out=out_rgb)
    final_np_float = np.concatenate([out_rgb, out_a], axis=2)
    final_np_uint8 = (np.clip(final_np_float, 0.0, 1.0) * 255).round().astype(np.uint8)
    return Image.fromarray(final_np_uint8, 'RGBA')

# --- 座標讀取與查找 ---
def load_hg3_coords(filepath):
    coords = {}
    if not os.path.exists(filepath): return None
    print(f"--- 開始讀取 hg3 座標檔: {filepath} ---")
    try:
        with open(filepath, 'r', encoding='utf-8-sig', errors='ignore') as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                filename = row.get('FileName', '').strip()
                if not filename: continue
                key_name = os.path.splitext(filename)[0]
                if key_name not in coords:
                    coords[key_name] = (int(row['OffsetX']), int(row['OffsetY']))
    except Exception: return None
    print(f"--- 成功讀取 {len(coords)} 筆不重複的座標 ---")
    return coords

def find_coords_for_part(part_base_name, coords_dict):
    if part_base_name in coords_dict:
        return coords_dict[part_base_name]
    match = re.match(r'^(.*)([-_]\d+)$', part_base_name)
    if match and match.group(1) in coords_dict:
        return coords_dict[match.group(1)]
    return 0, 0

# --- Fuku 預處理 ---
def preprocess_fuku_folders(fuku_base_dir, output_dir, coords_dict):
    print("  - 開始預處理 Fuku...")
    ensure_dir(output_dir)
    def layering_sort_key_advanced(filename):
        base_name = os.path.splitext(filename)[0].upper()
        base_name = ''.join(c for c in base_name if c in '0123456789ABCDE')
        if base_name.isdigit(): return (0, int(base_name), filename)
        letter_priorities = {'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5}  
        for letter, priority in letter_priorities.items():
            if letter in base_name: return (priority, filename)
        return (99, filename)
    def get_group_from_location(location_str):
        if location_str == 'root': return 1
        num = int(location_str)
        return 0 if num == 0 else num + 1
    all_fuku_items = []
    for item_name in os.listdir(fuku_base_dir):
        path = os.path.join(fuku_base_dir, item_name)
        if item_name.endswith('.png') and os.path.isfile(path):
             all_fuku_items.append({'type': 'single_image', 'path': path})
        elif os.path.isdir(path):
            all_fuku_items.append({'type': 'folder', 'name': item_name, 'path': path})
    for item in all_fuku_items:
        if item['type'] == 'single_image':
            fuku_path = item['path']
            fuku_base_name = os.path.splitext(os.path.basename(fuku_path))[0]
            output_path = os.path.join(output_dir, os.path.basename(fuku_path))
            if os.path.exists(output_path): continue
            try:
                img = Image.open(fuku_path).convert('RGBA')
                bbox = img.getbbox()
                original_fuku_coords = find_coords_for_part(fuku_base_name, coords_dict)
                if bbox:
                    cropped_img = img.crop(bbox)
                    coords_dict[fuku_base_name] = (original_fuku_coords[0] + bbox[0], original_fuku_coords[1] + bbox[1])
                    cropped_img.save(output_path)
                else:
                    img.save(output_path)
                    coords_dict[fuku_base_name] = original_fuku_coords
            except Exception as e:
                print(f"    - 警告：處理單張服裝 {fuku_base_name}.png 時出錯：{e}")
        elif item['type'] == 'folder':
            clothing_name = item['name']
            output_path = os.path.join(output_dir, f"{clothing_name}.png")
            if os.path.exists(output_path): continue
            all_parts = []
            for f_name in os.listdir(item['path']):
                f_path = os.path.join(item['path'], f_name)
                if os.path.isfile(f_path) and f_path.endswith('.png'):
                    all_parts.append({'path': f_path, 'location': 'root'})
                elif os.path.isdir(f_path) and f_name.isdigit():
                    for sub_f_path in get_files_safely(f_path):
                        all_parts.append({'path': sub_f_path, 'location': f_name})
            all_parts.sort(key=lambda p: (get_group_from_location(p['location']), layering_sort_key_advanced(os.path.basename(p['path']))))
            if not all_parts: continue
            min_x, min_y, max_x, max_y = float('inf'), float('inf'), float('-inf'), float('-inf')
            for part in all_parts:
                part_base_name = os.path.splitext(os.path.basename(part['path']))[0]
                part_coords = find_coords_for_part(part_base_name, coords_dict)
                with Image.open(part['path']) as img:
                    width, height = img.size
                    min_x, min_y, max_x, max_y = min(min_x, part_coords[0]), min(min_y, part_coords[1]), max(max_x, part_coords[0] + width), max(max_y, part_coords[1] + height)
            if min_x > max_x: continue
            canvas_img = Image.new('RGBA', (max_x - min_x, max_y - min_y), (0, 0, 0, 0))
            canvas_origin_coords = (min_x, min_y)
            for part in all_parts:
                canvas_img = composite_images(canvas_img, part['path'], canvas_origin_coords, coords_dict)
            canvas_img.save(output_path)
            coords_dict[clothing_name] = canvas_origin_coords
            print(f"    - ✓ 成功合成資料夾 {clothing_name}.png (原點: {canvas_origin_coords})")


# --- 單一角色處理邏輯 ---
def process_fuku_task(fuku_file, char_name, all_dirs, all_files, coords_dict):
    fuku_base_name = os.path.splitext(fuku_file)[0]
    fuku_path = os.path.join(all_dirs['preprocessed_fuku'], fuku_file)
    fuku_actual_origin_coords = find_coords_for_part(fuku_base_name, coords_dict)

    for kao_path in all_files['kao']:
        # 【V22 修改】使用新的檔名邏輯
        fuku_suffix = get_last_suffix(fuku_file)
        kao_suffix = get_last_suffix(kao_path)
        kami_suffix = get_last_suffix(all_files['kami'][0]) if all_files['kami'] else None
        
        name_parts = [char_name, fuku_suffix, kao_suffix]
        if kami_suffix:
            name_parts.append(kami_suffix)
        
        output_filename_base = "_".join(name_parts)
        
        base_img_for_kami = composite_images(fuku_path, kao_path, fuku_actual_origin_coords, coords_dict)
        if not base_img_for_kami: continue
        
        final_image_to_save = base_img_for_kami
        if all_files['kami']:
            final_image_to_save = composite_images(base_img_for_kami, all_files['kami'][0], fuku_actual_origin_coords, coords_dict)
        
        output_path_temp = os.path.join(all_dirs['temp_base'], f"{output_filename_base}.png")
        if not os.path.exists(output_path_temp):
            final_image_to_save.save(output_path_temp)

def process_single_character(char_dir, coords_dict):
    char_name = os.path.basename(char_dir)
    print(f"\n{'='*20} 開始處理角色: {char_name} {'='*20}")
    
    # 1. 設定來源路徑
    fuku_dir, kao_dir, kami_dir, kuchi_dir, hoho_dir, effect_dir = [os.path.join(char_dir, name) for name in ["fuku", "kao", "kami", "kuchi", "hoho", "effect"]]
    
    # 2. 獲取檔案列表
    # 預處理 Fuku
    output_dir = os.path.join(char_dir, "output")
    preprocessed_fuku_dir = os.path.join(output_dir, "preprocessed_fuku")
    ensure_dir(output_dir)
    preprocess_fuku_folders(fuku_dir, preprocessed_fuku_dir, coords_dict)
    
    fuku_files_processed_names = [os.path.basename(p) for p in get_files_safely(preprocessed_fuku_dir)]
    
    all_files = {
        'kao': get_files_safely(kao_dir), 'kami': get_files_safely(kami_dir),
        'kuchi': get_files_safely(kuchi_dir), 'hoho': get_files_safely(hoho_dir),
        'effect': get_files_safely(effect_dir)
    }

    if not fuku_files_processed_names or not all_files['kao']:
        print(f"  - 角色 {char_name} 的 fuku 或 kao 列表為空，處理終止。")
        return

    # 3. 設定輸出路徑
    temp_base_dir = os.path.join(output_dir, "temp_base")
    kao_kuchi_dir = os.path.join(output_dir, "kao_kuchi")
    ensure_dir(temp_base_dir) # temp_base 和 kao_kuchi 總是需要
    ensure_dir(kao_kuchi_dir)

    all_dirs = {'output': output_dir, 'preprocessed_fuku': preprocessed_fuku_dir, 'temp_base': temp_base_dir}

    # 4. Step 1: 建立 fuku + kao + kami -> temp_base
    print("  - 階段 1: 建立 fuku + kao + kami 基礎圖...")
    max_workers = os.cpu_count() or 4
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_fuku_task, fuku_file, char_name, all_dirs, all_files, coords_dict) for fuku_file in fuku_files_processed_names]
        for future in futures:
            try: future.result()
            except Exception as e: print(f"  -! 一個線程任務發生錯誤: {e}")

    fuku_origin_coords_map = {os.path.splitext(f)[0]: find_coords_for_part(os.path.splitext(f)[0], coords_dict) for f in fuku_files_processed_names}
    
    temp_base_files = get_files_safely(temp_base_dir)
    
    # 5. 【V24 修正】Step 2: -> kao_kuchi (保證此資料夾永遠有內容)
    print("  - 階段 2: 處理 kuchi...")
    for base_path in temp_base_files:
        base_name_no_ext = os.path.splitext(os.path.basename(base_path))[0]
        
        # 如果有 kuchi 檔案，則合成
        if all_files['kuchi']:
            try: fuku_origin = fuku_origin_coords_map.get(base_name_no_ext.split('_')[1], (0,0))
            except IndexError: fuku_origin = (0,0)
            
            for kuchi_path in all_files['kuchi']:
                output_name = f"{base_name_no_ext}_{get_last_suffix(kuchi_path)}.png"
                output_path = os.path.join(kao_kuchi_dir, output_name)
                if not os.path.exists(output_path):
                    canvas = composite_images(base_path, kuchi_path, fuku_origin, coords_dict)
                    if canvas: canvas.save(output_path)
        # 如果沒有 kuchi 檔案，則直接複製
        else:
            output_path = os.path.join(kao_kuchi_dir, os.path.basename(base_path))
            if not os.path.exists(output_path):
                shutil.copy(base_path, output_path)

    # 6. Step 3 & 4 (後續邏輯不變，它們會自動從 kao_kuchi 讀取)
    kao_kuchi_files = get_files_safely(kao_kuchi_dir)

    if all_files['hoho']:
        print("  - 階段 3: 添加 hoho...")
        kao_kuchi_hoho_dir = os.path.join(output_dir, "kao_kuchi_hoho")
        ensure_dir(kao_kuchi_hoho_dir)
        for base_path in kao_kuchi_files:
            base_name_no_ext = os.path.splitext(os.path.basename(base_path))[0]
            try: fuku_origin = fuku_origin_coords_map.get(base_name_no_ext.split('_')[1], (0,0))
            except IndexError: fuku_origin = (0,0)
            for hoho_path in all_files['hoho']:
                output_name = f"{base_name_no_ext}_{get_last_suffix(hoho_path)}.png"
                output_path = os.path.join(kao_kuchi_hoho_dir, output_name)
                if not os.path.exists(output_path):
                    canvas = composite_images(base_path, hoho_path, fuku_origin, coords_dict)
                    if canvas: canvas.save(output_path)
    else:
        kao_kuchi_hoho_dir = kao_kuchi_dir # 指向上一級，保持流程連貫

    if all_files['effect']:
        print("  - 階段 4: 添加 effect...")
        input_dirs_for_effect = []
        if os.path.exists(kao_kuchi_dir) and any(os.scandir(kao_kuchi_dir)):
            input_dirs_for_effect.append(kao_kuchi_dir)
        if kao_kuchi_hoho_dir != kao_kuchi_dir and os.path.exists(kao_kuchi_hoho_dir) and any(os.scandir(kao_kuchi_hoho_dir)):
            input_dirs_for_effect.append(kao_kuchi_hoho_dir)
        
        for input_dir in input_dirs_for_effect:
            effect_output_dir = f"{input_dir}_effect"
            ensure_dir(effect_output_dir)
            for base_path in get_files_safely(input_dir):
                base_name_no_ext = os.path.splitext(os.path.basename(base_path))[0]
                try: fuku_origin = fuku_origin_coords_map.get(base_name_no_ext.split('_')[1], (0,0))
                except IndexError: fuku_origin = (0,0)
                for effect_path in all_files['effect']:
                    output_name = f"{base_name_no_ext}_{get_last_suffix(effect_path)}.png"
                    output_path = os.path.join(effect_output_dir, output_name)
                    if not os.path.exists(output_path):
                        canvas = composite_images(base_path, effect_path, fuku_origin, coords_dict)
                        if canvas: canvas.save(output_path)

    print(f"--- ✓ 角色 {char_name} 處理完成 ---")

def main():
    script_dir = os.getcwd()
    coords_path = os.path.join(script_dir, "hg3_coordinates.txt")
    coords_data = load_hg3_coords(coords_path)
    if not coords_data:
        input("錯誤：找不到或無法讀取座標檔，請按 Enter 鍵結束。")
        return
    character_folders = []
    for item in os.listdir(script_dir):
        item_path = os.path.join(script_dir, item)
        if os.path.isdir(item_path) and os.path.isdir(os.path.join(item_path, "fuku")):
            character_folders.append(item_path)
    if not character_folders:
        print("\n未找到任何有效的角色資料夾。")
        return
    print(f"\n掃描完成！發現 {len(character_folders)} 個待處理的角色資料夾:")
    for folder in character_folders:
        print(f"  - {os.path.basename(folder)}")
    for char_folder in character_folders:
        process_single_character(char_folder, coords_data.copy())
    print(f"\n{'='*50}\n🎉 所有角色均已處理完畢！ 🎉\n{'='*50}")
    input("請按 Enter 鍵結束程式。")

if __name__ == '__main__':
    main()