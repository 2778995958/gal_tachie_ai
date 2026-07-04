# 【最終典藏完整還原版 Ver. 37.0 - Sinfo 條件與通配符完美實作版】
# 特點：保留多執行緒與Alpha合成，完美還原吉里吉里 # (姿勢)、@ (服裝)、* (模糊匹配) 與 ! (取反) 邏輯。
# 圖片堆疊順序完全依照 Sinfo 列表對照總表的先天層級逻辑 [::-1]。

import pandas as pd
from PIL import Image
import os
import csv
from collections import defaultdict
import glob
from datetime import datetime
import itertools 
import concurrent.futures
import threading

# ==============================================================================
# --- 使用者設定區 ---
MAX_WORKERS = 8  # 執行緒數量

# 【特殊圖層設定】
SPECIAL_UNDERLAY_IDS = {8320, 8321} 
PRIORITY_OVERLAY_PATHS = {'かぶせ 水着', '鬼面'} 
# ==============================================================================

log_lock = threading.Lock()
set_lock = threading.Lock()

# --- 1. 條件判定核心輔助函數 (還原 TJS2 foreMatch 邏輯) ---
def matches_single_condition(current_val, cond_val):
    """檢查單個條件是否符合，支援 ! 取反與 * 字首模糊匹配"""
    is_negated = cond_val.startswith('!')
    if is_negated: 
        cond_val = cond_val[1:]
    
    if cond_val.endswith('*'):
        prefix = cond_val[:-1]
        match = current_val.startswith(prefix)
    else:
        match = (current_val == cond_val)
        
    return not match if is_negated else match

def evaluate_face_condition(condition_str, dress_name, diff_id):
    """解析並評估複合條件字串，例如 '#手胸@パジャマ１' 或 '#手*'"""
    if not condition_str: 
        return True
        
    pose_cond = None
    dress_cond = None
    
    # 拆解 # (姿勢) 與 @ (服裝)
    if '#' in condition_str and '@' in condition_str:
        hash_idx = condition_str.index('#')
        at_idx = condition_str.index('@')
        if hash_idx < at_idx:
            pose_cond = condition_str[hash_idx+1:at_idx].strip()
            dress_cond = condition_str[at_idx+1:].strip()
        else:
            dress_cond = condition_str[at_idx+1:hash_idx].strip()
            pose_cond = condition_str[hash_idx+1:].strip()
    elif '#' in condition_str:
        pose_cond = condition_str[condition_str.index('#')+1:].strip()
    elif '@' in condition_str:
        dress_cond = condition_str[condition_str.index('@')+1:].strip()
        
    # 驗證姿勢條件
    if pose_cond and not matches_single_condition(diff_id, pose_cond): 
        return False
    # 驗證服裝條件
    if dress_cond and not matches_single_condition(dress_name, dress_cond): 
        return False
        
    return True

# --- 2. 資料讀取與預處理 ---
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
        return df
    except Exception as e:
        print(f"[錯誤] 處理 '{filepath}' 時發生問題: {e}")
        return None

def load_sinfo_data_manual(filepath):
    print(f"[INFO] 正在解析 '{filepath}'...")
    rules = []
    def clean_path(p): return "/".join(component.strip() for component in p.split('/'))
    try:
        with open(filepath, 'r', encoding='utf-8', newline='') as f:
            reader = csv.reader(f, delimiter='\t')
            for row in reader:
                if not row: continue
                rule_type = row[0].strip()
                if rule_type == 'dress':
                    rules.append({'type': 'dress', 'data': [item.strip() for item in row]})
                elif rule_type == 'face':
                    rules.append({'type': 'face', 'name': row[1].strip(), 'path': clean_path(row[3])})
                elif rule_type == 'facegroup':
                     if len(row) >= 2: rules.append({'type': 'facegroup', 'group_name': row[1].strip()})
                elif rule_type == 'fgname':
                    if len(row) >= 2: rules.append({'type': 'fgname', 'name': row[1].strip(), 'path': clean_path(row[2]) if len(row) >= 3 else ""})
                elif rule_type == 'fgalias':
                    if len(row) >= 3: rules.append({'type': 'fgalias', 'name': row[1].strip(), 'parts': [p.strip() for p in row[2:]]})
        return rules
    except Exception as e:
        print(f"[錯誤] 手動解析 '{filepath}' 時發生問題: {e}")
        return []

