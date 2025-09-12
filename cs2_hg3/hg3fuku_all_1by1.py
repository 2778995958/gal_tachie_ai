import os
from PIL import Image
import csv
import itertools
import re
import numpy as np
from multiprocessing import Pool, cpu_count

# --- 核心輔助函式 ---
def ensure_dir(dir_path):
    if not os.path.exists(dir_path): os.makedirs(dir_path)

def get_files_safely(dir_path):
    if not os.path.isdir(dir_path): return []
    return [os.path.join(dir_path, f) for f in os.listdir(dir_path) if f.endswith('.png')]

def get_last_suffix(file_path):
    if not file_path: return ""
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    if '_' in base_name:
        return base_name.rsplit('_', 1)[-1]
    return base_name

# <--- 修改開始: 新增一個函式來取得配對碼 ---
def get_match_key(suffix):
    """從後綴中移除開頭的數字0，取得真正的配對碼 (例如 '00a' -> 'a')"""
    if not suffix:
        return ""
    return suffix.lstrip('0')
# <--- 修改結束 ---

def custom_sort_key(file_path):
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    if '_' in base_name:
        suffix = base_name.rsplit('_', 1)[-1]
        return (len(suffix), suffix)
    return (len(base_name), base_name)

# --- 高精度合成函式 ---
def composite_high_quality(background_img, foreground_img, position):
    base_np = np.array(background_img, dtype=np.float64) / 255.0
    part_np = np.array(foreground_img, dtype=np.float64) / 255.0
    fg_layer = np.zeros_like(base_np)
    dx, dy = position
    part_h, part_w = part_np.shape[:2]; base_h, base_w = base_np.shape[:2]
    x1, y1, x2, y2 = max(dx, 0), max(dy, 0), min(dx + part_w, base_w), min(dy + part_h, base_h)
    px1, py1, px2, py2 = x1 - dx, y1 - dy, x2 - dx, y2 - dy
    if x1 < x2 and y1 < y2: fg_layer[y1:y2, x1:x2] = part_np[py1:py2, px1:px2]
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
def load_coordinates(filepath):
    coords = {}
    if not os.path.exists(filepath): return None
    print(f"--- 正在讀取座標檔案: {filepath} ---")
    try:
        with open(filepath, 'r', encoding='utf-8-sig', errors='ignore') as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                filename = row.get('FileName', '').strip()
                if filename:
                    try:
                        coords[os.path.splitext(filename)[0]] = (int(row['OffsetX']), int(row['OffsetY']), int(row['CanvasWidth']), int(row['CanvasHeight']))
                    except (ValueError, KeyError): pass
    except Exception: return None
    print(f"--- 成功讀取 {len(coords)} 筆座標 ---")
    return coords

def find_coords_info(png_path, coords_data):
    base_name = os.path.splitext(os.path.basename(png_path))[0]
    match = re.match(r'^(.*)([-_]\d+)$', base_name)
    if match and match.group(1) in coords_data: return coords_data[match.group(1)]
    if base_name in coords_data: return coords_data[base_name]
    print(f"     - 警告：在座標檔中找不到與 '{os.path.basename(png_path)}' 對應的座標。")
    return None

# --- 核心合成任務 ---
def process_task(args):
    parts_list, canvas_size, output_path, coords_data = args
    if os.path.exists(output_path): return

    print(f"     - 正在合成: {os.path.basename(output_path)}")
    canvas = Image.new('RGBA', canvas_size, (0, 0, 0, 0))
    for part_path in parts_list:
        part_info = find_coords_info(part_path, coords_data)
        if part_info:
            try:
                part_image = Image.open(part_path).convert("RGBA")
                canvas = composite_high_quality(canvas, part_image, (part_info[0], part_info[1]))
            except FileNotFoundError:
                print(f"       - 錯誤：檔案不存在 '{part_path}'")
    canvas.save(output_path)

