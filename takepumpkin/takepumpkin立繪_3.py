import os
from concurrent.futures import ThreadPoolExecutor
import shutil
from PIL import Image, ImageChops # 導入 ImageChops 用於裁剪
import itertools
import re
import csv
import numpy as np

# --- 核心合成與輔助函式 (保持不變) ---
def ensure_dir(dir_path):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

def load_offset_coords(filepath):
    """
    讀取新的 CSV 格式座標檔 (Kaguya_XY_Offset.txt)。
    - 解析 CSV 格式。
    - 鍵名為 source_file 去除副檔名。
    - 對於多影格的同一鍵名，只記錄其首次出現的座標。
    """
    coords = {}
    if not os.path.exists(filepath):
        print(f"錯誤：在指定路徑找不到座標檔案！\n路徑: {filepath}")
        return None
    
    print(f"--- 開始讀取新格式座標檔: {filepath} ---")
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            # 使用 csv 模組來讀取，更安全
            reader = csv.reader(f)
            
            # 跳過標頭行
            header = next(reader, None)
            print(f"    - 偵測到標頭: {header}")

            processed_keys = set() # 用來追蹤已經處理過的鍵

            for i, row in enumerate(reader):
                # 基本檢查，確保行中有足夠的資料
                if len(row) < 4:
                    print(f"警告：第 {i+2} 行資料欄位不足，已跳過。")
                    continue

                source_file = row[0].strip()
                x_str = row[2].strip()
                y_str = row[3].strip()

                # 產生鍵名：去除副檔名
                key_name = os.path.splitext(source_file)[0]

                # 規則：如果這個鍵已經處理過，就跳過，以確保只使用第一筆
                if key_name in processed_keys:
                    continue

                try:
                    # 將座標轉換為整數並儲存
                    coords[key_name] = (int(x_str), int(y_str))
                    # 將此鍵標記為已處理
                    processed_keys.add(key_name)
                except ValueError:
                    print(f"警告：座標檔案中第 {i+2} 行座標格式錯誤，已跳過：{row}")

    except Exception as e:
        print(f"讀取座標檔案 {filepath} 時發生錯誤：{e}")
        return None
        
    print(f"--- 成功讀取 {len(coords)} 筆不重複的座標 ---")
    return coords

def get_files_safely(dir_name):
    if not os.path.isdir(dir_name):
        return []
    return sorted([f for f in os.listdir(dir_name) if f.endswith('.png')])

def find_coords_for_part(part_base_name, coords_dict):
    """
    為指定的部件檔名查找座標。
    - 首先嘗試直接匹配。
    - 如果失敗，則嘗試去除 "-數字" 或 "_數字" 的影格後綴再進行匹配。
    """
    # 1. 優先嘗試直接匹配 (適用於檔名完全一樣的情況)
    if part_base_name in coords_dict:
        return coords_dict[part_base_name]

    # 2. 嘗試去除影格後綴進行匹配 (例如: "名稱-001" -> "名稱")
    #    使用正則表達式匹配結尾的 - 或 _ 跟著一串數字
    match = re.match(r'^(.*)([-_]\d+)$', part_base_name)
    if match:
        # 如果匹配成功，group(1) 就是不包含後綴的基礎名稱
        key_prefix = match.group(1)
        if key_prefix in coords_dict:
            return coords_dict[key_prefix]

    # 3. 如果都找不到，返回預設座標 (0, 0)
    return 0, 0

