# 【最終典藏版 Ver. 34.0 - 多執行緒極速合成版】
import pandas as pd
from PIL import Image
import os
import csv
from collections import defaultdict
import glob
from datetime import datetime
import itertools 
import concurrent.futures # 導入多執行緒模組
import threading          # 導入鎖定模組

# ==============================================================================
# --- 使用者設定區 ---
SPECIAL_UNDERLAY_IDS = {8320, 8321} 
PRIORITY_OVERLAY_PATHS = {'かぶせ 水着'}
MAX_WORKERS = 8  # 設定同時處理的執行緒數量 (建議設定為 CPU 核心數的 1~2 倍，例如 4, 8, 16)
# ==============================================================================

# 建立全域鎖，防止多執行緒同時寫入檔案造成衝突
log_lock = threading.Lock()
set_lock = threading.Lock()

# --- 1. 資料讀取與預處理 ---
def load_layer_data_with_paths(filepath):
    print(f"[INFO] 正在解析 '{filepath}'...")
    parsed_data = []
    try:
        with open(filepath, 'r', encoding='utf-8', newline='') as f:
            next(f); next(f) # Skip headers
            reader = csv.reader(f, delimiter='\t')
            for row in reader:
                if len(row) >= 10 and row[9].strip().isdigit():
                    parsed_data.append({
                        'layer_id': int(row[9].strip()), 'name': row[1].strip(),
                        'left': int(row[2].strip()), 'top': int(row[3].strip()),
                        'width': int(row[4].strip()) if len(row) > 4 and row[4].strip().isdigit() else 0,
                        'height': int(row[5].strip()) if len(row) > 5 and row[5].strip().isdigit() else 0,
                        'opacity': int(row[7].strip()) if len(row) > 7 and row[7].strip().isdigit() else 255,
                        'group_layer_id': int(row[10].strip()) if len(row) > 10 and row[10].strip().isdigit() else 0
                    })
        df = pd.DataFrame(parsed_data)
        print(f"[INFO] '{filepath}' 解析成功，載入 {len(df)} 個圖層。")
        
        print("[INFO] 正在建立圖層的完整路徑...")
        id_to_info = df.set_index('layer_id').to_dict('index')
        paths = {}
        for layer_id in df['layer_id']:
            current_id, path_parts, visited_ids = layer_id, [], set()
            while current_id in id_to_info and current_id not in visited_ids:
                visited_ids.add(current_id)
                info = id_to_info[current_id]
                if info['name']: path_parts.append(info['name'])
                parent_id = info['group_layer_id']
                if parent_id == 0: break
                current_id = parent_id
            paths[layer_id] = "/".join(reversed(path_parts))
        df['full_path'] = df['layer_id'].map(paths)
        df['full_path'] = df['full_path'].fillna(df['name'])
        print("[INFO] 完整路徑建立完成。")
        return df
    except Exception as e:
        print(f"[錯誤] 處理 '{filepath}' 時發生問題: {e}")
        return None

def load_sinfo_data_manual(filepath):
    print(f"[INFO] 正在解析 '{filepath}'...")
    rules = []

    def clean_path(p):
        return "/".join(component.strip() for component in p.split('/'))

    try:
        with open(filepath, 'r', encoding='utf-8', newline='') as f:
            reader = csv.reader(f, delimiter='\t')
            for row in reader:
                if not row: continue
                rule_type = row[0].strip()

                if rule_type == 'dress':
                    cleaned_row = [item.strip() for item in row]
                    rules.append({'type': 'dress', 'data': cleaned_row})

                elif rule_type == 'face':
                    face_path = clean_path(row[3])
                    rules.append({'type': 'face', 'name': row[1].strip(), 'path': face_path})

                elif rule_type == 'facegroup':
                     if len(row) >= 2:
                        rules.append({'type': 'facegroup', 'group_name': row[1].strip()})

                elif rule_type == 'fgname':
                    if len(row) >= 2:
                        part_name = row[1].strip()
                        part_path = clean_path(row[2]) if len(row) >= 3 else ""
                        rules.append({'type': 'fgname', 'name': part_name, 'path': part_path})

                elif rule_type == 'fgalias':
                    if len(row) >= 3:
                        alias_name = row[1].strip()
                        part_names = [p.strip() for p in row[2:]]
                        rules.append({'type': 'fgalias', 'name': alias_name, 'parts': part_names})

        print(f"[INFO] '{filepath}' 解析成功。")
        return rules
    except Exception as e:
        print(f"[錯誤] 手動解析 '{filepath}' 時發生問題: {e}")
        return []

