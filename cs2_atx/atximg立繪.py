import os
import json
from PIL import Image
import numpy as np

# --- 基礎設定 ---
FUKU_DIR_NAME = "fuku"
KAO_DIR_NAME = "kao"
KAMI_DIR_NAME = "kami"
KUCHI_DIR_NAME = "kuchi"
HOHO_DIR_NAME = "hoho"
EFFECT_DIR_NAME = "effect"
OFFSET_FILE_NAME = "offset.json"
# ATLAS_FILE_NAME 已被移除

# --- 核心函式 (維持不變) ---
def ensure_dir(dir_path):
    if not os.path.exists(dir_path): os.makedirs(dir_path)

def load_json_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f: return json.load(f)
    except Exception as e:
        print(f"錯誤：讀取 {file_path} 失敗: {e}"); return None

def get_image_position(file_path, offset_data):
    key = os.path.splitext(os.path.basename(file_path))[0]
    position = offset_data.get(key)
    if position: return tuple(position)
    else: print(f"警告：在 offset.json 中找不到鍵 '{key}' 的座標。"); return (0, 0)

def get_png_files_from_dir(dir_path):
    if not os.path.isdir(dir_path): return []
    return sorted([os.path.join(dir_path, f) for f in os.listdir(dir_path) if f.endswith('.png')])

def get_all_png_files(dir_path):
    if not os.path.isdir(dir_path): return []
    all_files = []
    for item in os.listdir(dir_path):
        item_path = os.path.join(dir_path, item)
        if os.path.isdir(item_path):
            all_files.extend(get_all_png_files(item_path))
        elif item.endswith('.png'):
            all_files.append(item_path)
    return sorted(all_files)

def composite_numpy(base_np, part_img, part_pos):
    try:
        part_np = np.array(part_img, dtype=np.uint8)
        part_h, part_w, _ = part_np.shape; base_h, base_w, _ = base_np.shape
        x, y = part_pos
        x1, y1 = max(x, 0), max(y, 0); x2, y2 = min(x + part_w, base_w), min(y + part_h, base_h)
        part_x1, part_y1 = x1 - x, y1 - y; part_x2, part_y2 = x2 - x, y2 - y
        if x1 >= x2 or y1 >= y2: return base_np
        base_region = base_np[y1:y2, x1:x2]; part_region = part_np[part_y1:part_y2, part_x1:part_x2]
        part_alpha = part_region[:, :, 3] / 255.0; alpha_3d = np.dstack([part_alpha, part_alpha, part_alpha])
        blended_rgb = (part_region[:, :, :3] * alpha_3d + base_region[:, :, :3] * (1 - alpha_3d)).astype(np.uint8)
        new_alpha = (part_region[:, :, 3] + base_region[:, :, 3] * (1 - part_alpha)).astype(np.uint8)
        base_np[y1:y2, x1:x2, :3] = blended_rgb; base_np[y1:y2, x1:x2, 3] = new_alpha
        return base_np
    except Exception as e:
        print(f"      └ 錯誤: NumPy 合成失敗: {e}"); return base_np

def get_short_name(file_path):
    name = os.path.splitext(os.path.basename(file_path))[0]
    if '_' in name:
        return name.rsplit('_', 1)[-1]
    return name