def composite_images(base, part_img_path, fuku_base_image_origin_coords, coords_dict):
    """
    使用「預乘 Alpha Blending」工作流程來合成圖片，以消除透明邊緣的灰線問題。
    """
    try:
        if isinstance(base, str):
            base_img = Image.open(base).convert('RGBA')
        elif isinstance(base, Image.Image):
            base_img = base if base.mode == 'RGBA' else base.convert('RGBA')
        else:
            return None
    except Exception as e:
        print(f"警告：讀取基礎圖片 {base} 時發生錯誤：{e}")
        return None

    try:
        part_img = Image.open(part_img_path).convert("RGBA")
        part_base_name = os.path.splitext(os.path.basename(part_img_path))[0]
        
        part_x_original, part_y_original = find_coords_for_part(part_base_name, coords_dict)
        
        # 核心偏移量計算：部件的原始絕對座標 - fuku 基礎圖的原始絕對座標
        dx = part_x_original - fuku_base_image_origin_coords[0]
        dy = part_y_original - fuku_base_image_origin_coords[1]
        
    except Exception as e:
        print(f"警告：讀取部件圖片 {part_img_path} 或獲取座標時發生錯誤：{e}")
        return None
    
    # --- 核心合成邏輯：預乘 Alpha Blending ---

    # 1. 將 PIL 影像轉換為 NumPy 浮點數陣列 (0.0-1.0)
    base_np = np.array(base_img, dtype=np.float64) / 255.0
    part_np = np.array(part_img, dtype=np.float64) / 255.0

    # 2. 準備前景圖層 (將部件圖放置在與背景相同大小的畫布上)
    fg_layer = np.zeros_like(base_np)
    part_h, part_w = part_np.shape[:2]
    base_h, base_w = base_np.shape[:2]

    # 計算有效的貼上區域，防止部件超出邊界
    x1, y1 = max(dx, 0), max(dy, 0)
    x2, y2 = min(dx + part_w, base_w), min(dy + part_h, base_h)
    
    part_x1, part_y1 = x1 - dx, y1 - dy
    part_x2, part_y2 = x2 - dx, y2 - dy
    
    # 如果有重疊區域，則將部件像素複製到前景圖層
    if x1 < x2 and y1 < y2:
        fg_layer[y1:y2, x1:x2] = part_np[part_y1:part_y2, part_x1:part_x2]

    # 3. 分離 RGBA 色版
    bg_a = base_np[:, :, 3:4]
    fg_a = fg_layer[:, :, 3:4]
    
    # 4.【關鍵步驟】預乘 Alpha：將 RGB 色版乘以其 Alpha 值
    bg_rgb_prem = base_np[:, :, :3] * bg_a
    fg_rgb_prem = fg_layer[:, :, :3] * fg_a

    # 5.【關鍵步驟】混合預乘後的顏色
    # 公式: C_out = C_fg_prem + C_bg_prem * (1 - a_fg)
    out_rgb_prem = fg_rgb_prem + bg_rgb_prem * (1.0 - fg_a)

    # 6. 計算輸出的 Alpha 色版 (此公式不變)
    # 公式: a_out = a_fg + a_bg * (1 - a_fg)
    out_a = fg_a + bg_a * (1.0 - fg_a)

    # 7.【關鍵步驟】還原 (Un-premultiply)：將混合後的 RGB 除以新的 Alpha 值
    # 為了避免除以零，我們只在 Alpha > 0 的地方進行計算
    out_rgb = np.zeros_like(out_rgb_prem)
    mask = out_a > 1e-6 # 使用一個極小值來建立遮罩，避免浮點數不精確問題
    np.divide(out_rgb_prem, out_a, where=mask, out=out_rgb) # 安全地執行除法

    # 8. 將結果合併並轉換回 8-bit (0-255) 圖片格式
    final_np_float = np.concatenate([out_rgb, out_a], axis=2)
    # 進行四捨五入可以得到更精確的結果，然後才轉換型別
    final_np_uint8 = (np.clip(final_np_float, 0.0, 1.0) * 255).round().astype(np.uint8)

    return Image.fromarray(final_np_uint8, 'RGBA')

## ---
## **Fuku 預處理邏輯：處理單張與子資料夾**
## ---

