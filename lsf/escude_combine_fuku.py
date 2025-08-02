import os
import shutil
from PIL import Image
import re
import csv
import itertools
import numpy as np

# --- 核心輔助函式 (無變動) ---

def ensure_dir(dir_path):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

def load_offset_coords(filepath):
    info_dict = {}
    if not os.path.exists(filepath):
        print(f"錯誤：在指定路徑找不到座標檔案！\n路徑: {filepath}")
        return None
    
    print(f"--- 開始讀取 lsf_export_all.csv 格式座標檔: {filepath} ---")
    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            processed_keys = set()
            for i, row in enumerate(reader):
                if len(row) < 8: continue
                png_filename = row[2].strip()
                if not png_filename or png_filename in processed_keys: continue
                try:
                    info_dict[png_filename] = {
                        'coords': (int(row[3]), int(row[4])),
                        'blend_mode': int(row[7])
                    }
                    processed_keys.add(png_filename)
                except (ValueError, IndexError):
                    print(f"警告：座標檔案中第 {i+2} 行資料格式錯誤，已跳過：{row}")
    except Exception as e:
        print(f"讀取座標檔案 {filepath} 時發生錯誤：{e}")
        return None
    print(f"--- 成功讀取 {len(info_dict)} 筆不重複的部件資訊 ---")
    return info_dict

def find_part_info(part_base_name, all_info_dict):
    default_info = {'coords': (0, 0), 'blend_mode': 0}
    if part_base_name in all_info_dict:
        return all_info_dict[part_base_name]
    return default_info

def get_files_safely(dir_name):
    if not os.path.isdir(dir_name): return []
    return sorted([f for f in os.listdir(dir_name) if f.endswith('.png')])

def get_last_number(filename):
    base = os.path.splitext(os.path.basename(filename))[0]
    match = re.search(r'_(\d+)$', base)
    return match.group(1) if match else base

def compose_final_image(parts_in_order, scene_ref_coords, output_path, all_info_dict):
    if not parts_in_order: return
    part_data = []
    for part_path in parts_in_order:
        part_base = os.path.splitext(os.path.basename(part_path))[0]
        info = find_part_info(part_base, all_info_dict)
        try:
            img = Image.open(part_path).convert('RGBA')
            info['img'] = img
            part_data.append(info)
        except FileNotFoundError:
            print(f"警告：找不到部件檔案 {part_path}，已跳過。")
            return
    if not part_data: return
    for part in part_data:
        part['rel_pos'] = (part['coords'][0] - scene_ref_coords[0], part['coords'][1] - scene_ref_coords[1])
    min_x, min_y, max_x, max_y = float('inf'), float('inf'), float('-inf'), float('-inf')
    for part in part_data:
        x, y = part['rel_pos']; w, h = part['img'].size
        min_x, min_y = min(min_x, x), min(min_y, y)
        max_x, max_y = max(max_x, x + w), max(max_y, y + h)
    canvas_width, canvas_height = max_x - min_x, max_y - min_y
    if canvas_width <= 0 or canvas_height <= 0: return
    final_canvas = Image.new('RGBA', (canvas_width, canvas_height), (0, 0, 0, 0))
    for part in part_data:
        fg_layer_img = Image.new('RGBA', final_canvas.size, (0, 0, 0, 0))
        paste_x, paste_y = part['rel_pos'][0] - min_x, part['rel_pos'][1] - min_y
        fg_layer_img.paste(part['img'], (paste_x, paste_y))
        base_np, fg_np = np.array(final_canvas, dtype=np.float64)/255.0, np.array(fg_layer_img, dtype=np.float64)/255.0
        bg_rgb, bg_a, fg_rgb, fg_a = base_np[:,:,:3], base_np[:,:,3:4], fg_np[:,:,:3], fg_np[:,:,3:4]
        mode = part['blend_mode']
        if mode == 3: out_rgb_blend = fg_rgb * bg_rgb
        elif mode == 10: out_rgb_blend = fg_rgb + bg_rgb
        else: out_rgb_blend = fg_rgb
        out_a = fg_a + bg_a * (1.0 - fg_a)
        mask = out_a > 1e-6
        numerator = out_rgb_blend * fg_a + bg_rgb * bg_a * (1.0 - fg_a)
        out_rgb = np.zeros_like(bg_rgb)
        np.divide(numerator, out_a, where=mask, out=out_rgb)
        final_np_float = np.concatenate([out_rgb, out_a], axis=2)
        final_np_float = np.clip(final_np_float, 0.0, 1.0) 
        final_np_uint8 = (final_np_float * 255).round().astype(np.uint8)
        final_canvas = Image.fromarray(final_np_uint8, 'RGBA')
    ensure_dir(os.path.dirname(output_path))
    final_canvas.save(output_path)

