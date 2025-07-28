import os
import shutil
from PIL import Image, ImageChops # 導入 ImageChops 用於裁剪
import itertools
import re
import numpy as np

# --- 核心合成與輔助函式 (保持不變) ---
def ensure_dir(dir_path):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

def load_offset_coords(filepath):
    coords = {}
    if not os.path.exists(filepath):
        print(f"錯誤：在指定路徑找不到通用的座標檔案！\n路徑: {filepath}")
        return None
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'): continue
                parts = line.split(',')
                if len(parts) == 3:
                    name, x_str, y_str = parts[0].strip(), parts[1].strip(), parts[2].strip()
                    try:
                        coords[name] = (int(x_str), int(y_str))
                    except ValueError:
                        print(f"警告：座標檔案中此行格式錯誤，已跳過：{line}")
    except Exception as e:
        print(f"讀取座標檔案 {filepath} 時發生錯誤：{e}")
        return None
    print(f"--- 成功從 {filepath} 讀取 {len(coords)} 筆通用座標 ---")
    return coords

def get_files_safely(dir_name):
    if not os.path.isdir(dir_name):
        return []
    return sorted([f for f in os.listdir(dir_name) if f.endswith('.png')])

def find_coords_for_part(part_base_name, coords_dict):
    if part_base_name in coords_dict:
        return coords_dict[part_base_name]
    if len(part_base_name) > 1:
        potential_key = part_base_name[:-1]
        if potential_key in coords_dict:
            return coords_dict[potential_key]
    return 0, 0

def composite_images(base, part_img_path, fuku_base_image_origin_coords, coords_dict):
    try:
        if isinstance(base, str):
            base_img = Image.open(base).convert('RGBA')
        elif isinstance(base, Image.Image):
            base_img = base if base.mode == 'RGBA' else base.convert('RGBA')
        else: return None
    except Exception as e:
        print(f"警告：讀取基礎圖片 {base} 時發生錯誤：{e}")
        return None

    try:
        part_img = Image.open(part_img_path).convert("RGBA")
        part_base_name = os.path.splitext(os.path.basename(part_img_path))[0]
        
        part_x_original, part_y_original = find_coords_for_part(part_base_name, coords_dict)
        
        dx = part_x_original - fuku_base_image_origin_coords[0]
        dy = part_y_original - fuku_base_image_origin_coords[1]
        
    except Exception as e:
        print(f"警告：讀取部件圖片 {part_img_path} 或獲取座標時發生錯誤：{e}")
        return None
    
    base_np = np.array(base_img, dtype=np.float64) / 255.0
    part_np = np.array(part_img, dtype=np.float64) / 255.0

    fg_layer = np.zeros_like(base_np)

    part_h, part_w = part_np.shape[:2]
    base_h, base_w = base_np.shape[:2]

    x1, y1 = max(dx, 0), max(dy, 0)
    x2, y2 = min(dx + part_w, base_w), min(dy + part_h, base_h)

    part_x1, part_y1 = x1 - dx, y1 - dy
    part_x2, part_y2 = x2 - dx, y2 - dy

    if x1 < x2 and y1 < y2:
        fg_layer[y1:y2, x1:x2] = part_np[part_y1:part_y2, part_x1:part_x2]

    bg_rgb, bg_a = base_np[:,:,:3], base_np[:,:,3:4]
    fg_rgb, fg_a = fg_layer[:,:,:3], fg_layer[:,:,3:4]

    out_a = fg_a + bg_a * (1.0 - fg_a)
    out_rgb = np.zeros_like(bg_rgb)

    mask = out_a > 1e-6
    numerator = fg_rgb * fg_a + bg_rgb * bg_a * (1.0 - fg_a)
    np.divide(numerator, out_a, where=mask, out=out_rgb)

    final_np_float = np.concatenate([out_rgb, out_a], axis=2)
    final_np_uint8 = (final_np_float * 255).round().astype(np.uint8)

    return Image.fromarray(final_np_uint8, 'RGBA')

## ---
## **Fuku 預處理邏輯：處理單張與子資料夾**
## ---