# --- 2. 影像合成核心邏輯 (多執行緒工作單元) ---
def create_composite_task(layers_to_draw, base_info, output_path, log_file, combination_context):
    """
    這是要在執行緒中運行的函數。它負責實際的圖片合成與存檔。
    """
    if not layers_to_draw: return
    
    try:
        char_base_name = os.path.basename(os.path.dirname(output_path))
        base_x, base_y = base_info['left'], base_info['top']
        
        # 計算畫布大小
        first_part_info = layers_to_draw[0]
        min_x = first_part_info['left'] - base_x
        min_y = first_part_info['top'] - base_y
        max_x = min_x + first_part_info['width']
        max_y = min_y + first_part_info['height']

        for part_info in layers_to_draw[1:]:
            dx, dy = part_info['left'] - base_x, part_info['top'] - base_y
            min_x, min_y = min(min_x, dx), min(min_y, dy)
            max_x, max_y = max(max_x, dx + part_info['width']), max(max_y, dy + part_info['height'])
        
        canvas_width = max_x - min_x
        canvas_height = max_y - min_y
        master_canvas = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))

        for part_info in layers_to_draw:
            part_img_path = os.path.join(char_base_name, f"{char_base_name}_{part_info['layer_id']}.png")
            # 這裡不檢查檔案是否存在，因為主執行緒已經檢查過了，但為了安全加個 try
            try:
                part_img = Image.open(part_img_path).convert("RGBA")
            except FileNotFoundError:
                continue # 如果真的發生意外，跳過該層

            part_opacity = part_info.get('opacity', 255)
            if part_opacity < 255:
                alpha = part_img.getchannel('A').point(lambda p: p * (part_opacity / 255.0))
                part_img.putalpha(alpha)

            paste_x = (part_info['left'] - base_x) - min_x
            paste_y = (part_info['top'] - base_y) - min_y
            
            # 使用 Alpha Composite
            layer_canvas = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))
            layer_canvas.paste(part_img, (paste_x, paste_y))
            master_canvas = Image.alpha_composite(master_canvas, layer_canvas)

        master_canvas.save(output_path)
        
        # 使用鎖來保護寫入操作
        with log_lock:
            print(f"  ✅ [執行緒完成] {os.path.basename(output_path)}")
            log_file.write(f"[成功生成] {combination_context}: '{os.path.basename(output_path)}'\n")
            
    except Exception as e:
        with log_lock:
            print(f"  ❌ [錯誤] {os.path.basename(output_path)}: {e}")
            log_file.write(f"合成圖片錯誤: 檔案 '{os.path.basename(output_path)}' 生成失敗. 原因: {e}\n")

# --- 3. 核心處理邏輯 ---
def log_missing_assets(layer_df, char_base_name, log_file):
    print(f"[INFO] 正在進行素材完整性檢查...")
    log_file.write(f"\n--- 素材檔案完整性檢查 ---\n")
    missing_count = 0
    for _, row in layer_df.iterrows():
        if row['width'] == 0 and row['height'] == 0:
            continue
        
        img_path = os.path.join(char_base_name, f"{char_base_name}_{row['layer_id']}.png")
        if not os.path.exists(img_path):
            log_file.write(f"[素材檔案缺失] 找不到圖片: {img_path} (對應圖層名: '{row['name']}', ID: {row['layer_id']})\n")
            missing_count += 1
    
    if missing_count == 0:
        print("[INFO] 素材完整性檢查完畢，未發現缺失檔案。")
        log_file.write("所有在 .txt 中定義的實體圖層都有對應的 .png 檔案。\n")
    else:
        print(f"[警告] 素材完整性檢查完畢，發現 {missing_count} 個缺失的 .png 檔案。詳情請見日誌。")
    log_file.write(f"--- 檢查結束 ---\n")