def process_character_directory(char_dir):
    print(f"\n{'='*25} 開始處理角色資料夾: {char_dir} {'='*25}")
    
    char_name = os.path.basename(char_dir)
    offset_json_data = load_json_file(os.path.join(char_dir, OFFSET_FILE_NAME))
    if offset_json_data is None: return
    offset_data = {item['Key']: tuple(item['Value']) for item in offset_json_data}

    part_paths = { name: os.path.join(char_dir, name) for name in [FUKU_DIR_NAME, HOHO_DIR_NAME, KAO_DIR_NAME, KAMI_DIR_NAME, KUCHI_DIR_NAME, EFFECT_DIR_NAME] }
    
    fuku_files = get_all_png_files(part_paths[FUKU_DIR_NAME]); kao_files = get_png_files_from_dir(part_paths[KAO_DIR_NAME])
    kami_files = get_png_files_from_dir(part_paths[KAMI_DIR_NAME]); kuchi_files = get_png_files_from_dir(part_paths[KUCHI_DIR_NAME])
    hoho_files = get_png_files_from_dir(part_paths[HOHO_DIR_NAME]); effect_files = get_png_files_from_dir(part_paths[EFFECT_DIR_NAME])
    
    if not fuku_files or not kao_files: print("錯誤: 'fuku' 或 'kao' 資料夾為空。"); return
    
    print("--- 第 -1 步: 計算全域主畫布尺寸 ---")
    all_files_to_scan = fuku_files + kao_files + kami_files + kuchi_files + hoho_files + effect_files
    min_x, min_y, max_x, max_y = float('inf'), float('inf'), float('-inf'), float('-inf')
    for path in all_files_to_scan:
        pos = get_image_position(path, offset_data)
        try:
            with Image.open(path) as img: size = img.size
            min_x=min(min_x,pos[0]); min_y=min(min_y,pos[1]); max_x=max(max_x,pos[0]+size[0]); max_y=max(max_y,pos[1]+size[1])
        except Exception: print(f"警告: 無法讀取檔案尺寸: {path}")
    global_canvas_size = (max_x - min_x, max_y - min_y); global_offset = (-min_x, -min_y)
    print(f" > 全域主畫布尺寸: {global_canvas_size} | 全域偏移: {global_offset}")
    
    output_root = os.path.join(char_dir, "output"); ensure_dir(output_root)

    fuku_groups = []
    fuku_dir = part_paths.get(FUKU_DIR_NAME)
    if os.path.isdir(fuku_dir):
        subdirs = [d for d in os.listdir(fuku_dir) if os.path.isdir(os.path.join(fuku_dir, d))]
        if subdirs:
            for subdir_name in sorted(subdirs):
                files = get_png_files_from_dir(os.path.join(fuku_dir, subdir_name))
                if files: fuku_groups.append((subdir_name, files))
        else:
            for f_path in get_png_files_from_dir(fuku_dir):
                group_name = os.path.splitext(os.path.basename(f_path))[0]
                fuku_groups.append((group_name, [f_path]))
    
    print(f"\n--- 檢測到 {len(fuku_groups)} 種 Fuku 基礎群組 ---")

    for fuku_base_name, fuku_group_files in fuku_groups:
        print(f"\n--- 開始處理 Fuku 群組: {fuku_base_name} ---")
        
        fuku_group_files.sort(key=lambda f: os.path.getsize(f), reverse=True)
        canvas = Image.new("RGBA", global_canvas_size, (0,0,0,0)); base_np = np.array(canvas)
        for path in fuku_group_files:
             with Image.open(path) as p_img:
                pos = get_image_position(path, offset_data); new_pos = (pos[0] + global_offset[0], pos[1] + global_offset[1])
                base_np = composite_numpy(base_np, p_img.convert("RGBA"), new_pos)
        fuku_base_img = Image.fromarray(base_np)

        body_bases = {}
        if kami_files:
            for kami_path in kami_files:
                pos = get_image_position(kami_path, offset_data); new_pos = (pos[0] + global_offset[0], pos[1] + global_offset[1])
                with Image.open(kami_path) as p_img: body_np = composite_numpy(np.array(fuku_base_img), p_img.convert("RGBA"), new_pos)
                body_name = f"{char_name}_{fuku_base_name}_{get_short_name(kami_path)}"; body_bases[body_name] = Image.fromarray(body_np)
        else:
            body_name = f"{char_name}_{fuku_base_name}"
            body_bases[body_name] = fuku_base_img
        
        print(f"\n--- [{fuku_base_name}] 流程 A: 建立標準臉 (fuku_face) ---")
        fuku_face_dir = os.path.join(output_root, "fuku_face"); ensure_dir(fuku_face_dir)
        face_images = {}
        for body_name, body_img in body_bases.items():
            for kao_path in kao_files:
                base_np = np.array(body_img)
                pos = get_image_position(kao_path, offset_data); new_pos = (pos[0]+global_offset[0], pos[1]+global_offset[1])
                with Image.open(kao_path) as p_img: base_np = composite_numpy(base_np, p_img.convert("RGBA"), new_pos)
                name_parts = [body_name, get_short_name(kao_path)]
                if kuchi_files:
                    for kuchi_path in kuchi_files:
                        final_name_parts = name_parts + [get_short_name(kuchi_path)]
                        pos = get_image_position(kuchi_path, offset_data); new_pos = (pos[0]+global_offset[0], pos[1]+global_offset[1])
                        with Image.open(kuchi_path) as p_img: final_np = composite_numpy(base_np.copy(), p_img.convert("RGBA"), new_pos)
                        final_img = Image.fromarray(final_np); final_name = "_".join(final_name_parts) + ".png"
                        output_path = os.path.join(fuku_face_dir, final_name)
                        if not os.path.exists(output_path): final_img.save(output_path)
                        face_images[final_name] = final_img
                else:
                    final_img = Image.fromarray(base_np); final_name = "_".join(name_parts) + ".png"
                    output_path = os.path.join(fuku_face_dir, final_name)
                    if not os.path.exists(output_path): final_img.save(output_path)
                    face_images[final_name] = final_img
        print(f" > 已處理 {len(face_images)} 張標準臉。")
        
        if effect_files:
            fuku_face_effect_dir = os.path.join(output_root, "fuku_face_effect"); ensure_dir(fuku_face_effect_dir)
            for face_name, face_img in face_images.items():
                for effect_path in effect_files:
                    pos = get_image_position(effect_path, offset_data); new_pos = (pos[0]+global_offset[0], pos[1]+global_offset[1])
                    with Image.open(effect_path) as p_img: final_np = composite_numpy(np.array(face_img), p_img.convert("RGBA"), new_pos)
                    final_name = f"{os.path.splitext(face_name)[0]}_{get_short_name(effect_path)}.png"
                    output_path = os.path.join(fuku_face_effect_dir, final_name)
                    if not os.path.exists(output_path): Image.fromarray(final_np).save(output_path)
        
        if hoho_files:
            fuku_face_hoho_dir = os.path.join(output_root, "fuku_face_hoho"); ensure_dir(fuku_face_hoho_dir)
            hoho_face_images = {}
            for body_name, body_img in body_bases.items():
                for hoho_path in hoho_files:
                    pos = get_image_position(hoho_path, offset_data); new_pos = (pos[0]+global_offset[0], pos[1]+global_offset[1])
                    with Image.open(hoho_path) as p_img: base_np = composite_numpy(np.array(body_img), p_img.convert("RGBA"), new_pos)
                    for kao_path in kao_files:
                        pos = get_image_position(kao_path, offset_data); new_pos = (pos[0]+global_offset[0], pos[1]+global_offset[1])
                        with Image.open(kao_path) as p_img: kao_np = composite_numpy(base_np.copy(), p_img.convert("RGBA"), new_pos)
                        name_parts = [body_name, get_short_name(hoho_path), get_short_name(kao_path)]
                        if kuchi_files:
                            for kuchi_path in kuchi_files:
                                 pos = get_image_position(kuchi_path, offset_data); new_pos = (pos[0]+global_offset[0], pos[1]+global_offset[1])
                                 with Image.open(kuchi_path) as p_img: final_np = composite_numpy(kao_np.copy(), p_img.convert("RGBA"), new_pos)
                                 final_name = "_".join(name_parts + [get_short_name(kuchi_path)]) + ".png"
                                 final_img = Image.fromarray(final_np); output_path = os.path.join(fuku_face_hoho_dir, final_name)
                                 if not os.path.exists(output_path): final_img.save(output_path)
                                 hoho_face_images[final_name] = final_img
                        else:
                            final_img = Image.fromarray(kao_np); final_name = "_".join(name_parts) + ".png"
                            output_path = os.path.join(fuku_face_hoho_dir, final_name)
                            if not os.path.exists(output_path): final_img.save(output_path)
                            hoho_face_images[final_name] = final_img
            
            if effect_files:
                fuku_face_hoho_effect_dir = os.path.join(output_root, "fuku_face_hoho_effect"); ensure_dir(fuku_face_hoho_effect_dir)
                for face_name, face_img in hoho_face_images.items():
                    for effect_path in effect_files:
                        pos = get_image_position(effect_path, offset_data); new_pos = (pos[0]+global_offset[0], pos[1]+global_offset[1])
                        with Image.open(effect_path) as p_img: final_np = composite_numpy(np.array(face_img), p_img.convert("RGBA"), new_pos)
                        final_name = f"{os.path.splitext(face_name)[0]}_{get_short_name(effect_path)}.png"
                        output_path = os.path.join(fuku_face_hoho_effect_dir, final_name)
                        if not os.path.exists(output_path): Image.fromarray(final_np).save(output_path)

# ★★★★★【main 函式修改處】★★★★★
def main():
    script_dir = os.getcwd(); print(f"開始掃描目標資料夾於: {script_dir}")
    
    # 新的判斷條件：同時存在 fuku 資料夾和 offset.json 檔案
    char_dirs_to_process = [root for root, dirs, files in os.walk(script_dir) 
                            if FUKU_DIR_NAME in dirs and OFFSET_FILE_NAME in files and 'output' not in root[len(script_dir):]]
    
    if not char_dirs_to_process:
        # 更新提示訊息
        print(f"\n未找到任何同時包含 '{FUKU_DIR_NAME}' 資料夾與 '{OFFSET_FILE_NAME}' 檔案的角色資料夾。"); return
    
    for char_dir in char_dirs_to_process:
        process_character_directory(char_dir)
        
    print(f"\n{'='*60}\n所有角色資料夾處理完畢！\n{'='*60}")

if __name__ == '__main__':
    main()