# --- 3. 影像合成核心 (Worker) ---
def create_composite_task(layers_to_draw, base_info, output_path, log_file, combination_context):
    if not layers_to_draw: return
    try:
        char_base_name = os.path.basename(os.path.dirname(output_path))
        base_x, base_y = base_info['left'], base_info['top']
        
        first_part_info = layers_to_draw[0]
        min_x = first_part_info['left'] - base_x
        min_y = first_part_info['top'] - base_y
        max_x = min_x + first_part_info['width']
        max_y = min_y + first_part_info['height']

        for part_info in layers_to_draw[1:]:
            # === 💡 程式夥伴優化：如果是空資料夾或錨點(寬高為0)，直接跳過，不影響畫布大小 ===
            if part_info['width'] == 0 or part_info['height'] == 0:
                continue
            # ====================================================================
            dx, dy = part_info['left'] - base_x, part_info['top'] - base_y
            min_x, min_y = min(min_x, dx), min(min_y, dy)
            max_x, max_y = max(max_x, dx + part_info['width']), max(max_y, dy + part_info['height'])
        
        canvas_width = max_x - min_x
        canvas_height = max_y - min_y
        master_canvas = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))

        for part_info in layers_to_draw:
            part_img_path = os.path.join(char_base_name, f"{char_base_name}_{part_info['layer_id']}.png")
            try:
                part_img = Image.open(part_img_path).convert("RGBA")
            except FileNotFoundError: continue

            part_opacity = part_info.get('opacity', 255)
            if part_opacity < 255:
                alpha = part_img.getchannel('A').point(lambda p: p * (part_opacity / 255.0))
                part_img.putalpha(alpha)

            paste_x = (part_info['left'] - base_x) - min_x
            paste_y = (part_info['top'] - base_y) - min_y
            
            layer_canvas = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))
            layer_canvas.paste(part_img, (paste_x, paste_y))
            master_canvas = Image.alpha_composite(master_canvas, layer_canvas)

        master_canvas.save(output_path)
        with log_lock:
            log_file.write(f"[成功生成] {combination_context}: '{os.path.basename(output_path)}'\n")
            
    except Exception as e:
        with log_lock:
            print(f"  ❌ [錯誤] {os.path.basename(output_path)}: {e}")
            log_file.write(f"合成圖片錯誤: {e}\n")