def process_character(txt_path, sinfo_path, log_file):
    char_base_name = os.path.basename(txt_path).replace('.txt', '')
    output_folder = 'output'
    log_file.write(f"\n===== 開始檢查角色: {char_base_name} =====\n")
    print(f"\n{'='*20} 開始處理角色: {char_base_name} {'='*20}")

    layer_df = load_layer_data_with_paths(txt_path)
    if layer_df is None: return

    log_missing_assets(layer_df, char_base_name, log_file)

    sinfo_rules = load_sinfo_data_manual(sinfo_path)
    if not sinfo_rules: return

    char_output_folder = os.path.join(output_folder, char_base_name)
    generated_filenames_set = set()
    if os.path.exists(char_output_folder):
        print(f"[INFO] 正在掃描已存在的檔案於 '{char_output_folder}'...")
        existing_files = glob.glob(os.path.join(char_output_folder, '*.png'))
        generated_filenames_set.update(os.path.basename(f) for f in existing_files)
        print(f"[INFO] 掃描完成，發現 {len(generated_filenames_set)} 個已生成檔案。")

    path_to_id = pd.Series(layer_df.layer_id.values, index=layer_df.full_path).to_dict()
    id_to_path = {v: k for k, v in path_to_id.items()}
    
    # --- 規則分類 ---
    face_rules = defaultdict(list)
    conditional_faces = defaultdict(lambda: defaultdict(dict))
    facegroup_order = [r['group_name'] for r in sinfo_rules if r['type'] == 'facegroup']
    fgname_rules = [r for r in sinfo_rules if r['type'] == 'fgname']
    fgalias_rules = [r for r in sinfo_rules if r['type'] == 'fgalias']
    
    # --- Dress 規則處理 ---
    all_dress_rules_raw = [r['data'] for r in sinfo_rules if r['type'] == 'dress']
    dress_rules = defaultdict(lambda: defaultdict(list))
    dress_bases = {}

    for row in all_dress_rules_raw:
        if len(row) >= 4 and row[2].strip() == 'base':
            dress_name = row[1].strip()
            dress_bases[dress_name] = row[3].strip()

    for row in all_dress_rules_raw:
        dress_name = row[1].strip()
        if len(row) >= 5 and row[2].strip() == 'diff':
            diff_id = row[3].strip()
            diff_path = row[4].strip()
            dress_rules[dress_name][diff_id].append(diff_path)
        elif len(row) >= 5 and row[2].strip() != 'base':
            diff_id = row[3].strip()
            diff_path = row[4].strip()
            dress_rules[dress_name][diff_id].append(diff_path)
            
    for dress_name, base_path in dress_bases.items():
        if dress_name in dress_rules:
            for diff_id in dress_rules[dress_name]:
                dress_rules[dress_name][diff_id].insert(0, base_path)


    for rule in [r for r in sinfo_rules if r['type'] == 'face']:
        if '@' in rule['name']:
            face_name, condition = rule['name'].split('@', 1)
            if condition not in conditional_faces[face_name]: conditional_faces[face_name][condition] = []
            conditional_faces[face_name][condition].append(rule['path'])
        else:
            face_rules[rule['name']].append(rule['path'])

    generated_face_rules = {}
    fgname_to_paths_map = defaultdict(list)
    for rule in fgname_rules:
        fgname_to_paths_map[rule['name']].append(rule['path'])

    if fgalias_rules:
        print(f"[INFO] 偵測到 {len(fgalias_rules)} 條 fgalias 規則，將以此為準生成表情。")
        for alias_rule in fgalias_rules:
            alias_name = alias_rule['name']
            combo_paths = []
            for part_name in alias_rule['parts']:
                if part_name in fgname_to_paths_map:
                    paths = fgname_to_paths_map[part_name]
                    combo_paths.extend([p for p in paths if p and p.lower() != 'dummy'])
            generated_face_rules[alias_name] = combo_paths
    
    elif facegroup_order and fgname_rules:
        print("[INFO] 未偵測到 fgalias 規則，自動生成所有表情組合...")
        part_lists_in_order = []
        for group in facegroup_order:
            options_for_group = []
            for name, paths in fgname_to_paths_map.items():
                if name.startswith(group):
                    options_for_group.append((name, paths))
            if options_for_group:
                part_lists_in_order.append(options_for_group)
        
        if part_lists_in_order:
            all_combinations = list(itertools.product(*part_lists_in_order))
            for combo in all_combinations:
                combo_name = "_".join(part_tuple[0] for part_tuple in combo)
                combo_paths = [path for part_tuple in combo for path in part_tuple[1] if path]
                generated_face_rules[combo_name] = combo_paths

    final_face_rules = generated_face_rules if generated_face_rules else face_rules
    if not final_face_rules:
        print("[警告] 未找到任何有效的 'face' 或 'facegroup'/'fgalias' 規則。")
        return

    # --- 啟動多執行緒 ---
    print(f"[INFO] 啟動多執行緒處理，使用 {MAX_WORKERS} 個 Worker...")
    
    # 使用 ThreadPoolExecutor 管理執行緒
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []

        for dress_name, diffs in dress_rules.items():
            for diff_id, dress_paths in diffs.items():
                current_dress_key = f"{dress_name}_{diff_id}"
                
                last_dress_path = dress_paths[-1] if dress_paths else None
                forced_top_layer_id = path_to_id.get(last_dress_path) if last_dress_path else None
                
                dress_layer_ids = []
                for p in dress_paths:
                    lid = path_to_id.get(p)
                    if lid is not None: dress_layer_ids.append(lid)
                
                # 提交任務
                submit_face_combinations(executor, futures, final_face_rules, dress_layer_ids, forced_top_layer_id, path_to_id, id_to_path, layer_df, char_base_name, current_dress_key, generated_filenames_set, log_file, output_folder)
                
                for face_name, conditions in conditional_faces.items():
                    if matches_condition(dress_name, condition):
                        submit_face_combinations(executor, futures, {face_name: face_paths}, dress_layer_ids, forced_top_layer_id, path_to_id, id_to_path, layer_df, char_base_name, f"{current_dress_key}@{condition}", generated_filenames_set, log_file, output_folder)
        
        # 等待所有任務完成
        print(f"[INFO] 所有任務已提交，等待處理完成...")
        concurrent.futures.wait(futures)

    print(f"\n{'='*20} 角色: {char_base_name} 處理完成 {'='*20}")

