import os
import shutil
from PIL import Image
import itertools
import re
import numpy as np

# --- 核心合成與輔助函式 (維持不變) ---
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

def composite_images(base, part_img_path, fuku_coords, coords_dict):
    try:
        if isinstance(base, str):
            base_img = Image.open(base).convert('RGBA')
        elif isinstance(base, Image.Image):
            base_img = base if base.mode == 'RGBA' else base.convert('RGBA')
        else: return None
    except Exception: return None
    try:
        part_img = Image.open(part_img_path).convert("RGBA")
        part_base_name = os.path.splitext(os.path.basename(part_img_path))[0]
        part_x, part_y = find_coords_for_part(part_base_name, coords_dict)
        dx = part_x - fuku_coords[0]
        dy = part_y - fuku_coords[1]
    except Exception: return None
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

# ★★★★★【排序邏輯最終版】★★★★★
def preprocess_fuku_folders(fuku_base_dir, output_dir, coords_dict):
    """預處理 fuku 資料夾，組合身體圖（支援 0->根目錄->1->2 的排序）。"""
    print("  - 開始預處理 Fuku...")
    ensure_dir(output_dir)
    
    def layering_sort_key_advanced(filename):
        base_name = os.path.splitext(filename)[0].upper()
        if base_name.isdigit(): return (0, int(base_name), filename)
        letter_priorities = {'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5} 
        for letter, priority in letter_priorities.items():
            if letter in base_name: return (priority, filename)
        return (99, filename)
    
    # 新的輔助函式，根據位置決定圖層組編號
    def get_group_from_location(location_str):
        if location_str == 'root':
            return 1 # 根目錄是第 1 組
        num = int(location_str)
        if num == 0:
            return 0 # '0' 資料夾是第 0 組
        else:
            return num + 1 # '1' 資料夾是第 2 組, '2' 是第 3 組...

    clothing_subdirs = [d for d in os.listdir(fuku_base_dir) if os.path.isdir(os.path.join(fuku_base_dir, d))]
    
    if not clothing_subdirs:
        # ... (邏輯不變) ...
        return

    for clothing_name in clothing_subdirs:
        output_path = os.path.join(output_dir, f"{clothing_name}.png")
        if os.path.exists(output_path):
            print(f"    - 服裝 {clothing_name} 已存在，跳過。")
            continue
        
        print(f"    - 處理服裝: {clothing_name}")
        clothing_dir_path = os.path.join(fuku_base_dir, clothing_name)
        
        all_parts = []
        # 1. 掃描根目錄 (location: 'root')
        for f in get_files_safely(clothing_dir_path):
            all_parts.append({'path': os.path.join(clothing_dir_path, f), 'location': 'root'})
        
        # 2. 掃描數字子資料夾 (location: '0', '1', '2'...)
        for item in os.listdir(clothing_dir_path):
            item_path = os.path.join(clothing_dir_path, item)
            if os.path.isdir(item_path) and item.isdigit():
                for f in get_files_safely(item_path):
                    all_parts.append({'path': os.path.join(item_path, f), 'location': item})
        
        # --- 組合排序 ---
        all_parts.sort(key=lambda p: (get_group_from_location(p['location']), layering_sort_key_advanced(os.path.basename(p['path']))))
        
        # 為了日誌更清晰，顯示組別和檔名
        sorted_filenames = [f"(組{get_group_from_location(p['location'])}) {os.path.relpath(p['path'], clothing_dir_path)}" for p in all_parts]
        print(f"      - 排序後圖層順序: {sorted_filenames}")
        
        parts_to_composite = []
        max_x, max_y = 0, 0
        for part_info in all_parts:
            part_path = part_info['path']
            part_base_name = os.path.splitext(os.path.basename(part_path))[0]
            coords = find_coords_for_part(part_base_name, coords_dict)
            
            if coords != (0, 0):
                x, y = coords
                try:
                    with Image.open(part_path) as img:
                        width, height = img.size
                        max_x = max(max_x, x + width)
                        max_y = max(max_y, y + height)
                        parts_to_composite.append({'path': part_path, 'pos': (x, y)})
                except Exception: continue
        
        if not parts_to_composite: 
            print(f"      - 警告：在 {clothing_name} 中找不到任何有座標的部件，無法生成。")
            continue
            
        canvas_img = Image.new('RGBA', (max_x, max_y), (0, 0, 0, 0))
        fuku_assembly_base_coords = (0, 0)
        temp_coords_dict = {os.path.splitext(os.path.basename(p['path']))[0]: p['pos'] for p in parts_to_composite}
        
        # 將排序好的 parts_to_composite 列表傳遞給合成步驟
        # 注意：parts_to_composite 的順序繼承自 all_parts 的排序結果
        sorted_parts_for_compositing = []
        for part_info in all_parts:
            for comp_part in parts_to_composite:
                if part_info['path'] == comp_part['path']:
                    sorted_parts_for_compositing.append(comp_part)
                    break

        for part_info in sorted_parts_for_compositing:
            canvas_img = composite_images(canvas_img, part_info['path'], fuku_assembly_base_coords, temp_coords_dict)
        
        if canvas_img:
            print(f"      - ✓ 成功合成 {clothing_name}.png，並儲存。")
            canvas_img.save(output_path)
            
    print("  - Fuku 預處理完畢。")

def process_single_character(char_dir, offset_coords):
    # ... (此函式及 main 函式維持不變) ...
    char_name = os.path.basename(char_dir)
    print(f"\n{'='*20} 開始處理角色: {char_name} {'='*20}")
    FUKU_DIR, KAO_DIR, KAMI_DIR, KUCHI_DIR, HOHO_DIR, EFFECT_DIR = (os.path.join(char_dir, name) for name in ["fuku", "kao", "kami", "kuchi", "hoho", "effect"])
    kao_files, kami_files, kuchi_files, hoho_files, global_effect_files = (get_files_safely(d) for d in [KAO_DIR, KAMI_DIR, KUCHI_DIR, HOHO_DIR, EFFECT_DIR])
    MAX_EFFECT_LAYERS = 1
    OUTPUT_ROOT = os.path.join(char_dir, "output")
    PREPROCESSED_FUKU_DIR = os.path.join(OUTPUT_ROOT, "preprocessed_fuku")
    TEMP_BASE_DIR = os.path.join(OUTPUT_ROOT, "temp_base")
    ensure_dir(OUTPUT_ROOT)
    ensure_dir(PREPROCESSED_FUKU_DIR)
    preprocess_fuku_folders(FUKU_DIR, PREPROCESSED_FUKU_DIR, offset_coords)
    fuku_files = get_files_safely(PREPROCESSED_FUKU_DIR)
    if not fuku_files or not kao_files:
        print(f"錯誤：角色 {char_name} 的 fuku 或 kao 為空，跳過此角色。")
        return
    for fuku_file in fuku_files:
        fuku_base_name = os.path.splitext(fuku_file)[0]
        fuku_path = os.path.join(PREPROCESSED_FUKU_DIR, fuku_file)
        fuku_coords = (0, 0)
        print(f"\n  - 處理基礎組合: {fuku_base_name}")
        if os.path.exists(TEMP_BASE_DIR): shutil.rmtree(TEMP_BASE_DIR)
        ensure_dir(TEMP_BASE_DIR)
        print("    Step 1 (In-Memory): fuku + kao + kami -> temp_base")
        for kao_file in kao_files:
            base_img = composite_images(fuku_path, os.path.join(KAO_DIR, kao_file), fuku_coords, offset_coords)
            if not base_img: continue
            if kami_files:
                for kami_file in kami_files:
                    output_path = os.path.join(TEMP_BASE_DIR, f"{fuku_base_name}_{os.path.splitext(kao_file)[0]}_{os.path.splitext(kami_file)[0]}.png")
                    if not os.path.exists(output_path):
                        composed = composite_images(base_img.copy(), os.path.join(KAMI_DIR, kami_file), fuku_coords, offset_coords)
                        if composed: composed.save(output_path)
            else:
                output_path = os.path.join(TEMP_BASE_DIR, f"{fuku_base_name}_{os.path.splitext(kao_file)[0]}.png")
                if not os.path.exists(output_path): base_img.save(output_path)
        print("    Step 2 (File -> Memory -> File): temp_base + kuchi + fuku_effect -> kao_kuchi")
        KAO_KUCHI_DIR = os.path.join(OUTPUT_ROOT, "kao_kuchi")
        ensure_dir(KAO_KUCHI_DIR)
        fuku_specific_effect_dir = os.path.join(FUKU_DIR, fuku_base_name, "effect")
        fuku_specific_effect_files = get_files_safely(fuku_specific_effect_dir)
        for base_file in get_files_safely(TEMP_BASE_DIR):
            base_name_no_ext = os.path.splitext(base_file)[0]
            if kuchi_files:
                for kuchi_file in kuchi_files:
                    final_name = f"{base_name_no_ext}_{os.path.splitext(kuchi_file)[0]}.png"
                    output_path = os.path.join(KAO_KUCHI_DIR, final_name)
                    if not os.path.exists(output_path):
                        base_path = os.path.join(TEMP_BASE_DIR, base_file)
                        current_image = composite_images(base_path, os.path.join(KUCHI_DIR, kuchi_file), fuku_coords, offset_coords)
                        if fuku_specific_effect_files:
                            for effect_file in fuku_specific_effect_files:
                                current_image = composite_images(current_image, os.path.join(fuku_specific_effect_dir, effect_file), fuku_coords, offset_coords)
                        if current_image: current_image.save(output_path)
            else:
                output_path = os.path.join(KAO_KUCHI_DIR, base_file)
                if not os.path.exists(output_path):
                    base_path = os.path.join(TEMP_BASE_DIR, base_file)
                    current_image = Image.open(base_path)
                    if fuku_specific_effect_files:
                        for effect_file in fuku_specific_effect_files:
                            current_image = composite_images(current_image, os.path.join(fuku_specific_effect_dir, effect_file), fuku_coords, offset_coords)
                    if current_image: current_image.save(output_path)
        print("    Step 3+: Branching for optional parts...")
        if hoho_files:
            KAO_KUCHI_HOHO_DIR = os.path.join(OUTPUT_ROOT, "kao_kuchi_hoho")
            ensure_dir(KAO_KUCHI_HOHO_DIR)
            for base_file in get_files_safely(KAO_KUCHI_DIR):
                 if fuku_base_name not in base_file: continue
                 base_path = os.path.join(KAO_KUCHI_DIR, base_file)
                 for hoho_file in hoho_files:
                    output_path = os.path.join(KAO_KUCHI_HOHO_DIR, f"{os.path.splitext(base_file)[0]}_{os.path.splitext(hoho_file)[0]}.png")
                    if not os.path.exists(output_path):
                        composed = composite_images(base_path, os.path.join(HOHO_DIR, hoho_file), fuku_coords, offset_coords)
                        if composed: composed.save(output_path)
        if global_effect_files:
            KAO_KUCHI_EFFECT_DIR = os.path.join(OUTPUT_ROOT, "kao_kuchi_effect")
            ensure_dir(KAO_KUCHI_EFFECT_DIR)
            for base_file in get_files_safely(KAO_KUCHI_DIR):
                if fuku_base_name not in base_file: continue
                base_path = os.path.join(KAO_KUCHI_DIR, base_file)
                for size in range(1, MAX_EFFECT_LAYERS + 1):
                    if len(global_effect_files) < size: continue
                    for effect_combo in itertools.combinations(global_effect_files, size):
                        combo_suffix = "_".join(sorted([os.path.splitext(f)[0] for f in effect_combo]))
                        output_path = os.path.join(KAO_KUCHI_EFFECT_DIR, f"{os.path.splitext(base_file)[0]}_{combo_suffix}.png")
                        if not os.path.exists(output_path):
                            composed = Image.open(base_path)
                            for effect_file in effect_combo:
                                composed = composite_images(composed, os.path.join(EFFECT_DIR, effect_file), fuku_coords, offset_coords)
                            if composed: composed.save(output_path)
        if hoho_files and global_effect_files:
            KAO_KUCHI_HOHO_DIR = os.path.join(OUTPUT_ROOT, "kao_kuchi_hoho")
            KAO_KUCHI_HOHO_EFFECT_DIR = os.path.join(OUTPUT_ROOT, "kao_kuchi_hoho_effect")
            if not os.path.isdir(KAO_KUCHI_HOHO_DIR): continue
            ensure_dir(KAO_KUCHI_HOHO_EFFECT_DIR)
            for base_file in get_files_safely(KAO_KUCHI_HOHO_DIR):
                if fuku_base_name not in base_file: continue
                base_path = os.path.join(KAO_KUCHI_HOHO_DIR, base_file)
                for size in range(1, MAX_EFFECT_LAYERS + 1):
                    if len(global_effect_files) < size: continue
                    for effect_combo in itertools.combinations(global_effect_files, size):
                        combo_suffix = "_".join(sorted([os.path.splitext(f)[0] for f in effect_combo]))
                        output_path = os.path.join(KAO_KUCHI_HOHO_EFFECT_DIR, f"{os.path.splitext(base_file)[0]}_{combo_suffix}.png")
                        if not os.path.exists(output_path):
                            composed = Image.open(base_path)
                            for effect_file in effect_combo:
                                composed = composite_images(composed, os.path.join(EFFECT_DIR, effect_file), fuku_coords, offset_coords)
                            if composed: composed.save(output_path)
    print(f"--- ✓ 角色 {char_name} 處理完畢 ---")

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
