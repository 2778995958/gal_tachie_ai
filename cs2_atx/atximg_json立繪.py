import os
import json
from PIL import Image
import numpy as np
import re
from collections import defaultdict

# --- 基礎設定 ---
OFFSET_FILE_NAME = "offset.json"
CHARLIST_FILE_NAME = "charlist.cl"
EXCLUDE_DIRS = ['output', 'atx', '新增資料夾', '新增資料夾 (2)']

# --- 核心工具函式 (無變動) ---
def ensure_dir(dir_path):
    if not os.path.exists(dir_path): os.makedirs(dir_path)

def load_json_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f: return json.load(f)
    except UnicodeDecodeError:
        try:
            with open(file_path, 'r', encoding='shift_jis') as f: return json.load(f)
        except Exception as e: print(f"錯誤：使用 Shift-JIS 讀取 {file_path} 失敗: {e}"); return None
    except Exception as e: print(f"錯誤：讀取 {file_path} 失敗: {e}"); return None

def get_image_position(file_path, offset_data):
    key = os.path.splitext(os.path.basename(file_path))[0]
    position = offset_data.get(key)
    if position:
        if isinstance(position, (tuple, list)) and len(position) >= 2: return tuple(position[:2])
        if isinstance(position, dict) and 'x' in position and 'y' in position: return (position['x'], position['y'])
        print(f"警告：在 offset.json 中找到鍵 '{key}' 的座標格式不正確。"); return (0, 0)
    else:
        print(f"警告：在 offset.json 中找不到鍵 '{key}' 的座標。"); return (0, 0)

def composite_numpy(base_np, part_img, part_pos):
    try:
        part_np = np.array(part_img.convert("RGBA"), dtype=np.uint8)
        part_h, part_w, _ = part_np.shape; base_h, base_w, _ = base_np.shape
        x, y = part_pos
        x1, y1 = max(x, 0), max(y, 0); x2, y2 = min(x + part_w, base_w), min(y + part_h, base_h)
        part_x1, part_y1 = x1 - x, y1 - y; part_x2, part_y2 = x2 - x, y2 - y
        if x1 >= x2 or y1 >= y2: return base_np
        base_region = base_np[y1:y2, x1:x2]; part_region = part_np[part_y1:part_y2, part_x1:part_x2]
        part_alpha = (part_region[:, :, 3] / 255.0)[:, :, np.newaxis]
        blended_rgb = (part_region[:, :, :3] * part_alpha + base_region[:, :, :3] * (1 - part_alpha)).astype(np.uint8)
        new_alpha = (part_region[:, :, 3] + base_region[:, :, 3] * (1 - part_alpha.squeeze())).astype(np.uint8)
        base_np[y1:y2, x1:x2, :3] = blended_rgb; base_np[y1:y2, x1:x2, 3] = new_alpha
        return base_np
    except Exception as e:
        print(f"      └ 錯誤: NumPy 合成失敗: {e}"); return base_np

# --- 核心邏輯函式 ---
def parse_charlist(file_path):
    if not os.path.exists(file_path):
        print(f"錯誤: 找不到組裝說明書 {file_path}"); return None
    print(f"--- 正在解析組裝說明書: {os.path.basename(file_path)} ---")
    content_lines = None
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f: content_lines = f.readlines()
        print(" > 已使用 UTF-8 編碼成功讀取。")
    except UnicodeDecodeError:
        print(" > UTF-8 讀取失敗，自動嘗試使用 Shift-JIS (日文) 編碼...")
        try:
            with open(file_path, 'r', encoding='shift_jis') as f: content_lines = f.readlines()
            print(" > 已使用 Shift-JIS 編碼成功讀取。")
        except Exception as e: print(f"錯誤: 使用 UTF-8 和 Shift-JIS 編碼解析 '{file_path}' 均失敗: {e}"); return None
    except Exception as e: print(f"錯誤: 讀取 '{file_path}' 時發生未知錯誤: {e}"); return None
    if content_lines is None: return None
    sections = {}
    current_section_key = None
    for line in content_lines:
        line = line.strip()
        if not line: continue
        if line.startswith('#'):
            current_section_key = line[1:]
            sections[current_section_key] = []
        elif current_section_key:
            sections[current_section_key].append(line)
    print(f" > 解析完成，找到 {len(sections)} 個區塊。")
    return sections