def matches_condition(dress_name, condition):
    is_negated = condition.startswith('!')
    if is_negated: condition = condition[1:]
    match = dress_name.startswith(condition[:-1]) if condition.endswith('*') else (dress_name == condition)
    return not match if is_negated else match

# --- 修改為任務提交者 ---
def submit_face_combinations(executor, futures, face_rule_dict, dress_layer_ids, forced_top_layer_id, path_to_id, id_to_path, layer_df, char_base_name, dress_info_str, generated_filenames_set, log_file, output_folder):
    dress_id_set = set(dress_layer_ids)

    for face_name, face_paths in face_rule_dict.items():
        combination_context = f"組合 '{dress_info_str} + {face_name}'"
        
        face_layers = []
        all_paths_found = True
        for p in face_paths:
            lid = path_to_id.get(p)
            if lid is None:
                with log_lock: log_file.write(f"[路徑查找失敗] {combination_context}: 部件路徑 '{p}' 在 .txt 中找不到。\n")
                all_paths_found = False
            face_layers.append(lid)
        
        if not all_paths_found: continue

        all_needed_ids = set(face_layers + dress_layer_ids)
        all_needed_ids.discard(None)
        
        filtered_df = layer_df[layer_df['layer_id'].isin(all_needed_ids)].copy()
        
        # 檢查檔案是否存在 (快速檢查)
        missing_parts_log = []
        all_ids_in_filtered_df = set(filtered_df['layer_id'])
        for lid in all_needed_ids:
            if lid in all_ids_in_filtered_df:
                img_path = os.path.join(char_base_name, f"{char_base_name}_{lid}.png")
                if not os.path.exists(img_path):
                    missing_parts_log.append(f"'{id_to_path.get(lid, '未知')}'({lid})")
            else:
                 missing_parts_log.append(f"'未知圖層'({lid})")
        
        if missing_parts_log:
            with log_lock: log_file.write(f"[組合跳過] {combination_context}: 缺檔: {', '.join(missing_parts_log)}\n")
            continue
        
        layers_data = filtered_df.to_dict('records')
        if not layers_data: continue

        # --- 排序邏輯 (在主執行緒快速完成) ---
        group_dress = []
        group_face = []
        group_top = []
        face_id_set = set(face_layers)

        for item in layers_data:
            lid = item['layer_id']
            if lid == forced_top_layer_id: group_top.append(item)
            elif lid in face_id_set: group_face.append(item)
            elif lid in dress_id_set: group_dress.append(item)
            else: group_dress.append(item)

        group_dress.sort(key=lambda x: x['top'])
        group_face.sort(key=lambda x: x['top'])
        group_top.sort(key=lambda x: x['top'])

        layers_to_draw = group_dress + group_face + group_top
        
        if group_dress: base_info_for_coords = group_dress[0]
        elif layers_to_draw: base_info_for_coords = layers_to_draw[0]
        else: continue

        # 檔名生成
        final_used_ids = [info['layer_id'] for info in layers_to_draw]
        dress_part_ids = [lid for lid in final_used_ids if lid in dress_id_set]
        other_part_ids = [lid for lid in final_used_ids if lid not in dress_id_set]
        final_sorted_ids = sorted(list(set(dress_part_ids))) + sorted(list(set(other_part_ids)))
        id_string = "_".join(map(str, final_sorted_ids))
        output_filename = f"{char_base_name}_{id_string}.png"

        # 執行緒安全的檢查與新增 Set
        should_process = False
        with set_lock:
            if output_filename not in generated_filenames_set:
                generated_filenames_set.add(output_filename)
                should_process = True
        
        if not should_process:
            continue
        
        char_output_folder = os.path.join(output_folder, char_base_name)
        if not os.path.exists(char_output_folder): os.makedirs(char_output_folder)
        output_path = os.path.join(char_output_folder, output_filename)
        
        # 提交到執行緒池
        futures.append(executor.submit(create_composite_task, layers_to_draw, base_info_for_coords, output_path, log_file, combination_context))

# --- 4. 程式主入口 ---
if __name__ == '__main__':
    LOG_FILENAME = "generation_log.txt"
    print(f"程式啟動：自動掃描檔案配對... 錯誤日誌將寫入 {LOG_FILENAME}")
    with open(LOG_FILENAME, 'w', encoding='utf-8') as log_file:
        log_file.write(f"--- 圖片生成日誌 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ---\n")
        
        txt_files = [f for f in glob.glob('*.txt') if 'sinfo' not in f.lower() and 'log' not in f.lower()]
        if not txt_files: 
            print("未在當前目錄下找到任何有效的 .txt 檔案。")
        else:
            for txt_file in txt_files:
                sinfo_file = txt_file.replace('.txt', '.sinfo.txt')
                if os.path.exists(sinfo_file):
                    process_character(txt_file, sinfo_file, log_file)
                else:
                    print(f"[錯誤] 找不到 sinfo: {sinfo_file}，跳過 {txt_file}。")
                    log_file.write(f"[錯誤] 找不到 sinfo: {sinfo_file}，跳過 {txt_file}。\n")

    print(f"\n所有處理任務已完成！請檢查 output 資料夾。")