def preprocess_fuku_folders(fuku_base_dir, output_dir, coords_dict):
    """
    預處理 fuku 資料夾。此版本已更新，
    無論是處理單張圖片還是合成資料夾，所有合成操作
    均統一使用 composite_images 函式，以確保最高的圖像品質並消除灰邊。
    """
    print("  - 開始預處理 Fuku...")
    ensure_dir(output_dir)
    
    # --- 內部輔助函式 (排序邏輯不變) ---
    def layering_sort_key_advanced(filename):
        base_name = os.path.splitext(filename)[0].upper()
        # --- 新增修改 ---
        # 在檢查前，先將檔名中可能的全形字母轉換為半形
        base_name = base_name.replace('Ａ', 'A').replace('Ｂ', 'B').replace('Ｃ', 'C').replace('Ｄ', 'D').replace('Ｅ', 'E')
        # --- 修改結束 ---

        if base_name.isdigit(): return (0, int(base_name), filename)
        
        letter_priorities = {'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5}  
        for letter, priority in letter_priorities.items():
            if letter in base_name: 
                # 成功找到優先級，返回 (優先級數字, 檔名)
                return (priority, filename)
        
        # 如果上面都沒找到，則視為普通圖層，給予最低優先級 99
        return (99, filename)
        
    def get_group_from_location(location_str):
        if location_str == 'root': return 1 
        num = int(location_str)
        if num == 0: return 0 
        else: return num + 1 

    # --- 收集所有 Fuku 項目 (邏輯不變) ---
    all_fuku_items = []
    standalone_pngs = get_files_safely(fuku_base_dir)
    for png_file in standalone_pngs:
        all_fuku_items.append({'type': 'single_image', 'path': os.path.join(fuku_base_dir, png_file)})

    clothing_subdirs = [d for d in os.listdir(fuku_base_dir) if os.path.isdir(os.path.join(fuku_base_dir, d))]
    for clothing_name in clothing_subdirs:
        all_fuku_items.append({'type': 'folder', 'name': clothing_name, 'path': os.path.join(fuku_base_dir, clothing_name)})

    if not all_fuku_items:
        print("    - 沒有找到任何 Fuku 圖片或資料夾，跳過預處理。")
        return

    print(f"    - 發現 {len(all_fuku_items)} 個 Fuku 項目，開始處理。")

    for item in all_fuku_items:
        # --- 處理單張 Fuku 圖片 (邏輯不變，它只做裁剪，不涉及合成) ---
        if item['type'] == 'single_image':
            fuku_path = item['path']
            fuku_file = os.path.basename(fuku_path)
            fuku_base_name = os.path.splitext(fuku_file)[0]
            output_path = os.path.join(output_dir, fuku_file)

            original_fuku_coords = find_coords_for_part(fuku_base_name, coords_dict)
            
            if os.path.exists(output_path):
                print(f"    - 單張服裝 {fuku_base_name} 已存在，跳過。")
                if fuku_base_name not in coords_dict:
                    coords_dict[fuku_base_name] = original_fuku_coords
                continue

            try:
                img = Image.open(fuku_path).convert('RGBA')
                bbox = img.getbbox() 
                
                if bbox:
                    cropped_img = img.crop(bbox)
                    new_fuku_origin_x = original_fuku_coords[0] + bbox[0]
                    new_fuku_origin_y = original_fuku_coords[1] + bbox[1]
                    cropped_img.save(output_path)
                    print(f"    - ✓ 成功預處理單張服裝 {fuku_base_name}.png (裁剪後，實際原點: ({new_fuku_origin_x}, {new_fuku_origin_y}))。")
                    coords_dict[fuku_base_name] = (new_fuku_origin_x, new_fuku_origin_y)
                else:
                    print(f"    - 警告：單張服裝 {fuku_base_name}.png 為空，將複製透明圖。其原點為 {original_fuku_coords}。")
                    img.save(output_path)
                    coords_dict[fuku_base_name] = original_fuku_coords
            except Exception as e:
                print(f"    - 警告：處理單張服裝 {fuku_base_name}.png 時發生錯誤：{e}，已跳過。")
                continue

        # --- 【核心修改】處理 Fuku 資料夾 ---
        elif item['type'] == 'folder':
            clothing_name = item['name']
            output_path = os.path.join(output_dir, f"{clothing_name}.png")

            if os.path.exists(output_path):
                print(f"    - 服裝 {clothing_name} 已存在，跳過。")
                continue

            print(f"    - 處理服裝資料夾: {clothing_name}")
            clothing_dir_path = item['path']
            
            # 1. 收集並排序所有部件圖層 (邏輯不變)
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
            
            # 2. 計算所有部件構成的整體邊界，以確定最終畫布大小
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

            # 3. 【全新合成流程】
            canvas_width = max_x - min_x
            canvas_height = max_y - min_y
            
            # 建立一個初始的、完全透明的畫布作為合成底圖
            canvas_img = Image.new('RGBA', (canvas_width, canvas_height), (0, 0, 0, 0))
            
            # 這個新畫布的原點(0,0)在全局座標系中的位置是(min_x, min_y)
            canvas_origin_coords = (min_x, min_y)
            
            # 逐層呼叫 composite_images 進行高品質合成
            for part_info in all_parts:
                part_path = part_info['path']
                
                # 將當前部件疊加到已合成的 canvas_img 上
                updated_canvas = composite_images(
                    base=canvas_img, 
                    part_img_path=part_path, 
                    fuku_base_image_origin_coords=canvas_origin_coords, 
                    coords_dict=coords_dict
                )
                
                if updated_canvas:
                    canvas_img = updated_canvas # 更新畫布為剛合成完的結果
                else:
                    print(f"      - 警告：在預處理 {clothing_name} 時合成 {os.path.basename(part_path)} 失敗，已跳過此圖層。")

            # 4. 儲存最終結果
            if canvas_img:
                canvas_img.save(output_path)
                print(f"      - ✓ 成功使用統一邏輯合成 {clothing_name}.png，並儲存。")
                # 儲存這個合成品的原點座標
                coords_dict[clothing_name] = canvas_origin_coords
            else:
                print(f"      - 錯誤：合成 {clothing_name}.png 失敗。")
                
    print("  - Fuku 預處理完畢。")

## ---
## **單一角色處理邏輯 (保留所有循環和輸出路徑)**
## ---

def process_fuku_task(fuku_file, char_name, all_dirs, all_files, offset_coords):
    """
    單一線程執行的任務：處理一套 fuku 的所有組合。
    """
    # 從傳入的參數中解包路徑和檔案列表
    FUKU_DIR, KAO_DIR, KAMI_DIR, KUCHI_DIR, HOHO_DIR, EFFECT_DIR = all_dirs['fuku'], all_dirs['kao'], all_dirs['kami'], all_dirs['kuchi'], all_dirs['hoho'], all_dirs['effect']
    OUTPUT_ROOT, PREPROCESSED_FUKU_DIR, TEMP_BASE_DIR = all_dirs['output'], all_dirs['preprocessed_fuku'], all_dirs['temp_base']
    
    kao_files, kami_files, kuchi_files, hoho_files, global_effect_files = all_files['kao'], all_files['kami'], all_files['kuchi'], all_files['hoho'], all_files['effect']
    
    # --- 以下是從舊的 for 迴圈中移過來的邏輯 ---
    
    fuku_base_name = get_base_key_from_filename(fuku_file)
    fuku_path = os.path.join(PREPROCESSED_FUKU_DIR, fuku_file)
    fuku_actual_origin_coords = find_coords_for_part(fuku_base_name, offset_coords)
    print(f"    - [線程處理中] 基礎組合: {fuku_base_name} (原點: {fuku_actual_origin_coords})")

    # Step 1: fuku + kao + kami -> temp_base
    for kao_file in kao_files:
        kao_base_key = get_base_key_from_filename(kao_file)
        output_filename_base = f"{char_name}_{fuku_base_name}_{kao_base_key}"
        base_img_for_kami = composite_images(fuku_path, os.path.join(KAO_DIR, kao_file), fuku_actual_origin_coords, offset_coords)
        if not base_img_for_kami: continue
        
        final_base_output_name = f"{output_filename_base}.png"
        output_path_temp = os.path.join(TEMP_BASE_DIR, final_base_output_name)
        if not os.path.exists(output_path_temp):
            final_image_to_save = None
            if kami_files:
                # 您的邏輯：只使用第一個 kami
                default_kami_file = kami_files[0]
                final_image_to_save = composite_images(base_img_for_kami.copy(), os.path.join(KAMI_DIR, default_kami_file), fuku_actual_origin_coords, offset_coords)
            else:
                final_image_to_save = base_img_for_kami
            if final_image_to_save:
                final_image_to_save.save(output_path_temp)
                # print(f"      ✓ {fuku_base_name}: 生成 {final_base_output_name}") # 輸出訊息可以簡化

    # Step 2: temp_base + kuchi + fuku_specific_effect -> kao_kuchi
    KAO_KUCHI_DIR = os.path.join(OUTPUT_ROOT, "kao_kuchi")
    ensure_dir(KAO_KUCHI_DIR)
    fuku_specific_effect_dir = os.path.join(FUKU_DIR, fuku_base_name, "effect")
    fuku_specific_effect_files = get_files_safely(fuku_specific_effect_dir)
    temp_base_files_for_fuku = [f for f in get_files_safely(TEMP_BASE_DIR) if f"_{fuku_base_name}_" in f]

    for base_file in temp_base_files_for_fuku:
        base_name_no_ext = os.path.splitext(base_file)[0]
        base_path = os.path.join(TEMP_BASE_DIR, base_file)
        if kuchi_files:
            for kuchi_file in kuchi_files:
                kuchi_base_key = get_base_key_from_filename(kuchi_file)
                final_name = f"{base_name_no_ext}_{kuchi_base_key}.png"
                output_path_kuchi = os.path.join(KAO_KUCHI_DIR, final_name)
                if not os.path.exists(output_path_kuchi):
                    current_image = composite_images(base_path, os.path.join(KUCHI_DIR, kuchi_file), fuku_actual_origin_coords, offset_coords)
                    if not current_image: continue
                    if fuku_specific_effect_files:
                        for effect_file in fuku_specific_effect_files:
                            current_image = composite_images(current_image.copy(), os.path.join(fuku_specific_effect_dir, effect_file), fuku_actual_origin_coords, offset_coords)
                            if not current_image: break
                    if current_image: current_image.save(output_path_kuchi)
        else:
            final_name = f"{base_name_no_ext}.png"
            output_path_kuchi = os.path.join(KAO_KUCHI_DIR, final_name)
            if not os.path.exists(output_path_kuchi):
                current_image = Image.open(base_path).convert('RGBA')
                if fuku_specific_effect_files:
                    for effect_file in fuku_specific_effect_files:
                        current_image = composite_images(current_image.copy(), os.path.join(fuku_specific_effect_dir, effect_file), fuku_actual_origin_coords, offset_coords)
                        if not current_image: break
                if current_image: current_image.save(output_path_kuchi)
    
    # Step 3 & 4 ... (hoho 和 effect 的處理邏輯)
    # 為了簡潔，這裡省略貼上重複的程式碼，它們的邏輯和上面類似
    # 您需要將原有的 Step 3 和 Step 4 的迴圈邏輯也複製到這個函式裡
    # 注意：在處理 Step 3 和 4 時，您需要從 KAO_KUCHI_DIR 讀取檔案
    # 這裡我為您補全 Step 3 & 4
    
    # --- Step 3: kao_kuchi + hoho -> kao_kuchi_hoho ---
    if hoho_files:
        KAO_KUCHI_HOHO_DIR = os.path.join(OUTPUT_ROOT, "kao_kuchi_hoho")
        ensure_dir(KAO_KUCHI_HOHO_DIR)
        kao_kuchi_files_for_fuku = [f for f in get_files_safely(KAO_KUCHI_DIR) if f"_{fuku_base_name}_" in f]
        for base_file in kao_kuchi_files_for_fuku:
            base_name_no_ext = os.path.splitext(base_file)[0]
            base_path = os.path.join(KAO_KUCHI_DIR, base_file)
            for hoho_file in hoho_files:
                hoho_base_key = get_base_key_from_filename(hoho_file)
                final_name = f"{base_name_no_ext}_{hoho_base_key}.png"
                output_path_hoho = os.path.join(KAO_KUCHI_HOHO_DIR, final_name)
                if not os.path.exists(output_path_hoho):
                    composed = composite_images(base_path, os.path.join(HOHO_DIR, hoho_file), fuku_actual_origin_coords, offset_coords)
                    if composed: composed.save(output_path_hoho)
                        
    # --- Step 4: 合成 Global Effect ---
    MAX_EFFECT_LAYERS = 1
    if global_effect_files:
        input_dirs_for_effect = []
        if hoho_files: input_dirs_for_effect.append(os.path.join(OUTPUT_ROOT, "kao_kuchi_hoho"))
        input_dirs_for_effect.append(os.path.join(OUTPUT_ROOT, "kao_kuchi"))
        
        for input_dir in input_dirs_for_effect:
            if not os.path.isdir(input_dir): continue
            
            output_dir = f"{input_dir}_effect"
            ensure_dir(output_dir)
            
            base_files_for_fuku_effect = [f for f in get_files_safely(input_dir) if f"_{fuku_base_name}_" in f]
            for base_file in base_files_for_fuku_effect:
                base_name_no_ext = os.path.splitext(base_file)[0]
                base_path = os.path.join(input_dir, base_file)
                for size in range(1, MAX_EFFECT_LAYERS + 1):
                    if len(global_effect_files) < size: continue
                    for effect_combo in itertools.combinations(global_effect_files, size):
                        combo_suffix = "_".join(sorted([get_base_key_from_filename(f) for f in effect_combo]))
                        final_name = f"{base_name_no_ext}_{combo_suffix}.png"
                        output_path_effect = os.path.join(output_dir, final_name)
                        if not os.path.exists(output_path_effect):
                            composed = Image.open(base_path).convert('RGBA')
                            for effect_file in effect_combo:
                                composed = composite_images(composed, os.path.join(EFFECT_DIR, effect_file), fuku_actual_origin_coords, offset_coords)
                                if not composed: break
                            if composed: composed.save(output_path_effect)
    
    # print(f"    ✓ [線程完成] {fuku_base_name}")

def process_single_character(char_dir, offset_coords):
    char_name = os.path.basename(char_dir)
    print(f"\n{'='*20} 開始處理角色: {char_name} {'='*20}")
    
    # --- 1. 準備所有路徑和檔案列表 (這部分不變) ---
    FUKU_DIR, KAO_DIR, KAMI_DIR, KUCHI_DIR, HOHO_DIR, EFFECT_DIR = (os.path.join(char_dir, name) for name in ["fuku", "kao", "kami", "kuchi", "hoho", "effect"])
    OUTPUT_ROOT = os.path.join(char_dir, "output")
    PREPROCESSED_FUKU_DIR = os.path.join(OUTPUT_ROOT, "preprocessed_fuku")
    TEMP_BASE_DIR = os.path.join(OUTPUT_ROOT, "temp_base")

    all_dirs = {
        'fuku': FUKU_DIR, 'kao': KAO_DIR, 'kami': KAMI_DIR, 'kuchi': KUCHI_DIR, 'hoho': HOHO_DIR, 'effect': EFFECT_DIR,
        'output': OUTPUT_ROOT, 'preprocessed_fuku': PREPROCESSED_FUKU_DIR, 'temp_base': TEMP_BASE_DIR
    }

    ensure_dir(OUTPUT_ROOT)
    ensure_dir(PREPROCESSED_FUKU_DIR)
    ensure_dir(TEMP_BASE_DIR)

    kao_files = get_files_safely(KAO_DIR)
    kami_files = get_files_safely(KAMI_DIR)
    kuchi_files = get_files_safely(KUCHI_DIR)
    hoho_files = get_files_safely(HOHO_DIR)
    global_effect_files = get_files_safely(EFFECT_DIR)

    all_files = {'kao': kao_files, 'kami': kami_files, 'kuchi': kuchi_files, 'hoho': hoho_files, 'effect': global_effect_files}

    # --- 2. 預處理 Fuku (這一步仍然需要同步執行) ---
    preprocess_fuku_folders(FUKU_DIR, PREPROCESSED_FUKU_DIR, offset_coords)
    fuku_files = get_files_safely(PREPROCESSED_FUKU_DIR)
    
    if not fuku_files or not kao_files:
        print(f"  - 錯誤：角色 {char_name} 的 fuku 或 kao 列表為空，無法繼續組合，已跳過。")
        return

    # --- 3. 【核心修改】使用線程池並行處理所有 fuku 任務 ---
    # 使用 os.cpu_count() 來決定最大線程數，通常是最佳選擇
    # 如果 os.cpu_count() 返回 None，則預設為 4
    max_worker_threads = os.cpu_count() or 4
    print(f"\n  - 初始化線程池，最大線程數: {max_worker_threads}")
    print(f"  - 開始對 {len(fuku_files)} 套 fuku 進行並行處理...")

    with ThreadPoolExecutor(max_workers=max_worker_threads) as executor:
        # 提交所有任務
        futures = [executor.submit(process_fuku_task, fuku_file, char_name, all_dirs, all_files, offset_coords) for fuku_file in fuku_files]
        
        # 等待所有線程執行完畢
        for future in futures:
            try:
                # .result() 會等待線程結束，如果線程中發生錯誤，這裡會拋出異常
                future.result()
            except Exception as e:
                print(f"  -! 一個線程在執行時發生嚴重錯誤: {e}")

    print(f"\n--- ✓ 角色 {char_name} 所有 fuku 組合均已處理完畢 ---")

## ---
## **主程式入口**
## ---

def get_base_key_from_filename(filename):
    """
    從完整檔名中獲取移除了影格後綴的核心基礎名稱。
    例如: "伊桜里顔A大-001.png" -> "伊桜里顔A大"
          "effect_A.png" -> "effect_A"
    """
    # 先移除 .png 副檔名
    base_name_no_ext = os.path.splitext(filename)[0]
    # 使用我們之前用過的正則表達式，來分離基礎名稱和影格後綴
    match = re.match(r'^(.*)([-_]\d+)$', base_name_no_ext)
    if match:
        # 如果匹配成功，返回不包含後綴的第一部分
        return match.group(1) 
    else:
        # 如果沒有影格後綴，直接返回原始的、無副檔名的名稱
        return base_name_no_ext

def main():
    script_dir = os.getcwd()
    print(f"程式啟動於: {script_dir}")
    offset_file_path = os.path.join(script_dir, "Kaguya_XY_Offset.csv")
    
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