def layering_sort_key_advanced(filename):
    base_name = os.path.splitext(filename)[0].upper().replace('Ａ', 'A').replace('Ｂ', 'B').replace('Ｃ', 'C').replace('Ｄ', 'D').replace('Ｅ', 'E')
    if base_name.isdigit(): return (0, int(base_name), filename)
    letter_priorities = {'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5};
    for letter, priority in letter_priorities.items():
        if letter in base_name: return (priority, filename)
    return (99, filename)

def get_group_from_location(location_str):
    if location_str == 'root': return 1
    num = int(location_str)
    return 0 if num == 0 else num + 1

def process_single_character(char_dir, all_info_dict):
    char_name = os.path.basename(char_dir)
    print(f"\n{'='*20} 開始處理角色: {char_name} {'='*20}")

    FUKU_DIR, KAO_DIR, KAMI_DIR, KUCHI_DIR, HOHO_DIR, EFFECT_DIR = (os.path.join(char_dir, d) for d in ["fuku", "kao", "kami", "kuchi", "hoho", "effect"])
    OUTPUT_ROOT = os.path.join(char_dir, "output")
    ensure_dir(OUTPUT_ROOT)

    kao_files, kami_files, kuchi_files, hoho_files, effect_files = (get_files_safely(d) for d in [KAO_DIR, KAMI_DIR, KUCHI_DIR, HOHO_DIR, EFFECT_DIR])
    if not os.path.exists(FUKU_DIR) or not kao_files:
        print(f"  - 錯誤：角色 {char_name} 的 fuku 或 kao 資料夾不存在或為空，已跳過。")
        return

    for fuku_item_name in sorted(os.listdir(FUKU_DIR)):
        fuku_item_path = os.path.join(FUKU_DIR, fuku_item_name)
        fuku_parts_paths, scene_ref_coords, fuku_name_part = [], (0, 0), ""

        if os.path.isfile(fuku_item_path) and fuku_item_name.lower().endswith('.png'):
            fuku_parts_paths = [fuku_item_path]
            fuku_info = find_part_info(os.path.splitext(fuku_item_name)[0], all_info_dict)
            scene_ref_coords, fuku_name_part = fuku_info['coords'], get_last_number(fuku_item_name)
        elif os.path.isdir(fuku_item_path):
            print(f"  - 處理多部件 fuku: {fuku_item_name}")
            fuku_name_part = fuku_item_name
            all_parts_info = []
            for f in get_files_safely(fuku_item_path): all_parts_info.append({'path': os.path.join(fuku_item_path, f), 'location': 'root'})
            for sub in os.listdir(fuku_item_path):
                sub_path = os.path.join(fuku_item_path, sub)
                if os.path.isdir(sub_path) and sub.isdigit():
                    for f in get_files_safely(sub_path): all_parts_info.append({'path': os.path.join(sub_path, f), 'location': sub})
            all_parts_info.sort(key=lambda p: (get_group_from_location(p['location']), layering_sort_key_advanced(os.path.basename(p['path']))))
            fuku_parts_paths = [p['path'] for p in all_parts_info]
            if not fuku_parts_paths: continue
            min_x, min_y = float('inf'), float('inf')
            for part_path in fuku_parts_paths:
                part_info = find_part_info(os.path.splitext(os.path.basename(part_path))[0], all_info_dict)
                min_x, min_y = min(min_x, part_info['coords'][0]), min(min_y, part_info['coords'][1])
            scene_ref_coords = (min_x, min_y) if min_x != float('inf') else (0, 0)
        else: continue

        fuku_specific_effects = []
        if os.path.isdir(fuku_item_path):
            specific_effect_dir = os.path.join(fuku_item_path, "effect")
            if os.path.isdir(specific_effect_dir): fuku_specific_effects = [os.path.join(specific_effect_dir, f) for f in get_files_safely(specific_effect_dir)]

        for kao_file in kao_files:
            base_parts = list(fuku_parts_paths)
            base_parts.append(os.path.join(KAO_DIR, kao_file))
            if kami_files: base_parts.append(os.path.join(KAMI_DIR, kami_files[0]))
            
            kuchi_options = [None] + kuchi_files
            for kuchi_file in kuchi_options:
                parts_after_kuchi, kuchi_name_part = list(base_parts), ""
                if kuchi_file:
                    parts_after_kuchi.append(os.path.join(KUCHI_DIR, kuchi_file))
                    kuchi_name_part = f"_{get_last_number(kuchi_file)}"
                parts_after_kuchi.extend(fuku_specific_effects)

                hoho_options = [None] + hoho_files
                for hoho_file in hoho_options:
                    parts_after_hoho, hoho_name_part = list(parts_after_kuchi), ""
                    if hoho_file:
                        parts_after_hoho.append(os.path.join(HOHO_DIR, hoho_file))
                        hoho_name_part = f"_{get_last_number(hoho_file)}"
                    
                    MAX_EFFECT_LAYERS = 1
                    effect_options = [()]
                    for size in range(1, MAX_EFFECT_LAYERS + 1):
                        if len(effect_files) >= size: effect_options.extend(itertools.combinations(effect_files, size))
                    for effect_combo in effect_options:
                        final_parts_in_order, effect_name_part = list(parts_after_hoho), ""
                        if effect_combo:
                            final_parts_in_order.extend([os.path.join(EFFECT_DIR, f) for f in effect_combo])
                            effect_name_part = f"_{'_'.join(sorted([get_last_number(f) for f in effect_combo]))}"
                        
                        # --- 【核心修改】動態決定輸出資料夾 ---
                        folder_parts = ["kao"]
                        if kuchi_file: folder_parts.append("kuchi")
                        if hoho_file: folder_parts.append("hoho")
                        subfolder_name = "_".join(folder_parts)
                        if effect_combo: subfolder_name += "_effect"
                        
                        # 基礎 fuku+kao 組合放在 output/kao/
                        # 其他組合放在對應的子資料夾
                        current_output_dir = os.path.join(OUTPUT_ROOT, subfolder_name)
                        
                        # 組合最終檔名和路徑
                        kao_name_part = get_last_number(kao_file)
                        output_filename = f"{char_name}_{fuku_name_part}_{kao_name_part}{kuchi_name_part}{hoho_name_part}{effect_name_part}.png"
                        output_path = os.path.join(current_output_dir, output_filename)

                        if os.path.exists(output_path): continue
                        compose_final_image(final_parts_in_order, scene_ref_coords, output_path, all_info_dict)

def main():
    script_dir = os.getcwd()
    print(f"程式啟動於: {script_dir}")
    offset_file_path = os.path.join(script_dir, "lsf_export_all.csv") 
    all_info_dict = load_offset_coords(offset_file_path)
    if all_info_dict is None:
        input("錯誤：找不到或無法讀取座標檔，請按 Enter 鍵結束。")
        return
    character_folders = []
    print("開始掃描所有子資料夾...")
    for item in os.listdir(script_dir):
        item_path = os.path.join(script_dir, item)
        if os.path.isdir(item_path) and os.path.isdir(os.path.join(item_path, "fuku")) and os.path.isdir(os.path.join(item_path, "kao")):
            character_folders.append(item_path)
    if not character_folders:
        print("\n在目前資料夾下，沒有找到任何包含 'fuku' 和 'kao' 的角色資料夾。")
        input("請檢查資料夾結構，然後按 Enter 鍵結束。")
        return
    print(f"\n掃描完成！發現 {len(character_folders)} 個待處理的角色資料夾:")
    for folder in character_folders:
        print(f"  - {os.path.basename(folder)}")
    for char_folder in character_folders:
        process_single_character(char_folder, all_info_dict)
    print(f"\n{'='*50}\n🎉 所有角色均已處理完畢！ 🎉\n{'='*50}")
    input("請按 Enter 鍵結束程式。")

if __name__ == '__main__':
    main()