def preprocess_fuku_folders(fuku_base_dir, output_dir, coords_dict):
    """
    預處理 fuku 資料夾，生成合併或單獨的 fuku 圖片，
    並在 coords_dict 中記錄這些圖片的實際像素原點在原始大圖座標系中的位置。
    """
    print("  - 開始預處理 Fuku...")
    ensure_dir(output_dir)
    
    def layering_sort_key_advanced(filename):
        base_name = os.path.splitext(filename)[0].upper()
        if base_name.isdigit(): return (0, int(base_name), filename)
        letter_priorities = {'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5}  
        for letter, priority in letter_priorities.items():
            if letter in base_name: return (priority, filename)
        return (99, filename)
        
    def get_group_from_location(location_str):
        if location_str == 'root': return 1 
        num = int(location_str)
        if num == 0: return 0 
        else: return num + 1 

    all_fuku_items = []

    # 1. 收集直接放在 fuku/ 下的單張 png 圖片
    standalone_pngs = get_files_safely(fuku_base_dir)
    for png_file in standalone_pngs:
        all_fuku_items.append({'type': 'single_image', 'path': os.path.join(fuku_base_dir, png_file)})

    # 2. 收集 fuku/ 下的子資料夾
    clothing_subdirs = [d for d in os.listdir(fuku_base_dir) if os.path.isdir(os.path.join(fuku_base_dir, d))]
    for clothing_name in clothing_subdirs:
        all_fuku_items.append({'type': 'folder', 'name': clothing_name, 'path': os.path.join(fuku_base_dir, clothing_name)})

    if not all_fuku_items:
        print("    - 沒有找到任何 Fuku 圖片或資料夾，跳過預處理。")
        return

    print(f"    - 發現 {len(all_fuku_items)} 個 Fuku 項目，開始處理。")

    for item in all_fuku_items:
        if item['type'] == 'single_image':
            # 處理單張圖片
            fuku_path = item['path']
            fuku_file = os.path.basename(fuku_path)
            fuku_base_name = os.path.splitext(fuku_file)[0]
            output_path = os.path.join(output_dir, fuku_file)

            # 獲取單張 fuku 的原始絕對座標
            original_fuku_coords = find_coords_for_part(fuku_base_name, coords_dict)
            
            if os.path.exists(output_path):
                print(f"    - 單張服裝 {fuku_base_name} 已存在，跳過。")
                # 即使跳過，也要確保 coords_dict 中有其正確的原始座標
                if fuku_base_name not in coords_dict:
                    coords_dict[fuku_base_name] = original_fuku_coords
                continue

            try:
                img = Image.open(fuku_path).convert('RGBA')
                
                # --- 新增邏輯：裁切多餘空白並計算新原點 ---
                # 找到圖片的實際內容邊界
                bbox = img.getbbox() 
                
                if bbox: # 如果圖片不是完全透明的
                    # 裁剪圖片到實際內容大小
                    cropped_img = img.crop(bbox)
                    
                    # 計算裁剪後圖片的 (0,0) 像素在原始大圖座標系中的新位置
                    # 原始 fuku 的 (0,0) 在原始大圖是 original_fuku_coords
                    # 裁剪框的左上角 (bbox[0], bbox[1]) 在原始 fuku 中
                    # 所以裁剪後圖片的 (0,0) 在原始大圖中是 original_fuku_coords + (bbox[0], bbox[1])
                    new_fuku_origin_x = original_fuku_coords[0] + bbox[0]
                    new_fuku_origin_y = original_fuku_coords[1] + bbox[1]

                    cropped_img.save(output_path)
                    print(f"    - ✓ 成功預處理單張服裝 {fuku_base_name}.png (裁剪後，實際原點: ({new_fuku_origin_x}, {new_fuku_origin_y}))。")
                    
                    # 將裁剪後的實際原點存回 coords_dict
                    coords_dict[fuku_base_name] = (new_fuku_origin_x, new_fuku_origin_y)
                else: # 圖片是完全透明的
                    print(f"    - 警告：單張服裝 {fuku_base_name}.png 為空或完全透明，將複製為透明圖片。其原點將為 {original_fuku_coords}。")
                    # 即使是透明圖片，也按原始座標記錄，讓其他部件可以正確對齊到一個「空」的位置
                    img.save(output_path)
                    coords_dict[fuku_base_name] = original_fuku_coords # 保持原始座標，因為沒有裁剪

            except Exception as e:
                print(f"    - 警告：處理單張服裝 {fuku_base_name}.png 時發生錯誤：{e}，已跳過。")
                continue

        elif item['type'] == 'folder':
            # 處理資料夾 (這部分邏輯保持不變，因為它已經正確地裁剪了空白並記錄了原點)
            clothing_name = item['name']
            output_path = os.path.join(output_dir, f"{clothing_name}.png")

            if os.path.exists(output_path):
                print(f"    - 服裝 {clothing_name} 已存在，跳過。")
                # 如果已經存在，我們假設它的偏移量之前已經被計算並儲存了
                continue

            print(f"    - 處理服裝資料夾: {clothing_name}")
            clothing_dir_path = item['path']
            
            all_parts = []
            for f in get_files_safely(clothing_dir_path):
                all_parts.append({'path': os.path.join(clothing_dir_path, f), 'location': 'root'})
            
            for sub_item in os.listdir(clothing_dir_path):
                sub_item_path = os.path.join(clothing_dir_path, sub_item)
                if os.path.isdir(sub_item_path) and sub_item.isdigit():
                    for f in get_files_safely(sub_item_path):
                        all_parts.append({'path': os.path.join(sub_item_path, f), 'location': sub_item})
            
            all_parts.sort(key=lambda p: (get_group_from_location(p['location']), layering_sort_key_advanced(os.path.basename(p['path']))))
            
            sorted_filenames = [f"(組{get_group_from_location(p['location'])}) {os.path.relpath(p['path'], clothing_dir_path)}" for p in all_parts]
            print(f"      - 排序後圖層順序: {sorted_filenames}")
            
            parts_for_canvas_calc = []
            min_x, min_y = float('inf'), float('inf')
            max_x, max_y = float('-inf'), float('-inf')

            for part_info in all_parts:
                part_path = part_info['path']
                part_base_name = os.path.splitext(os.path.basename(part_path))[0]
                part_original_coords = find_coords_for_part(part_base_name, coords_dict)
                
                try:
                    with Image.open(part_path) as img:
                        width, height = img.size
                        parts_for_canvas_calc.append({'path': part_path, 'original_pos': part_original_coords, 'width': width, 'height': height})
                        
                        min_x = min(min_x, part_original_coords[0])
                        min_y = min(min_y, part_original_coords[1])
                        max_x = max(max_x, part_original_coords[0] + width)
                        max_y = max(max_y, part_original_coords[1] + height)
                except Exception as e:
                    print(f"      - 警告：讀取部件 {part_path} 時發生錯誤：{e}，已跳過。")
                    continue

            if not parts_for_canvas_calc:
                print(f"      - 警告：在 {clothing_name} 中找不到任何有效部件或無法讀取，無法生成。")
                continue

            canvas_width = max_x - min_x
            canvas_height = max_y - min_y
            
            canvas_img = Image.new('RGBA', (canvas_width, canvas_height), (0, 0, 0, 0))
            
            for part_info in all_parts:
                found_part_data = next((p for p in parts_for_canvas_calc if p['path'] == part_info['path']), None)
                if found_part_data:
                    adjusted_pos_x = found_part_data['original_pos'][0] - min_x
                    adjusted_pos_y = found_part_data['original_pos'][1] - min_y
                    
                    try:
                        part_img = Image.open(found_part_data['path']).convert('RGBA')
                        canvas_img.paste(part_img, (adjusted_pos_x, adjusted_pos_y), part_img)
                    except Exception as e:
                        print(f"      - 警告：貼圖部件 {found_part_data['path']} 時發生錯誤：{e}")

            if canvas_img:
                canvas_img.save(output_path)
                print(f"      - ✓ 成功合成 {clothing_name}.png，並儲存。")
                coords_dict[clothing_name] = (min_x, min_y)
            else:
                print(f"      - 錯誤：合成 {clothing_name}.png 失敗。")
                
    print("  - Fuku 預處理完畢。")

## ---
## **單一角色處理邏輯 (保留所有循環和輸出路徑)**
## ---

def process_single_character(char_dir, offset_coords):
    char_name = os.path.basename(char_dir)
    print(f"\n{'='*20} 開始處理角色: {char_name} {'='*20}")
    FUKU_DIR, KAO_DIR, KAMI_DIR, KUCHI_DIR, HOHO_DIR, EFFECT_DIR = (os.path.join(char_dir, name) for name in ["fuku", "kao", "kami", "kuchi", "hoho", "effect"])
    
    kao_files = get_files_safely(KAO_DIR)
    kami_files = get_files_safely(KAMI_DIR)
    kuchi_files = get_files_safely(KUCHI_DIR)
    hoho_files = get_files_safely(HOHO_DIR)
    global_effect_files = get_files_safely(EFFECT_DIR)

    MAX_EFFECT_LAYERS = 1 # 根據你的需求設定最大疊加層數
    
    OUTPUT_ROOT = os.path.join(char_dir, "output")
    PREPROCESSED_FUKU_DIR = os.path.join(OUTPUT_ROOT, "preprocessed_fuku")
    TEMP_BASE_DIR = os.path.join(OUTPUT_ROOT, "temp_base")

    ensure_dir(OUTPUT_ROOT)
    ensure_dir(PREPROCESSED_FUKU_DIR)
    
    preprocess_fuku_folders(FUKU_DIR, PREPROCESSED_FUKU_DIR, offset_coords)
    
    fuku_files = get_files_safely(PREPROCESSED_FUKU_DIR)
    
    print(f"  - 檔案檢查：找到 {len(fuku_files)} 個已處理的 fuku 檔案，{len(kao_files)} 個 kao 檔案。")
    if not fuku_files or not kao_files:
        print(f"  - 錯誤：角色 {char_name} 的 fuku 或 kao 列表為空，無法繼續組合，已跳過。")
        return

    # --- Step 1: fuku + kao + kami -> temp_base ---
    print("\n  Step 1: fuku + kao + kami -> temp_base")
    if os.path.exists(TEMP_BASE_DIR): shutil.rmtree(TEMP_BASE_DIR)
    ensure_dir(TEMP_BASE_DIR)

    for fuku_file in fuku_files:
        fuku_base_name = os.path.splitext(fuku_file)[0]
        fuku_path = os.path.join(PREPROCESSED_FUKU_DIR, fuku_file)
        
        fuku_actual_origin_coords = find_coords_for_part(fuku_base_name, offset_coords) 
        print(f"    - 處理基礎組合: {fuku_base_name} (fuku圖片的實際原點: {fuku_actual_origin_coords})")

        for kao_file in kao_files:
            output_filename_base = f"{char_name}_{fuku_base_name}_{os.path.splitext(kao_file)[0]}"
            
            base_img_for_kami = composite_images(fuku_path, os.path.join(KAO_DIR, kao_file), 
                                                fuku_actual_origin_coords, offset_coords)
            
            if not base_img_for_kami: continue

            if kami_files:
                for kami_file in kami_files:
                    final_base_output_name = f"{output_filename_base}_{os.path.splitext(kami_file)[0]}.png"
                    output_path_temp = os.path.join(TEMP_BASE_DIR, final_base_output_name)
                    
                    if not os.path.exists(output_path_temp):
                        composed = composite_images(base_img_for_kami.copy(), os.path.join(KAMI_DIR, kami_file), 
                                                    fuku_actual_origin_coords, offset_coords)
                        if composed: 
                            composed.save(output_path_temp)
                            print(f"      ✓ 生成 {final_base_output_name}")
            else:
                final_base_output_name = f"{output_filename_base}.png"
                output_path_temp = os.path.join(TEMP_BASE_DIR, final_base_output_name)
                if not os.path.exists(output_path_temp):
                    base_img_for_kami.save(output_path_temp)
                    print(f"      ✓ 生成 {final_base_output_name} (無kami)")


    # --- Step 2: 從 temp_base 讀取，合成 kuchi 和 fuku_specific_effect ---
    print("\n  Step 2: temp_base + kuchi + fuku_specific_effect -> kao_kuchi")
    KAO_KUCHI_DIR = os.path.join(OUTPUT_ROOT, "kao_kuchi")
    ensure_dir(KAO_KUCHI_DIR)

    for fuku_file in fuku_files:
        fuku_base_name = os.path.splitext(fuku_file)[0]
        fuku_actual_origin_coords = find_coords_for_part(fuku_base_name, offset_coords)
        fuku_specific_effect_dir = os.path.join(FUKU_DIR, fuku_base_name, "effect")
        fuku_specific_effect_files = get_files_safely(fuku_specific_effect_dir)
        
        temp_base_files_for_fuku = [f for f in get_files_safely(TEMP_BASE_DIR) if fuku_base_name in f]

        for base_file in temp_base_files_for_fuku:
            base_name_no_ext = os.path.splitext(base_file)[0]
            base_path = os.path.join(TEMP_BASE_DIR, base_file)

            if kuchi_files:
                for kuchi_file in kuchi_files:
                    final_name = f"{base_name_no_ext}_{os.path.splitext(kuchi_file)[0]}.png"
                    output_path_kuchi = os.path.join(KAO_KUCHI_DIR, final_name)
                    
                    if not os.path.exists(output_path_kuchi):
                        current_image = composite_images(base_path, os.path.join(KUCHI_DIR, kuchi_file), 
                                                        fuku_actual_origin_coords, offset_coords)
                        
                        if not current_image: continue

                        if fuku_specific_effect_files:
                            for effect_file in fuku_specific_effect_files:
                                current_image = composite_images(current_image.copy(), os.path.join(fuku_specific_effect_dir, effect_file), 
                                                                fuku_actual_origin_coords, offset_coords)
                                if not current_image: break
                        
                        if current_image: 
                            current_image.save(output_path_kuchi)
                            print(f"      ✓ 生成 {final_name}")
            else:
                final_name = f"{base_name_no_ext}.png"
                output_path_kuchi = os.path.join(KAO_KUCHI_DIR, final_name)
                
                if not os.path.exists(output_path_kuchi):
                    current_image = Image.open(base_path).convert('RGBA')
                    
                    if fuku_specific_effect_files:
                        for effect_file in fuku_specific_effect_files:
                            current_image = composite_images(current_image.copy(), os.path.join(fuku_specific_effect_dir, effect_file), 
                                                            fuku_actual_origin_coords, offset_coords)
                            if not current_image: break
                    
                    if current_image: 
                        current_image.save(output_path_kuchi)
                        print(f"      ✓ 生成 {final_name} (無kuchi，有fuku_effect)" if fuku_specific_effect_files else f"      ✓ 生成 {final_name} (無kuchi，無fuku_effect)")


    # --- Step 3: 從 kao_kuchi 讀取，合成 hoho ---
    print("\n  Step 3: kao_kuchi + hoho -> kao_kuchi_hoho")
    if hoho_files:
        KAO_KUCHI_HOHO_DIR = os.path.join(OUTPUT_ROOT, "kao_kuchi_hoho")
        ensure_dir(KAO_KUCHI_HOHO_DIR)
        
        for fuku_file in fuku_files:
            fuku_base_name = os.path.splitext(fuku_file)[0]
            fuku_actual_origin_coords = find_coords_for_part(fuku_base_name, offset_coords)
            
            kao_kuchi_files_for_fuku = [f for f in get_files_safely(KAO_KUCHI_DIR) if fuku_base_name in f]

            for base_file in kao_kuchi_files_for_fuku:
                base_name_no_ext = os.path.splitext(base_file)[0]
                base_path = os.path.join(KAO_KUCHI_DIR, base_file)
                
                for hoho_file in hoho_files:
                    final_name = f"{base_name_no_ext}_{os.path.splitext(hoho_file)[0]}.png"
                    output_path_hoho = os.path.join(KAO_KUCHI_HOHO_DIR, final_name)
                    
                    if not os.path.exists(output_path_hoho):
                        composed = composite_images(base_path, os.path.join(HOHO_DIR, hoho_file), 
                                                    fuku_actual_origin_coords, offset_coords)
                        if composed: 
                            composed.save(output_path_hoho)
                            print(f"      ✓ 生成 {final_name}")
    else:
        print("  - 無 hoho 檔案，跳過 Step 3。")

    # --- Step 4: 從 kao_kuchi_hoho 或 kao_kuchi 讀取，合成 global_effect ---
    print("\n  Step 4: 合成 Global Effect")
    
    input_dirs_to_process = [] # 要處理的輸入目錄及其對應的輸出目錄
    
    # 這裡的邏輯需要確保所有組合都被考慮到，即使沒有 hoho，也要處理 kao_kuchi + effect
    if hoho_files: # 如果有 hoho，處理 kao_kuchi_hoho + effect
        input_dirs_to_process.append({
            'input': os.path.join(OUTPUT_ROOT, "kao_kuchi_hoho"),
            'output': os.path.join(OUTPUT_ROOT, "kao_kuchi_hoho_effect")
        })
    
    # 處理 kao_kuchi + effect (無論是否有 hoho，這都是一個獨立的輸出分支)
    input_dirs_to_process.append({
        'input': os.path.join(OUTPUT_ROOT, "kao_kuchi"),
        'output': os.path.join(OUTPUT_ROOT, "kao_kuchi_effect")
    })

    if not global_effect_files:
        print("  - 無 global_effect 檔案，跳過 Step 4。")
        return

    for dir_pair in input_dirs_to_process:
        current_input_dir = dir_pair['input']
        current_output_dir = dir_pair['output']

        if not os.path.isdir(current_input_dir):
            print(f"    - 輸入目錄 '{current_input_dir}' 不存在，跳過。")
            continue
        
        ensure_dir(current_output_dir)

        for fuku_file in fuku_files:
            fuku_base_name = os.path.splitext(fuku_file)[0]
            fuku_actual_origin_coords = find_coords_for_part(fuku_base_name, offset_coords)
            
            base_files_for_fuku = [f for f in get_files_safely(current_input_dir) if fuku_base_name in f]

            for base_file in base_files_for_fuku:
                base_name_no_ext = os.path.splitext(base_file)[0]
                base_path = os.path.join(current_input_dir, base_file)

                for size in range(1, MAX_EFFECT_LAYERS + 1):
                    if len(global_effect_files) < size: continue
                    
                    for effect_combo in itertools.combinations(global_effect_files, size):
                        combo_suffix = "_".join(sorted([os.path.splitext(f)[0] for f in effect_combo]))
                        final_name = f"{base_name_no_ext}_{combo_suffix}.png"
                        output_path_effect = os.path.join(current_output_dir, final_name)
                        
                        if not os.path.exists(output_path_effect):
                            composed = Image.open(base_path).convert('RGBA')
                            
                            for effect_file in effect_combo:
                                composed = composite_images(composed, os.path.join(EFFECT_DIR, effect_file), 
                                                            fuku_actual_origin_coords, offset_coords)
                                if not composed: break
                            
                            if composed: 
                                composed.save(output_path_effect)
                                print(f"      ✓ 生成 {final_name}")
    print(f"--- ✓ 角色 {char_name} 處理完畢 ---")


## ---
## **主程式入口**
## ---

def main():
    script_dir = os.getcwd()
    print(f"程式啟動於: {script_dir}")
    offset_file_path = os.path.join(script_dir, "Kaguya_XY_Offset(Auto).txt")
    
    offset_coords = load_offset_coords(offset_file_path)
    if offset_coords is None:
        input("錯誤：找不到或無法讀取座標檔，請按 Enter 鍵結束。")
        return

    character_folders = []
    print("開始掃描所有子資料夾...")
    for item in os.listdir(script_dir):
        item_path = os.path.join(script_dir, item)
        if os.path.isdir(item_path):
            fuku_path = os.path.join(item_path, "fuku")
            kao_path = os.path.join(item_path, "kao")
            if os.path.isdir(fuku_path) and os.path.isdir(kao_path):
                character_folders.append(item_path)

    if not character_folders:
        print("\n在目前資料夾下，沒有找到任何包含 'fuku' 和 'kao' 的角色資料夾。")
        input("請檢查資料夾結構，然後按 Enter 鍵結束。")
        return

    print(f"\n掃描完成！發現 {len(character_folders)} 個待處理的角色資料夾:")
    for folder in character_folders:
        print(f"  - {os.path.basename(folder)}")

    for char_folder in character_folders:
        process_single_character(char_folder, offset_coords)

    print(f"\n{'='*50}\n🎉 所有角色均已處理完畢！ 🎉\n{'='*50}")
    input("請按 Enter 鍵結束程式。")

if __name__ == '__main__':
    main()