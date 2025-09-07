# 【最終典藏版 Ver. 33.0 - 新增 Facegroup 功能】
import pandas as pd
from PIL import Image
import os
import csv
from collections import defaultdict
import glob
from datetime import datetime
import itertools # 匯入用於產生組合的工具

# ==============================================================================
# --- 使用者設定區 ---
SPECIAL_UNDERLAY_IDS = {8320, 8321} 
PRIORITY_OVERLAY_PATHS = {'かぶせ 水着'}
# ==============================================================================


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
    try:
        with open(filepath, 'r', encoding='utf-8', newline='') as f:
            reader = csv.reader(f, delimiter='\t')
            for row in reader:
                if not row: continue
                rule_type = row[0].strip()

                if rule_type == 'dress':
                    rules.append({'type': 'dress', 'data': row})
                elif rule_type == 'face':
                    rules.append({'type': 'face', 'name': row[1].strip(), 'path': row[3].strip()})
                elif rule_type == 'facegroup':
                     if len(row) >= 2:
                        rules.append({'type': 'facegroup', 'group_name': row[1].strip()})
                elif rule_type == 'fgname':
                    if len(row) >= 2:
                        part_name = row[1].strip()
                        # 【升級】如果沒有第3個元素，路徑就設為空字串
                        part_path = row[2].strip() if len(row) >= 3 else ""
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