def process_character(char_dir, coords_data):
    char_name = os.path.basename(char_dir)
    print(f"\n{'='*25}\n處理角色: {char_name}\n{'='*25}")
    
    # 1. 設定路徑
    fuku_dir, kao_dir, kami_dir, kuchi_dir, hoho_dir, effect_dir = [os.path.join(char_dir, name) for name in ["fuku", "kao", "kami", "kuchi", "hoho", "effect"]]
    output_dir = os.path.join(char_dir, "output")
    kao_kuchi_dir, kao_kuchi_hoho_dir = [os.path.join(output_dir, name) for name in ["kao_kuchi", "kao_kuchi_hoho"]]
    kao_kuchi_effect_dir, kao_kuchi_hoho_effect_dir = f"{kao_kuchi_dir}_effect", f"{kao_kuchi_hoho_dir}_effect"
    for d in [output_dir, kao_kuchi_dir, kao_kuchi_hoho_dir, kao_kuchi_effect_dir, kao_kuchi_hoho_effect_dir]:
        ensure_dir(d)

    # 2. 獲取所有部件
    fuku_items = [os.path.join(fuku_dir, name) for name in os.listdir(fuku_dir)] if os.path.exists(fuku_dir) else []
    kao_files = get_files_safely(kao_dir)
    kami_files = get_files_safely(kami_dir)
    kuchi_files = get_files_safely(kuchi_dir)
    hoho_files = get_files_safely(hoho_dir)
    effect_files = get_files_safely(effect_dir)

    if not fuku_items or not kao_files:
        print(f"  - 錯誤：角色 '{char_name}' 的 fuku 或 kao 資料夾為空，無法繼續。")
        return

    # 3. 建立所有組合任務列表
    tasks = []
    
    # <--- 修改開始: 使用 get_match_key 來建立對照表 ---
    # 對照表的 "鍵" 是 'a', "值" 是 '.../Tkars01L_000a.png'
    kuchi_map = {get_match_key(get_last_suffix(f)): f for f in kuchi_files}
    # <--- 修改結束 ---

    kami_cycle = kami_files or [None]
    hoho_cycle = hoho_files or [None]
    effect_cycle = effect_files or [None]
    
    for fuku_item, kami, hoho, effect in itertools.product(
        fuku_items, kami_cycle, hoho_cycle, effect_cycle):
        
        for kao in kao_files:
            kao_suffix = get_last_suffix(kao)
            # <--- 修改開始: 使用 get_match_key 來查找配對 ---
            # 取得 kao 的配對碼 (例如 '00a' -> 'a')
            match_key = get_match_key(kao_suffix)
            # 使用配對碼 'a' 去查找 kuchi
            kuchi = kuchi_map.get(match_key)
            # <--- 修改結束 ---
            
            fuku_parts = get_files_safely(fuku_item) if os.path.isdir(fuku_item) else [fuku_item]
            if not fuku_parts: continue
            
            base_info = find_coords_info(fuku_parts[0], coords_data)
            if not base_info: continue
            canvas_size = (base_info[2], base_info[3])
            
            base_parts = fuku_parts + [p for p in [kao, kami, kuchi] if p]
            
            # 任務1: kao_kuchi
            parts1 = list(base_parts); parts1.sort(key=custom_sort_key)
            name_parts1 = [char_name] + [get_last_suffix(p) for p in parts1]
            filename1 = "_".join(name_parts1) + ".png"
            tasks.append((parts1, canvas_size, os.path.join(kao_kuchi_dir, filename1), coords_data))
            
            # 任務2: kao_kuchi_effect
            if effect:
                parts2 = base_parts + [effect]; parts2.sort(key=custom_sort_key)
                name_parts2 = [char_name] + [get_last_suffix(p) for p in parts2]
                filename2 = "_".join(name_parts2) + ".png"
                tasks.append((parts2, canvas_size, os.path.join(kao_kuchi_effect_dir, filename2), coords_data))
            
            # 任務3: kao_kuchi_hoho
            if hoho:
                parts3 = base_parts + [hoho]; parts3.sort(key=custom_sort_key)
                name_parts3 = [char_name] + [get_last_suffix(p) for p in parts3]
                filename3 = "_".join(name_parts3) + ".png"
                tasks.append((parts3, canvas_size, os.path.join(kao_kuchi_hoho_dir, filename3), coords_data))

            # 任務4: kao_kuchi_hoho_effect
            if hoho and effect:
                parts4 = base_parts + [hoho, effect]; parts4.sort(key=custom_sort_key)
                name_parts4 = [char_name] + [get_last_suffix(p) for p in parts4]
                filename4 = "_".join(name_parts4) + ".png"
                tasks.append((parts4, canvas_size, os.path.join(kao_kuchi_hoho_effect_dir, filename4), coords_data))

    # 4. 使用多執行緒處理所有獨立的合成任務
    if tasks:
        num_processes = min(cpu_count(), len(tasks))
        print(f"  - 發現 {len(tasks)} 個獨立合成任務，將使用 {num_processes} 個核心處理...")
        with Pool(processes=num_processes) as pool:
            pool.map(process_task, tasks)

# --- 主程式入口 ---
def main():
    script_dir = os.getcwd()
    coords_path = os.path.join(script_dir, "hg3_coordinates.txt")
    coords_data = load_coordinates(coords_path)
    if not coords_data:
        input("錯誤：座標檔讀取失敗，請按 Enter 鍵結束。")
        return

    character_folders = [os.path.join(script_dir, item) for item in os.listdir(script_dir) if os.path.isdir(item) and os.path.isdir(os.path.join(item, "fuku"))]
    if not character_folders:
        print("未找到任何有效的角色資料夾。")
        return
    
    print(f"\n掃描完成！發現 {len(character_folders)} 個待處理的角色資料夾:")
    for folder in character_folders:
        print(f"  - {os.path.basename(folder)}")

    for char_folder in character_folders:
        process_character(char_folder, coords_data)

    print(f"\n{'='*50}\n🎉 所有角色均已處理完畢！ 🎉\n{'='*50}")
    input("請按 Enter 鍵結束程式。")

if __name__ == '__main__':
    main()