def find_part_folder(base_dir, folder_prefix, part_code):
    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for subdir_name in dirs:
            if subdir_name.startswith(folder_prefix) and subdir_name.endswith(part_code):
                return os.path.join(root, subdir_name)
    return None

def find_specific_file(search_dir, filename_to_find):
    path = os.path.join(search_dir, filename_to_find)
    if os.path.exists(path): return path
    try:
        for item in os.listdir(search_dir):
            item_path = os.path.join(search_dir, item)
            if os.path.isdir(item_path) and item not in EXCLUDE_DIRS:
                file_path = os.path.join(item_path, filename_to_find)
                if os.path.exists(file_path): return file_path
    except FileNotFoundError: return None
    return None

def process_character_from_cl(cl_path):
    char_dir = os.path.dirname(cl_path)
    print(f"\n{'='*25} 開始處理檔案: {os.path.basename(cl_path)} {'='*25}")

    cl_data = parse_charlist(cl_path)
    if cl_data is None: return

    print("\n--- 步驟 1: 根據 charlist.cl 預先建立資料夾索引 ---")
    directory_cache = {}
    all_pose1_prefixes = {}
    for key, lines in cl_data.items():
        if key.startswith("pose1@"):
            for line in lines:
                parts = line.split()
                if len(parts) < 2: continue
                all_pose1_prefixes[parts[1]] = parts[0]
    unique_folder_lookups = set()
    for pose2_label, folder_prefix in all_pose1_prefixes.items():
        for p2_line in cl_data.get(pose2_label, []):
            try:
                part_code = p2_line.split(',')[1].strip()
                if part_code and part_code != '@':
                    unique_folder_lookups.add((folder_prefix, part_code))
            except IndexError: continue
    print(f" > 找到 {len(unique_folder_lookups)} 個獨一無二的資料夾搜尋組合，開始建立索引...")
    for folder_prefix, part_code in unique_folder_lookups:
        cache_key = (folder_prefix, part_code)
        folder_path = find_part_folder(char_dir, folder_prefix, part_code)
        directory_cache[cache_key] = folder_path
        if not folder_path:
            print(f"   > 索引警告: 找不到 ({folder_prefix}, {part_code}) 的對應資料夾")
    print(" > 資料夾索引建立完畢。")

    top_key = '_TOP_'
    if top_key not in cl_data:
        print(f"錯誤: 在 {os.path.basename(cl_path)} 中找不到主索引區塊 '#_TOP_'。"); return
    character_sets_to_process = cl_data.get(top_key, [])
    print(f"\n--- 步驟 2: 開始遍歷角色集 ---")
    print(f"在主目錄 #_TOP_ 中找到 {len(character_sets_to_process)} 個定義...")

    for char_entry_line in character_sets_to_process:
        entry_parts = char_entry_line.split();
        if len(entry_parts) < 2: continue
        pose1_key = entry_parts[1]
        if pose1_key not in cl_data: print(f"\n[!] 警告: 在 #_TOP_ 中定義的區塊 '{pose1_key}' 不存在於檔案中，跳過。"); continue
        try: character_name = pose1_key.split('@')[1].replace('.txt', '')
        except IndexError: character_name = pose1_key
        print(f"\n{'='*15}>> 開始處理角色集: {character_name} (來自 #{pose1_key}) <<{'='*15}")
        
        for pose1_line in cl_data.get(pose1_key, []):
            parts = pose1_line.split();
            if len(parts) < 2: continue
            folder_prefix, pose2_label = parts[0], parts[1]
            print(f"\n處理中 Pose Group: [ {folder_prefix} ], Section: [ {pose2_label} ]...")
            pose2_lines = cl_data.get(pose2_label, [])
            if not pose2_lines:
                print(f"  [!] 警告: 區塊 #{pose2_label} 為空，跳過。"); continue

            grouped_pose2_lines = defaultdict(list)
            for line in pose2_lines:
                try:
                    group_key = line.split(',')[1].strip()
                    grouped_pose2_lines[group_key].append(line)
                except IndexError: continue

            for group_key, lines_in_group in grouped_pose2_lines.items():
                print(f"\n  --- 開始處理分組 (第二欄為 '{group_key}') ---")
                active_fuku_dir = directory_cache.get((folder_prefix, group_key))
                if not active_fuku_dir:
                    print(f"    [!] 警告: 從索引中找不到分組 '{group_key}' 的對應資料夾，跳過此分組。"); continue

                print(f"    - 正在為分組 '{group_key}' 預掃描資源...")
                parts_to_scan = set()
                all_local_offsets = {}
                offset_path = os.path.join(active_fuku_dir, OFFSET_FILE_NAME)
                offset_data_raw = load_json_file(offset_path)
                if offset_data_raw:
                    all_local_offsets.update({item['Key']: item['Value'] for item in offset_data_raw} if isinstance(offset_data_raw, list) else offset_data_raw)

                for p2_line in lines_in_group:
                    base_cloth_code = p2_line.split(',')[1].strip()
                    weapon_part_code = p2_line.split(',')[2].strip()
                    face_label_for_line = p2_line.split()[-1].strip()
                    active_folder_name = os.path.basename(active_fuku_dir)
                    filename_prefix = active_folder_name[:-len(base_cloth_code)] if active_folder_name.endswith(base_cloth_code) else active_folder_name
                    parts_to_scan.add(os.path.join(active_fuku_dir, f"{filename_prefix}_{base_cloth_code}.png"))
                    if weapon_part_code not in ['@', '0']:
                        parts_to_scan.add(os.path.join(active_fuku_dir, f"{filename_prefix}_{weapon_part_code.zfill(2)}.png"))
                    for f_line in cl_data.get(face_label_for_line, []):
                        face_line_parts = f_line.split(',')
                        face_part_rules = {3: (3, {}), 4: (4, {}), 5: (5, {}), 6: (6, {}), 7: (7, {})}
                        for index, (padding, value_map) in face_part_rules.items():
                            if index >= len(face_line_parts): continue
                            input_code = face_line_parts[index].strip()
                            if not input_code or input_code in ['@', '0']: continue
                            output_code = value_map.get(input_code, input_code)
                            parts_to_scan.add(os.path.join(active_fuku_dir, f"{filename_prefix}_{output_code.zfill(padding)}.png"))
                
                min_x, min_y, max_x, max_y = float('inf'), float('inf'), float('-inf'), float('-inf')
                for path in parts_to_scan:
                    pos = get_image_position(path, all_local_offsets)
                    try:
                        with Image.open(path) as img: size = img.size
                        min_x, min_y = min(min_x, pos[0]), min(min_y, pos[1])
                        max_x, max_y = max(max_x, pos[0] + size[0]), max(max_y, pos[1] + size[1])
                    except FileNotFoundError: pass
                    except Exception as e: print(f"    [!] 預掃描警告: 無法讀取檔案尺寸: {path}, 錯誤: {e}")
                
                if any(v == float('inf') or v == float('-inf') for v in [min_x, min_y, max_x, max_y]):
                    print(f"    [!] 錯誤：在預掃描後無法確定分組 '{group_key}' 的畫布尺寸，跳過此分組。"); continue
                group_canvas_size = (max_x - min_x, max_y - min_y)
                group_offset = (-min_x, -min_y)
                print(f"    > 為分組 '{group_key}' 計算出統一畫布: {group_canvas_size} | 統一偏移: {group_offset}")

                fuku_counter = 0
                for pose2_line in lines_in_group:
                    fuku_counter += 1
                    print(f"      --- 處理身體組合 #{fuku_counter} (分組 '{group_key}') ---")
                    base_cloth_code = pose2_line.split(',')[1].strip()
                    weapon_part_code = pose2_line.split(',')[2].strip()
                    active_folder_name = os.path.basename(active_fuku_dir)
                    filename_prefix = active_folder_name[:-len(base_cloth_code)] if active_folder_name.endswith(base_cloth_code) else active_folder_name
                    output_dir = os.path.join(active_fuku_dir, "output"); ensure_dir(output_dir)
                    fuku_base_canvas = np.zeros((group_canvas_size[1], group_canvas_size[0], 4), dtype=np.uint8)
                    
                    cloth_filename = f"{filename_prefix}_{base_cloth_code}.png"
                    cloth_filepath = os.path.join(active_fuku_dir, cloth_filename)
                    if os.path.exists(cloth_filepath):
                        print(f"        - 組合身體部件 (衣服): {cloth_filename}")
                        with Image.open(cloth_filepath) as p_img:
                            pos = get_image_position(cloth_filepath, all_local_offsets)
                            fuku_base_canvas = composite_numpy(fuku_base_canvas, p_img, (pos[0] + group_offset[0], pos[1] + group_offset[1]))
                    else: print(f"        - 警告: 找不到身體部件 (衣服) {cloth_filename}")
                    
                    if weapon_part_code not in ['@', '0']:
                        weapon_filename = f"{filename_prefix}_{weapon_part_code.zfill(2)}.png"
                        weapon_filepath = os.path.join(active_fuku_dir, weapon_filename)
                        if os.path.exists(weapon_filepath):
                            print(f"        - 組合身體部件 (武器): {weapon_filename}")
                            with Image.open(weapon_filepath) as p_img:
                                pos = get_image_position(weapon_filepath, all_local_offsets)
                                fuku_base_canvas = composite_numpy(fuku_base_canvas, p_img, (pos[0] + group_offset[0], pos[1] + group_offset[1]))
                        else: print(f"        - 警告: 找不到身體部件 (武器) {weapon_filename}")
                    
                    fuku_base_image = Image.fromarray(fuku_base_canvas)
                    face_label = pose2_line.split()[-1].strip()
                    face_lines = cl_data.get(face_label, [])
                    if not face_lines:
                        print("      - 未找到對應的face區塊或區塊為空，跳過此身體組合的圖片生成。"); continue
                    
                    face_counter = 0
                    for face_line in face_lines:
                        face_counter += 1
                        final_canvas_np = np.array(fuku_base_image)
                        print(f"        - 組合表情 #{face_counter}")
                        face_line_parts = face_line.split(',')
                        face_part_rules = {3: (3, {}), 4: (4, {}), 5: (5, {}), 6: (6, {}), 7: (7, {})}
                        for index, (padding, value_map) in face_part_rules.items():
                            if index >= len(face_line_parts): continue
                            input_code = face_line_parts[index].strip()
                            if not input_code or input_code in ['@', '0']: continue
                            output_code = value_map.get(input_code, input_code)
                            filename_to_find = f"{filename_prefix}_{output_code.zfill(padding)}.png"
                            part_path = find_specific_file(active_fuku_dir, filename_to_find)
                            if part_path:
                                with Image.open(part_path) as p_img:
                                    pos = get_image_position(part_path, all_local_offsets)
                                    final_canvas_np = composite_numpy(final_canvas_np, p_img, (pos[0] + group_offset[0], pos[1] + group_offset[1]))
                            else: print(f"          > 警告: 在當前作用域中找不到 {filename_to_find}")
                        
                        # 【★★★★★ 最終檔名格式 ★★★★★】
                        # 組合描述性名稱 (ca21a) 和 唯一性流水號 (fuku1)
                        descriptive_part = f"{folder_prefix}{base_cloth_code}"
                        output_filename = f"{character_name}_{descriptive_part}_fuku{fuku_counter}_face{face_counter}.png"
                        
                        output_path = os.path.join(output_dir, output_filename)
                        if os.path.exists(output_path):
                            print(f"        > 檔案已存在，跳過: {output_filename}")
                            continue

                        Image.fromarray(final_canvas_np).save(output_path)
                        print(f"        > √ 已儲存於: {os.path.relpath(output_path, char_dir)}")

def main():
    script_dir = os.getcwd()
    print(f"開始掃描目標資料夾於: {script_dir}")
    cl_files_to_process = []
    for root, dirs, files in os.walk(script_dir):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        if CHARLIST_FILE_NAME in files: cl_files_to_process.append(os.path.join(root, CHARLIST_FILE_NAME))
    if not cl_files_to_process: print(f"\n未找到任何可處理的 '{CHARLIST_FILE_NAME}' 檔案。"); return
    print(f"\n找到 {len(cl_files_to_process)} 個待處理的角色。")
    for cl_path in cl_files_to_process: process_character_from_cl(cl_path)
    print(f"\n{'='*60}\n所有角色資料夾處理完畢！\n{'='*60}")

if __name__ == '__main__':
    main()