# --- 2. 影像合成核心邏輯 ---
def create_composite_image_relative(existing_layers_info, output_path, log_file):
    if not existing_layers_info: return False
    try:
        char_base_name = os.path.basename(os.path.dirname(output_path))
        base_info = existing_layers_info[0]
        base_x, base_y = base_info['left'], base_info['top']
        min_x, min_y, max_x, max_y = 0, 0, base_info['width'], base_info['height']
        for part_info in existing_layers_info[1:]:
            dx, dy = part_info['left'] - base_x, part_info['top'] - base_y
            min_x, min_y = min(min_x, dx), min(min_y, dy)
            max_x, max_y = max(max_x, dx + part_info['width']), max(max_y, dy + part_info['height'])
        master_canvas = Image.new("RGBA", (max_x - min_x, max_y - min_y), (0, 0, 0, 0))
        for part_info in existing_layers_info:
            part_img_path = os.path.join(char_base_name, f"{char_base_name}_{part_info['layer_id']}.png")
            part_img = Image.open(part_img_path).convert("RGBA")
            part_opacity = part_info.get('opacity', 255)
            if part_opacity < 255:
                if part_img.mode != 'RGBA': part_img = part_img.convert('RGBA')
                alpha = part_img.getchannel('A').point(lambda p: p * (part_opacity / 255.0))
                part_img.putalpha(alpha)
            paste_x, paste_y = (part_info['left'] - base_x) - min_x, (part_info['top'] - base_y) - min_y
            temp_layer = Image.new("RGBA", master_canvas.size, (0, 0, 0, 0))
            temp_layer.paste(part_img, (paste_x, paste_y))
            master_canvas = Image.alpha_composite(master_canvas, temp_layer)
        master_canvas.save(output_path)
        print(f"  ✅ 已儲存: {output_path}")
        return True
    except Exception as e:
        log_file.write(f"合成圖片錯誤: 檔案 '{os.path.basename(output_path)}' 生成失敗. 原因: {e}\n")
        print(f"  [錯誤] 合成圖片時發生未知問題: {e}")
        return False

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
    
    # --- 規則分類與處理 ---
    face_rules = defaultdict(list)
    conditional_faces = defaultdict(lambda: defaultdict(dict))
    facegroup_order = [r['group_name'] for r in sinfo_rules if r['type'] == 'facegroup']
    fgname_rules = [r for r in sinfo_rules if r['type'] == 'fgname']
    fgalias_rules = [r for r in sinfo_rules if r['type'] == 'fgalias']
    
    # --- 【最終修正】採用更穩健的三段式邏輯處理 dress 規則 ---
    all_dress_rules_raw = [r['data'] for r in sinfo_rules if r['type'] == 'dress']
    dress_rules = defaultdict(lambda: defaultdict(list))
    dress_bases = {}

    # 1. 第一段：找出所有 base
    for row in all_dress_rules_raw:
        if len(row) >= 4 and row[2].strip() == 'base':
            dress_name = row[1].strip()
            dress_bases[dress_name] = row[3].strip()

    # 2. 第二段：聚合所有 diff (包括舊格式)
    for row in all_dress_rules_raw:
        dress_name = row[1].strip()
        if len(row) >= 5 and row[2].strip() == 'diff':
            diff_id = row[3].strip()
            diff_path = row[4].strip()
            dress_rules[dress_name][diff_id].append(diff_path)
        elif len(row) >= 5 and row[2].strip() != 'base': # 兼容舊格式
            diff_id = row[3].strip()
            diff_path = row[4].strip()
            dress_rules[dress_name][diff_id].append(diff_path)
            
    # 3. 第三段：將 base 添加到對應的 diff 組中
    for dress_name, base_path in dress_bases.items():
        if dress_name in dress_rules:
            for diff_id in dress_rules[dress_name]:
                # 使用 insert 確保 base 總是在最前面
                dress_rules[dress_name][diff_id].insert(0, base_path)
    # --- dress 規則處理結束 ---


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
                else:
                    print(f"[警告] fgalias '{alias_name}' 中定義的組件 '{part_name}' 在 fgname 中找不到，已忽略此組件。")
            generated_face_rules[alias_name] = combo_paths
    
    elif facegroup_order and fgname_rules:
        print("[INFO] 未偵測到 fgalias 規則，將自動生成所有可能的表情組合...")
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
            print(f"[INFO] 已成功生成 {len(generated_face_rules)} 個 facegroup 表情組合。")

    final_face_rules = generated_face_rules if generated_face_rules else face_rules
    if not final_face_rules:
        print("[警告] 未找到任何有效的 'face' 或 'facegroup'/'fgalias' 規則。")
        return

    for dress_name, diffs in dress_rules.items():
        for diff_id, dress_paths in diffs.items():
            current_dress_key = f"{dress_name}_{diff_id}"
            print(f"\n--- 正在處理組合: {dress_name} (版本: {diff_id}) ---")
            
            priority_overlay_ids, other_dress_ids = [], []
            for p in dress_paths:
                lid = path_to_id.get(p)
                if lid is None: continue
                if p in PRIORITY_OVERLAY_PATHS: priority_overlay_ids.append(lid)
                else: other_dress_ids.append(lid)
            
            special_dress_parts = [lid for lid in other_dress_ids if lid in SPECIAL_UNDERLAY_IDS]
            normal_dress_parts = [lid for lid in other_dress_ids if lid not in SPECIAL_UNDERLAY_IDS]
            base_layers_for_comp, overlay_layers_for_comp = (normal_dress_parts[:1] + special_dress_parts + normal_dress_parts[:1], normal_dress_parts[1:]) if special_dress_parts and normal_dress_parts else (normal_dress_parts[:1], normal_dress_parts[1:])
            
            process_face_combinations(final_face_rules, base_layers_for_comp, priority_overlay_ids, overlay_layers_for_comp, path_to_id, id_to_path, layer_df, char_base_name, current_dress_key, generated_filenames_set, log_file, output_folder)
            
            for face_name, conditions in conditional_faces.items():
                if matches_condition(dress_name, condition):
                    process_face_combinations({face_name: face_paths}, base_layers_for_comp, priority_overlay_ids, overlay_layers_for_comp, path_to_id, id_to_path, layer_df, char_base_name, f"{current_dress_key}@{condition}", generated_filenames_set, log_file, output_folder)

    print(f"\n{'='*20} 角色: {char_base_name} 處理完成 {'='*20}")

def matches_condition(dress_name, condition):
    is_negated = condition.startswith('!')
    if is_negated: condition = condition[1:]
    match = dress_name.startswith(condition[:-1]) if condition.endswith('*') else (dress_name == condition)
    return not match if is_negated else match

