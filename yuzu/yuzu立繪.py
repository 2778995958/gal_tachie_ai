# 【最終典藏版 Ver. 32.1 - 錯誤修正版】
import pandas as pd
from PIL import Image
import os
import csv
from collections import defaultdict
import glob
from datetime import datetime

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
                # <<< 修改部分：在這裡就將名稱中的 / 替換成 _，確保路徑格式一致
                if info['name']: path_parts.append(info['name'].replace('/', '_'))
                parent_id = info['group_layer_id']
                if parent_id == 0: break
                current_id = parent_id
            # <<< 修改部分：路徑組合符號也統一用 _，避免混淆
            paths[layer_id] = "_".join(reversed(path_parts))
        df['full_path'] = df['layer_id'].map(paths)
        # <<< 修改部分：處理沒有父層級的圖層名稱
        df['full_path'] = df['full_path'].fillna(df['name'].str.replace('/', '_'))
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
                if rule_type == 'dress' and len(row) >= 5:
                    # <<< 修改部分：在讀取規則時，也將路徑中的 / 替換成 _
                    rule_path = row[4].strip().replace('/', '_')
                    rules.append({'type': 'dress', 'name': row[1].strip(), 'id': row[3].strip(), 'path': rule_path})
                elif rule_type == 'face' and len(row) >= 4:
                    # <<< 修改部分：在讀取規則時，也將路徑中的 / 替換成 _
                    rule_path = row[3].strip().replace('/', '_')
                    rules.append({'type': 'face', 'name': row[1].strip(), 'path': rule_path})
        print(f"[INFO] '{filepath}' 解析成功，載入 {len(rules)} 條規則。")
        return rules
    except Exception as e:
        print(f"[錯誤] 手動解析 '{filepath}' 時發生問題: {e}")
        return []

# --- 2. 影像合成核心邏輯 ---
def create_composite_image_relative(existing_layers_info, output_path, log_file):
    # ... (此函式保持不變)
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
    """【新功能】檢查所有在 .txt 中定義的圖層，記錄缺失的 .png 檔案"""
    print(f"[INFO] 正在進行素材完整性檢查...")
    log_file.write(f"\n--- 素材檔案完整性檢查 ---\n")
    missing_count = 0
    for _, row in layer_df.iterrows():
        # 如果圖層沒有寬高，通常它只是一個資料夾，不需要有對應圖片
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

    # --- 執行素材完整性檢查 ---
    log_missing_assets(layer_df, char_base_name, log_file)

    sinfo_rules = load_sinfo_data_manual(sinfo_path)
    if not sinfo_rules: return

    # ... (後續的處理邏輯與之前版本相同)
    char_output_folder = os.path.join(output_folder, char_base_name)
    generated_filenames_set = set()
    if os.path.exists(char_output_folder):
        print(f"[INFO] 正在掃描已存在的檔案於 '{char_output_folder}'...")
        existing_files = glob.glob(os.path.join(char_output_folder, '*.png'))
        generated_filenames_set.update(os.path.basename(f) for f in existing_files)
        print(f"[INFO] 掃描完成，發現 {len(generated_filenames_set)} 個已生成檔案。")

    path_to_id = pd.Series(layer_df.layer_id.values, index=layer_df.full_path).to_dict()
    id_to_path = {v: k for k, v in path_to_id.items()}
    
    # <<< 修改部分：刪除了 dress_fingerprint_map 變數的初始化

    dress_rules, face_rules, conditional_faces = defaultdict(lambda: defaultdict(list)), defaultdict(list), defaultdict(lambda: defaultdict(dict))
    for rule in sinfo_rules:
        if rule['type'] == 'dress':
            dress_rules[rule['name']][rule['id']].append(rule['path'])
        elif rule['type'] == 'face':
            if '@' in rule['name']:
                face_name, condition = rule['name'].split('@', 1)
                if condition not in conditional_faces[face_name]: conditional_faces[face_name][condition] = []
                conditional_faces[face_name][condition].append(rule['path'])
            else:
                face_rules[rule['name']].append(rule['path'])
    
    for dress_name, diffs in dress_rules.items():
        for diff_id, dress_paths in diffs.items():
            current_dress_key = f"{dress_name}_{diff_id}"
            print(f"\n--- 正在處理組合: {dress_name} (版本: {diff_id}) ---")
            
            base_dress_layers_ids = [path_to_id.get(p) for p in dress_paths]
            valid_ids = frozenset(lid for lid in base_dress_layers_ids if lid is not None)
            if not valid_ids: 
                log_file.write(f"[服裝定義失敗] '{current_dress_key}' 的所有部件在 .txt 中都找不到，已跳過。\n")
                continue

            # <<< 修改部分：將整個檢查服裝定義重複的 if/else 區塊刪除
            # (原本在這裡有一段 if valid_ids in dress_fingerprint_map: ... 的程式碼)
            
            priority_overlay_ids, other_dress_ids = [], []
            for p in dress_paths:
                lid = path_to_id.get(p)
                if p in PRIORITY_OVERLAY_PATHS: priority_overlay_ids.append(lid)
                else: other_dress_ids.append(lid)
            
            special_dress_parts = [lid for lid in other_dress_ids if lid in SPECIAL_UNDERLAY_IDS]
            normal_dress_parts = [lid for lid in other_dress_ids if lid not in SPECIAL_UNDERLAY_IDS]
            base_layers_for_comp, overlay_layers_for_comp = (normal_dress_parts[:1] + special_dress_parts + normal_dress_parts[:1], normal_dress_parts[1:]) if special_dress_parts and normal_dress_parts else (normal_dress_parts[:1], normal_dress_parts[1:])
            
            process_face_combinations(face_rules, base_layers_for_comp, priority_overlay_ids, overlay_layers_for_comp, path_to_id, id_to_path, layer_df, char_base_name, current_dress_key, generated_filenames_set, log_file, output_folder)
            for face_name, conditions in conditional_faces.items():
                for condition, face_paths in conditions.items():
                    if matches_condition(dress_name, condition):
                        process_face_combinations({face_name: face_paths}, base_layers_for_comp, priority_overlay_ids, overlay_layers_for_comp, path_to_id, id_to_path, layer_df, char_base_name, f"{current_dress_key}@{condition}", generated_filenames_set, log_file, output_folder)

    print(f"\n{'='*20} 角色: {char_base_name} 處理完成 {'='*20}")