# --- 4. 邏輯控制 ---
def process_character(txt_path, sinfo_path, log_file):
    char_base_name = os.path.basename(txt_path).replace('.txt', '')
    output_folder = 'output'
    log_file.write(f"\n===== 開始檢查角色: {char_base_name} =====\n")
    print(f"\n{'='*20} 開始處理角色: {char_base_name} {'='*20}")

    layer_df = load_layer_data_with_paths(txt_path)
    if layer_df is None: return

    sinfo_rules = load_sinfo_data_manual(sinfo_path)
    if not sinfo_rules: return

    char_output_folder = os.path.join(output_folder, char_base_name)
    generated_filenames_set = set()
    if os.path.exists(char_output_folder):
        existing_files = glob.glob(os.path.join(char_output_folder, '*.png'))
        generated_filenames_set.update(os.path.basename(f) for f in existing_files)

    path_to_id = pd.Series(layer_df.layer_id.values, index=layer_df.full_path).to_dict()
    id_to_path = {v: k for k, v in path_to_id.items()}
    
    # 規則解析
    face_rules = defaultdict(list)
    conditional_faces = defaultdict(list)  # 修改：改為單層 list 儲存 (condition_str, path)
    facegroup_order = [r['group_name'] for r in sinfo_rules if r['type'] == 'facegroup']
    fgname_rules = [r for r in sinfo_rules if r['type'] == 'fgname']
    fgalias_rules = [r for r in sinfo_rules if r['type'] == 'fgalias']
    
    all_dress_rules_raw = [r['data'] for r in sinfo_rules if r['type'] == 'dress']
    dress_rules = defaultdict(lambda: defaultdict(list))
    dress_bases = {}

    for row in all_dress_rules_raw:
        if len(row) >= 4 and row[2].strip() == 'base': dress_bases[row[1].strip()] = row[3].strip()

    for row in all_dress_rules_raw:
        dress_name = row[1].strip()
        diff_id = row[3].strip() if len(row) >= 5 else "unknown"
        diff_path = row[4].strip() if len(row) >= 5 else ""
        if diff_path: dress_rules[dress_name][diff_id].append(diff_path)
            
    for dress_name, base_path in dress_bases.items():
        if dress_name in dress_rules:
            for diff_id in dress_rules[dress_name]:
                dress_rules[dress_name][diff_id].insert(0, base_path)

    # --- 【核心修正 1】分離表情名稱與 ＃、＠ 條件 ---
    for rule in [r for r in sinfo_rules if r['type'] == 'face']:
        raw_name = rule['name']
        cond_idx = len(raw_name)
        if '#' in raw_name: cond_idx = min(cond_idx, raw_name.index('#'))
        if '@' in raw_name: cond_idx = min(cond_idx, raw_name.index('@'))
        
        face_name = raw_name[:cond_idx].strip()
        condition_str = raw_name[cond_idx:].strip()
        
        if condition_str:
            conditional_faces[face_name].append((condition_str, rule['path']))
        else:
            face_rules[face_name].append(rule['path'])

    generated_face_rules = {}
    fgname_to_paths_map = defaultdict(list)
    for rule in fgname_rules:
        fgname_to_paths_map[rule['name']].append(rule['path'])

    if fgalias_rules:
        for alias_rule in fgalias_rules:
            generated_face_rules[alias_rule['name']] = []
            for part_name in alias_rule['parts']:
                if part_name in fgname_to_paths_map:
                    generated_face_rules[alias_rule['name']].extend([p for p in fgname_to_paths_map[part_name] if p and p.lower() != 'dummy'])
    
    elif facegroup_order and fgname_rules:
        part_lists_in_order = []
        for group in facegroup_order:
            options = [(name, paths) for name, paths in fgname_to_paths_map.items() if name.startswith(group)]
            if options: part_lists_in_order.append(options)
        
        if part_lists_in_order:
            for combo in itertools.product(*part_lists_in_order):
                combo_name = "_".join(c[0] for c in combo)
                generated_face_rules[combo_name] = [p for c in combo for p in c[1] if p]

    final_face_rules = generated_face_rules if generated_face_rules else face_rules
    if not final_face_rules: return

    print(f"[INFO] 啟動多執行緒處理，使用 {MAX_WORKERS} 個 Worker...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []
        for dress_name, diffs in dress_rules.items():
            for diff_id, dress_paths in diffs.items():
                current_dress_key = f"{dress_name}_{diff_id}"
                
                priority_overlay_ids, other_dress_ids = [], []
                for p in dress_paths:
                    lid = path_to_id.get(p)
                    if lid is None: continue
                    if p in PRIORITY_OVERLAY_PATHS: priority_overlay_ids.append(lid)
                    else: other_dress_ids.append(lid)
                
                special_dress_parts = [lid for lid in other_dress_ids if lid in SPECIAL_UNDERLAY_IDS]
                normal_dress_parts = [lid for lid in other_dress_ids if lid not in SPECIAL_UNDERLAY_IDS]
                
                base_layers_for_comp = normal_dress_parts[:1] + special_dress_parts + normal_dress_parts[:1] if special_dress_parts and normal_dress_parts else normal_dress_parts[:1]
                overlay_layers_for_comp = normal_dress_parts[1:]
                
                # 提交普通/組裝表情
                submit_face_combinations(executor, futures, final_face_rules, base_layers_for_comp, priority_overlay_ids, overlay_layers_for_comp, path_to_id, layer_df, char_base_name, current_dress_key, generated_filenames_set, log_file, output_folder)
                
                # --- 【核心修正 2】精確過濾並提交成立的條件表情 ---
                current_active_conditional_faces = defaultdict(list)
                for face_name, rules_list in conditional_faces.items():
                    for condition_str, path in rules_list:
                        if evaluate_face_condition(condition_str, dress_name, diff_id):
                            current_active_conditional_faces[face_name].append(path)
                
                for face_name, face_paths in current_active_conditional_faces.items():
                    submit_face_combinations(executor, futures, {face_name: face_paths}, base_layers_for_comp, priority_overlay_ids, overlay_layers_for_comp, path_to_id, layer_df, char_base_name, f"{current_dress_key}_cond", generated_filenames_set, log_file, output_folder)
        
        concurrent.futures.wait(futures)
    print(f"\n{'='*20} 角色: {char_base_name} 處理完成 {'='*20}")

# --- 核心排序與組合 ---
def submit_face_combinations(executor, futures, face_rule_dict, base_layers, priority_overlays, final_overlays, path_to_id, layer_df, char_base_name, dress_info_str, generated_filenames_set, log_file, output_folder):
    
    dress_id_set = set(base_layers + priority_overlays + final_overlays)
    
    # 收集所有需要的 ID（包含支援 * 通配符的擴展）
    all_needed_ids_set = dress_id_set.copy()
    for face_paths in face_rule_dict.values():
         for p in face_paths:
             if '*' in p:
                 prefix = p.replace('*', '')
                 for full_path, lid in path_to_id.items():
                     if full_path.startswith(prefix): all_needed_ids_set.add(lid)
             else:
                 lid = path_to_id.get(p)
                 if lid: all_needed_ids_set.add(lid)

    filtered_df = layer_df[layer_df['layer_id'].isin(all_needed_ids_set)].copy()
    layer_info_map = filtered_df.set_index('layer_id').to_dict('index')

    for face_name, face_paths in face_rule_dict.items():
        combination_context = f"組合 '{dress_info_str} + {face_name}'"
        
        face_layers_ids = []
        all_paths_found = True
        
        # --- 【核心修正 3】支援路徑字首 * 模糊匹配的多圖層批量抓取 ---
        for p in face_paths:
            if '*' in p:
                prefix = p.replace('*', '')
                matched_lids = [lid for full_path, lid in path_to_id.items() if full_path.startswith(prefix)]
                if matched_lids:
                    face_layers_ids.extend(matched_lids)
                else:
                    all_paths_found = False
            else:
                lid = path_to_id.get(p)
                if lid is None: all_paths_found = False
                else: face_layers_ids.append(lid)
        
        if not all_paths_found: continue

        # --- 【核心修正 4】對照總表先天層級順序，並加上 [::-1] 倒序（確保 ほほ 在底，眉 在面） ---
        face_id_set = set(face_layers_ids)
        sorted_face_layers_ids = [int(lid) for lid in layer_df['layer_id'].values if lid in face_id_set][::-1]
        
        # 最終三明治拼接順序：身體(底) -> 依總表排好的五官 -> 置頂面具配件 -> 其餘服裝(面)
        ordered_ids = base_layers + sorted_face_layers_ids + priority_overlays + final_overlays
        
        layers_to_draw = []
        for lid in ordered_ids:
            if lid in layer_info_map:
                info = layer_info_map[lid].copy()
                info['layer_id'] = lid
                layers_to_draw.append(info)
        
        if not layers_to_draw: continue
        
        base_info_for_coords = layers_to_draw[0]

        final_used_ids = [info['layer_id'] for info in layers_to_draw]
        dress_part_ids = [lid for lid in final_used_ids if lid in dress_id_set]
        other_part_ids = [lid for lid in final_used_ids if lid not in dress_id_set]
        final_sorted_ids = sorted(list(set(dress_part_ids))) + sorted(list(set(other_part_ids)))
        id_string = "_".join(map(str, final_sorted_ids))
        output_filename = f"{char_base_name}_{id_string}.png"

        should_process = False
        with set_lock:
            if output_filename not in generated_filenames_set:
                generated_filenames_set.add(output_filename)
                should_process = True
        
        if not should_process: continue
        
        char_output_folder = os.path.join(output_folder, char_base_name)
        if not os.path.exists(char_output_folder): os.makedirs(char_output_folder)
        output_path = os.path.join(char_output_folder, output_filename)
        
        futures.append(executor.submit(create_composite_task, layers_to_draw, base_info_for_coords, output_path, log_file, combination_context))

if __name__ == '__main__':
    LOG_FILENAME = "generation_log.txt"
    print(f"程式啟動... Log: {LOG_FILENAME}")
    with open(LOG_FILENAME, 'w', encoding='utf-8') as log_file:
        log_file.write(f"--- Start ({datetime.now()}) ---\n")
        txt_files = [f for f in glob.glob('*.txt') if 'sinfo' not in f.lower() and 'log' not in f.lower()]
        for txt_file in txt_files:
            sinfo_file = txt_file.replace('.txt', '.sinfo.txt')
            if os.path.exists(sinfo_file): process_character(txt_file, sinfo_file, log_file)
    print(f"\n完成！")