def process_face_combinations(face_rule_dict, base_layers, priority_overlays, final_overlays, path_to_id, id_to_path, layer_df, char_base_name, dress_info_str, generated_filenames_set, log_file, output_folder):
    # 【更新】建立一個集合，用於快速識別哪些 ID 屬於 dress
    dress_id_set = {lid for lid in (base_layers + priority_overlays + final_overlays) if lid is not None}

    for face_name, face_paths in face_rule_dict.items():
        combination_context = f"組合 '{dress_info_str} + {face_name}'"
        
        face_layers, all_paths_found = [], True
        for p in face_paths:
            lid = path_to_id.get(p)
            if lid is None:
                log_file.write(f"[路徑查找失敗] {combination_context}: 部件路徑 '{p}' 在 .txt 中找不到。\n")
                all_paths_found = False
            face_layers.append(lid)
        
        if not all_paths_found: 
            print(f"  ⏭️  跳過組合: {face_name} (Sinfo 中定義的路徑錯誤)")
            continue

        sorted_face_paths = sorted(face_paths, key=lambda p: p.count('/'), reverse=True)
        sorted_face_layers = [path_to_id.get(p) for p in sorted_face_paths]
        final_layers = base_layers + sorted_face_layers + priority_overlays + final_overlays
        
        existing_layers_info, missing_parts_log = [], []
        for lid in final_layers:
            if lid is None: continue
            info_row = layer_df[layer_df['layer_id'] == lid]
            if not info_row.empty:
                info = info_row.iloc[0].to_dict()
                img_path = os.path.join(char_base_name, f"{char_base_name}_{lid}.png")
                if os.path.exists(img_path):
                    existing_layers_info.append(info)
                else:
                    missing_parts_log.append(f"'{id_to_path.get(lid, '未知')}'({lid})")
        
        if missing_parts_log:
            log_file.write(f"[組合跳過] {combination_context}: 因缺少以下必要部件檔案，此組合已跳過: {', '.join(missing_parts_log)}\n")
            print(f"  ⏭️  跳過組合: {face_name} (缺少 {len(missing_parts_log)} 個 .png 檔案)")
            continue

        if not existing_layers_info or (base_layers and existing_layers_info[0].get('layer_id') != base_layers[0]):
            if base_layers and base_layers[0] is not None:
                log_file.write(f"[基礎檔案缺失] {combination_context}: 基礎圖層 '{id_to_path.get(base_layers[0], '未知')}'({base_layers[0]}) 的圖片不存在，組合跳過。\n")
            elif not base_layers:
                 log_file.write(f"[基礎檔案缺失] {combination_context}: 服裝未定義任何基礎圖層，組合跳過。\n")
            continue
        
        # --- 【更新】使用新的排序邏輯來生成檔名 ---
        # 1. 提取所有實際會用到的圖層 ID
        final_used_ids = [info['layer_id'] for info in existing_layers_info]
        
        # 2. 將 ID 分為 'dress' 和 '其他' (表情等) 兩組
        dress_part_ids = []
        other_part_ids = []
        for lid in final_used_ids:
            if lid in dress_id_set:
                dress_part_ids.append(lid)
            else:
                other_part_ids.append(lid)
        
        # 3. 分別對兩組 ID 進行排序，然後合併，確保 dress ID 在前
        final_sorted_ids = sorted(list(set(dress_part_ids))) + sorted(list(set(other_part_ids)))
        
        # 4. 組合成字串並構成最終檔名
        id_string = "_".join(map(str, final_sorted_ids))
        output_filename = f"{char_base_name}_{id_string}.png"


        if output_filename in generated_filenames_set:
            log_file.write(f"[檔名重複] {combination_context}: 跳過已存在的檔案 '{output_filename}'。\n")
            continue
        
        char_output_folder = os.path.join(output_folder, char_base_name)
        if not os.path.exists(char_output_folder): os.makedirs(char_output_folder)
        output_path = os.path.join(char_output_folder, output_filename)
        
        if create_composite_image_relative(existing_layers_info, output_path, log_file):
            generated_filenames_set.add(output_filename)
            log_file.write(f"[成功生成] {combination_context}: 已儲存為 '{output_filename}'\n")

# --- 4. 程式主入口 ---
if __name__ == '__main__':
    LOG_FILENAME = "generation_log.txt"
    print(f"程式啟動：自動掃描檔案配對... 錯誤日誌將寫入 {LOG_FILENAME}")
    with open(LOG_FILENAME, 'w', encoding='utf-8') as log_file:
        log_file.write(f"--- 圖片生成日誌 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ---\n")
        
        txt_files = [f for f in glob.glob('*.txt') if 'sinfo' not in f.lower() and 'log' not in f.lower()]
        if not txt_files: 
            print("未在當前目錄下找到任何有效的 .txt 檔案。")
            log_file.write("未在當前目錄下找到任何有效的 .txt 檔案。\n")
        else:
            for txt_file in txt_files:
                sinfo_file = txt_file.replace('.txt', '.sinfo.txt')
                if os.path.exists(sinfo_file):
                    process_character(txt_file, sinfo_file, log_file)
                else:
                    print(f"[錯誤] 找不到對應的 sinfo 檔案: {sinfo_file}，已跳過 {txt_file}。")
                    log_file.write(f"[錯誤] 找不到對應的 sinfo 檔案: {sinfo_file}，已跳過 {txt_file}。\n")

    
    print(f"\n所有處理任務已完成！請檢查 output 資料夾以及 {LOG_FILENAME} 日誌檔案。")