def matches_condition(dress_name, condition):
    is_negated = condition.startswith('!')
    if is_negated: condition = condition[1:]
    match = dress_name.startswith(condition[:-1]) if condition.endswith('*') else (dress_name == condition)
    return not match if is_negated else match

def process_face_combinations(face_rule_dict, base_layers, priority_overlays, final_overlays, path_to_id, id_to_path, layer_df, char_base_name, dress_info_str, generated_filenames_set, log_file, output_folder):
    for face_name, face_paths in face_rule_dict.items():
        combination_context = f"組合 '{dress_info_str} + {face_name}'"
        
        face_layers, all_paths_found = [], True
        for p in face_paths:
            # <<< 修改部分：在查找路徑前，也將路徑中的 / 替換成 _
            lookup_path = p.replace('/', '_')
            lid = path_to_id.get(lookup_path)
            if lid is None:
                log_file.write(f"[路徑查找失敗] {combination_context}: 部件路徑 '{lookup_path}' 在 .txt 中找不到。\n")
                all_paths_found = False
            face_layers.append(lid)
        
        if not all_paths_found: continue

        # <<< 修改部分：排序時也對路徑進行格式統一化
        sorted_face_paths = sorted(face_paths, key=lambda p: p.replace('/', '_').count('_'), reverse=True)
        sorted_face_layers = [path_to_id.get(p.replace('/', '_')) for p in sorted_face_paths]
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
        
        if not existing_layers_info or existing_layers_info[0].get('layer_id') != final_layers[0]:
            if final_layers and final_layers[0] is not None:
                log_file.write(f"[基礎檔案缺失] {combination_context}: 基礎圖層 '{id_to_path.get(final_layers[0], '未知')}'({final_layers[0]}) 的圖片不存在，組合跳過。\n")
            continue
        
        final_used_ids = [info['layer_id'] for info in existing_layers_info]
        id_string = "_".join(map(str, final_used_ids))
        output_filename = f"{char_base_name}_{id_string}.png"

        if output_filename in generated_filenames_set:
            log_file.write(f"[檔名重複] {combination_context}: 跳過已存在的檔案 '{output_filename}'。\n")
            continue
        
        if missing_parts_log:
            log_file.write(f"[部件缺失] {combination_context}: 正在生成，但跳過了不存在的部件: {', '.join(missing_parts_log)}\n")
        
        char_output_folder = os.path.join(output_folder, char_base_name)
        if not os.path.exists(char_output_folder): os.makedirs(char_output_folder)
        output_path = os.path.join(char_output_folder, output_filename)
        
        if create_composite_image_relative(existing_layers_info, output_path, log_file):
            generated_filenames_set.add(output_filename)
            log_file.write(f"[成功生成] {combination_context}: 已儲存為 '{output_filename}'\n")

# --- 4. 程式主入口 ---
if __name__ == '__main__':
    LOG_FILENAME = "generation_log.txt" # <<< 修改部分：更改日誌檔案名，避免與舊日誌混淆
    print(f"程式啟動：自動掃描檔案配對... 錯誤日誌將寫入 {LOG_FILENAME}")
    with open(LOG_FILENAME, 'w', encoding='utf-8') as log_file:
        log_file.write(f"--- 圖片生成日誌 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ---\n")
        
        txt_files = [f for f in glob.glob('*.txt') if 'sinfo' not in f.lower() and 'log' not in f.lower()]
        if not txt_files: 
            print("未在當前目錄下找到任何有效的 .txt 檔案。")
            log_file.write("未在當前目錄下找到任何有效的 .txt 檔案。\n")
        else:
            for txt_file in txt_files:
                process_character(txt_file, txt_file.replace('.txt', '.sinfo.txt'), log_file)
    
    print(f"\n所有處理任務已完成！請檢查 output 資料夾以及 {LOG_FILENAME} 日誌檔案。")
