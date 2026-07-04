# ==============================================================================
# 【終極大一統智慧全局 Z-Order 版 Ver. 47.0 - 官方表情條件覆蓋還原版】
# ==============================================================================
# 特點：
# 1. 完美還原官方表情覆蓋機制：滿足特定姿勢條件(如 #手顔)時，特殊表情直接替換/覆蓋基礎表情，根治雙手沒放臉穿幫。
# 2. 智慧缺圖控管策略（MISSING_IMG_POLICY）：支援 0(缺圖都合), 1(衣服缺不合), 2(不論衣服表情缺一不可)，消滅日誌雙標。
# 3. 智慧型名稱後退降級搜索：完美修復「只有臉沒身體」問題，路徑不對時自動降級匹配純圖層名。
# 4. 5重圖片格式智慧相容：自動碰撞 {ID}.png, {名稱}.png 及其前綴組合，確保素材 100% 載入。
# 5. 100% 還原官方全局 Z-Order 渲染鐵律：所有啟用的圖層完全對照總表先天順序進行全局倒序 [::-1] 疊加。
# 6. 6手交叉配對引擎：智慧相容 *.pbd.txt, *.pbd, *.txt 與 *.sinfo.txt, *.sinfo, *_info.txt。
# ==============================================================================

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
import re

# ==============================================================================
# --- 使用者設定區 ---
MAX_WORKERS = 12  # 多執行緒線程數量
PRIORITY_OVERLAY_PATHS = {'かぶせ 水着123', '鬼面123', 'かぶせ 水着123'} 

# 【缺圖控管策略設定位】
# 0 = 缺圖都合（殘缺輸出）
# 1 = 身體/服裝(dress)有缺絕對不合，只有臉部表情(face)缺仍可合成 (推薦)
# 2 = 嚴格控管，無論是衣服還是表情，組合中缺了任何一張圖就絕對不合成
MISSING_IMG_POLICY = 1  
# ==============================================================================

log_lock = threading.Lock()
set_lock = threading.Lock()

# --- 1. 智慧型多重編碼與啟發式特徵校驗核心 ---
def read_file_with_smart_encoding(filepath):
    """智慧型編碼探測鏈：依序碰撞最可能的文字編碼，並進行啟發式特徵校驗，防止偽解碼攔截"""
    encodings = ['utf-8-sig', 'utf-8', 'utf-16', 'utf-16-le', 'utf-16-be', 'shift_jis', 'cp932', 'euc-jp']
    
    for enc in encodings:
        try:
            with open(filepath, 'rb') as f:
                raw_bytes = f.read()
            
            content = raw_bytes.decode(enc)
            
            if enc in ['shift_jis', 'cp932', 'euc-jp']:
                if '\x00' in content:
                    continue
                if len(content) > 0:
                    has_tab = '\t' in content
                    has_keyword = any(k in content for k in ['dress', 'face', 'layer_type', '#', 'bs_'])
                    if not (has_tab or has_keyword):
                        continue 
                        
            return content.splitlines(), enc
        except (UnicodeDecodeError, LookupError):
            continue
    
    print(f"  ⚠️ [警告] '{filepath}' 無法用常規日文或UTF編碼解析，將使用強制容錯讀取。")
    with open(filepath, 'r', encoding='utf-8', errors='backslashreplace', newline='') as f:
        return f.read().splitlines(), 'utf-8_fallback_errors'

# --- 2. 條件判定核心輔助函數 (完美還原官方 TJS foreMatch 邏輯) ---
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
        
    if pose_cond and not matches_single_condition(diff_id, pose_cond): 
        return False
    if dress_cond and not matches_single_condition(dress_name, dress_cond): 
        return False
        
    return True

# --- 3. 資料讀取與路徑標準化預處理 ---
def normalize_path_string(path_str):
    """將路徑底線化、移除任何空白，確保跨平台查找 100% 精確"""
    return path_str.replace('/', '_').replace(' ', '').replace(' ', '')

def load_layer_data_with_paths(filepath):
    print(f"[INFO] 正在解析配置總表 '{filepath}'...")
    parsed_data = []
    
    lines, detected_enc = read_file_with_smart_encoding(filepath)
    print(f"[INFO] '{filepath}' 經特徵校驗確定編碼為: {detected_enc}")
    
    try:
        if len(lines) < 2: return None
        reader = csv.reader(lines[2:], delimiter='\t')
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
        
        id_to_info = df.set_index('layer_id').to_dict('index')
        paths_slash, paths_underscore = {}, {}
        for layer_id in df['layer_id']:
            current_id, path_parts, visited_ids = layer_id, [], set()
            while current_id in id_to_info and current_id not in visited_ids:
                visited_ids.add(current_id)
                info = id_to_info[current_id]
                if info['name']: path_parts.append(info['name'])
                parent_id = info['group_layer_id']
                if parent_id == 0: break
                current_id = parent_id
            
            paths_slash[layer_id] = "/".join(reversed(path_parts))
            paths_underscore[layer_id] = "_".join(normalize_path_string(p) for p in reversed(path_parts))
            
        df['full_path_slash'] = df['layer_id'].map(paths_slash).fillna(df['name'])
        df['full_path_underscore'] = df['layer_id'].map(paths_underscore).fillna(df['name'].apply(normalize_path_string))
        return df
    except Exception as e:
        print(f"[錯誤] 處理配置總表 '{filepath}' 時發生問題: {e}")
        return None

def load_sinfo_data_manual(filepath):
    print(f"[INFO] 正在解析規則定義 '{filepath}'...")
    rules = []
    def clean_path(p): return "/".join(component.strip() for component in p.split('/'))
    
    lines, detected_enc = read_file_with_smart_encoding(filepath)
    print(f"[INFO] '{filepath}' 經特徵校驗確定編碼為: {detected_enc}")
    
    try:
        reader = csv.reader(lines, delimiter='\t')
        for row in reader:
            if not row or row[0].strip().startswith('#'): continue
            rule_type = row[0].strip()
            if rule_type == 'dress':
                rules.append({'type': 'dress', 'data': [item.strip() for item in row]})
            elif rule_type == 'face':
                path_idx = 3 if len(row) >= 4 and row[2].strip() == 'base' else 2
                rule_path = clean_path(row[path_idx]) if len(row) > path_idx else ""
                rules.append({'type': 'face', 'name': row[1].strip(), 'path': rule_path})
            elif rule_type == 'facegroup' and len(row) >= 2:
                 rules.append({'type': 'facegroup', 'group_name': row[1].strip()})
            elif rule_type == 'fgname' and len(row) >= 2:
                rules.append({'type': 'fgname', 'name': row[1].strip(), 'path': clean_path(row[2]) if len(row) >= 3 else ""})
            elif rule_type == 'fgalias' and len(row) >= 3:
                rules.append({'type': 'fgalias', 'name': row[1].strip(), 'parts': [p.strip() for p in row[2:]]})
        return rules
    except Exception as e:
        print(f"[錯誤] 解析規則定義 '{filepath}' 時發生問題: {e}")
        return []

# --- 4. 影像合成核心 (工作線程) ---
def create_composite_task(layers_to_draw, base_info, output_path, log_file, combination_context, img_folders, dress_id_set):
    if not layers_to_draw: return
    try:
        base_x, base_y = base_info['left'], base_info['top']
        
        # 1. 探測所有實體檔案的完整性，並標記缺失歸屬
        missing_dress = False
        missing_face = False
        loaded_layers = [] 
        
        for part_info in layers_to_draw:
            lid = part_info['layer_id']
            lname = part_info.get('name', '')
            
            if part_info['width'] == 0 or part_info['height'] == 0:
                continue
                
            part_img = None
            possible_paths = []
            for folder in img_folders:
                possible_paths.append(os.path.join(folder, f"{folder}_{lid}.png"))
                possible_paths.append(os.path.join(folder, f"{lid}.png"))
                if lname:
                    possible_paths.append(os.path.join(folder, f"{folder}_{lname}.png"))
                    possible_paths.append(os.path.join(folder, f"{lname}.png"))
                    possible_paths.append(os.path.join(folder, f"{folder}_{normalize_path_string(lname)}.png"))
            
            for img_p in possible_paths:
                if os.path.exists(img_p):
                    part_img = Image.open(img_p).convert("RGBA")
                    break
                    
            if part_img is None: 
                if lid in dress_id_set: missing_dress = True
                else: missing_face = True
                
                with log_lock:
                    log_file.write(f"[圖層缺失] {combination_context}: 找不到圖層 ID {lid} ({lname}) 的實體圖片。\n")
            else:
                loaded_layers.append((part_info, part_img))

        # 2. 智慧型控管攔截
        if MISSING_IMG_POLICY == 1 and missing_dress:
            with log_lock:
                log_file.write(f"[原則跳過] {combination_context}: 衣服/身體圖層有缺，依控管策略(1)阻斷合成。\n")
            return
        elif MISSING_IMG_POLICY == 2 and (missing_dress or missing_face):
            with log_lock:
                log_file.write(f"[原則跳過] {combination_context}: 組合中存有缺件，依控管策略(2)阻斷合成。\n")
            return

        if not loaded_layers: return

        # 3. 計算最精確畫布邊界
        first_part = loaded_layers[0][0]
        min_x, min_y = first_part['left'] - base_x, first_part['top'] - base_y
        max_x, max_y = min_x + first_part['width'], min_y + first_part['height']

        for part_info, _ in loaded_layers[1:]:
            dx, dy = part_info['left'] - base_x, part_info['top'] - base_y
            min_x, min_y = min(min_x, dx), min(min_y, dy)
            max_x, max_y = max(max_x, dx + part_info['width']), max(max_y, dy + part_info['height'])
        
        canvas_width, canvas_height = max_x - min_x, max_y - min_y
        master_canvas = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))

        # 4. 進行實際的透明度堆疊貼圖
        for part_info, part_img in loaded_layers:
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

# --- 5. 邏輯控制中心 ---
def process_character(pbd_txt_path, sinfo_path, log_file):
    pbd_base_name = os.path.basename(pbd_txt_path)
    for ext in ['.pbd.txt', '.pbd', '.txt']:
        if pbd_base_name.lower().endswith(ext):
            pbd_base_name = pbd_base_name[:-len(ext)]
            break
            
    stripped_base_name = re.sub(r'_\d+$', '', pbd_base_name) 
    
    output_folder = 'output'
    log_file.write(f"\n===== 開始檢查立繪配置: {pbd_base_name} =====\n")
    print(f"\n{'='*20} 開始處理: {pbd_base_name} {'='*20}")

    layer_df = load_layer_data_with_paths(pbd_txt_path)
    if layer_df is None: return

    sinfo_rules = load_sinfo_data_manual(sinfo_path)
    if not sinfo_rules: return

    char_output_folder = os.path.join(output_folder, pbd_base_name)
    generated_filenames_set = set()
    if os.path.exists(char_output_folder):
        existing_files = glob.glob(os.path.join(char_output_folder, '*.png'))
        generated_filenames_set.update(os.path.basename(f) for f in existing_files)

    path_to_id = {}
    for _, r in layer_df.iterrows():
        path_to_id[r['full_path_slash']] = r['layer_id']
        path_to_id[r['full_path_underscore']] = r['layer_id']
        path_to_id[normalize_path_string(r['full_path_slash'])] = r['layer_id']
        path_to_id[normalize_path_string(r['name'])] = r['layer_id']

    img_folders = [pbd_base_name, stripped_base_name]

    face_rules = defaultdict(list)
    conditional_faces = defaultdict(list)
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
            for diff_id in dress_rules[dress_name]: dress_rules[dress_name][diff_id].insert(0, base_path)

    for rule in [r for r in sinfo_rules if r['type'] == 'face']:
        raw_name = rule['name']
        cond_idx = len(raw_name)
        if '#' in raw_name: cond_idx = min(cond_idx, raw_name.index('#'))
        if '@' in raw_name: cond_idx = min(cond_idx, raw_name.index('@'))
        
        face_name = raw_name[:cond_idx].strip()
        condition_str = raw_name[cond_idx:].strip()
        if condition_str: conditional_faces[face_name].append((condition_str, rule['path']))
        else: face_rules[face_name].append(rule['path'])

    generated_face_rules = {}
    fgname_to_paths_map = defaultdict(list)
    for rule in fgname_rules: fgname_to_paths_map[rule['name']].append(rule['path'])

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

    print(f"[INFO] 啟動平行執行緒處理，最大 Worker 數: {MAX_WORKERS}...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []
        for dress_name, diffs in dress_rules.items():
            for diff_id, dress_paths in diffs.items():
                current_dress_key = f"{dress_name}_{diff_id}"
                
                dress_layers_ids = []
                for p in dress_paths:
                    lid = path_to_id.get(p) or path_to_id.get(normalize_path_string(p))
                    
                    if lid is None and '/' in p:
                        last_part = p.split('/')[-1]
                        lid = path_to_id.get(last_part) or path_to_id.get(normalize_path_string(last_part))
                        
                    if lid is not None:
                        dress_layers_ids.append(lid)
                    else:
                        with log_lock:
                            log_file.write(f"[服裝路徑未匹配] 配置 '{current_dress_key}': 部件 '{p}' 在總表中找不到，跳過該圖層。\n")
                
                if not dress_layers_ids:
                    log_file.write(f"[服裝定義失敗] '{current_dress_key}' 的所有衣服部件在總表中都找不到，已跳過該組合。\n")
                    continue
                
                # 💡 核心演進：為當前服裝/姿勢，動態計算最終採用的表情規則（完美還原官方覆蓋邏輯）
                active_face_rules = {}
                for f_name, f_paths in final_face_rules.items():
                    active_face_rules[f_name] = list(f_paths)
                    
                # 檢查是否有成立的條件限定表情，若有，直接「覆蓋(Override)」基礎規則
                for f_name, rules_list in conditional_faces.items():
                    for condition_str, path in rules_list:
                        if evaluate_face_condition(condition_str, dress_name, diff_id):
                            # 特定姿勢下，該表情完全由特殊圖層取代
                            active_face_rules[f_name] = [path]
                            break 
                
                # 提交經過精確條件覆蓋後的最終表情群組
                submit_face_combinations(executor, futures, active_face_rules, dress_layers_ids, path_to_id, layer_df, pbd_base_name, current_dress_key, generated_filenames_set, log_file, output_folder, img_folders)
        
        concurrent.futures.wait(futures)
    print(f"『{pbd_base_name}』全局 Z-Order 智慧版合成工作順利完工！")

# --- 6. 核心排序與組合發送引擎 ---
def submit_face_combinations(executor, futures, face_rule_dict, dress_layers_ids, path_to_id, layer_df, pbd_base_name, dress_info_str, generated_filenames_set, log_file, output_folder, img_folders):
    
    all_needed_ids_set = set(dress_layers_ids)
    for face_paths in face_rule_dict.values():
         for p in face_paths:
             if '*' in p:
                 prefix_slash = p.replace('*', '')
                 prefix_underscore = normalize_path_string(prefix_slash)
                 for full_path, lid in path_to_id.items():
                     if full_path.startswith(prefix_slash) or full_path.startswith(prefix_underscore):
                         all_needed_ids_set.add(lid)
             else:
                 lid = path_to_id.get(p) or path_to_id.get(normalize_path_string(p))
                 if lid is None and '/' in p:
                     last_part = p.split('/')[-1]
                     lid = path_to_id.get(last_part) or path_to_id.get(normalize_path_string(last_part))
                 if lid: 
                     all_needed_ids_set.add(lid)

    filtered_df = layer_df[layer_df['layer_id'].isin(all_needed_ids_set)].copy()
    layer_info_map = filtered_df.set_index('layer_id').to_dict('index')

    for face_name, face_paths in face_rule_dict.items():
        combination_context = f"組合 '{dress_info_str} + {face_name}'"
        face_layers_ids = []
        all_paths_found = True
        
        for p in face_paths:
            if '*' in p:
                prefix_slash = p.replace('*', '')
                prefix_underscore = normalize_path_string(prefix_slash)
                matched_lids = [lid for full_path, lid in path_to_id.items() if full_path.startswith(prefix_slash) or full_path.startswith(prefix_underscore)]
                if matched_lids: face_layers_ids.extend(matched_lids)
                else: all_paths_found = False
            else:
                lid = path_to_id.get(p) or path_to_id.get(normalize_path_string(p))
                if lid is None and '/' in p:
                    last_part = p.split('/')[-1]
                    lid = path_to_id.get(last_part) or path_to_id.get(normalize_path_string(last_part))
                
                if lid is None: all_paths_found = False
                else: face_layers_ids.append(lid)
        
        if not all_paths_found: continue

        # ==================== 【100% 還原官方全局 Z-Order 倒序】 ====================
        current_active_set = set(dress_layers_ids + face_layers_ids)
        ordered_ids = [int(lid) for lid in layer_df['layer_id'].values if lid in current_active_set][::-1]
        # ====================================================================================
        
        layers_to_draw = []
        for lid in ordered_ids:
            if lid in layer_info_map:
                info = layer_info_map[lid].copy()
                info['layer_id'] = lid
                layers_to_draw.append(info)
        
        if not layers_to_draw: continue
        
        valid_draw_parts = [p for p in layers_to_draw if p['width'] > 0 and p['height'] > 0]
        if not valid_draw_parts: continue
        base_info_for_coords = valid_draw_parts[0]

        final_used_ids = [info['layer_id'] for info in layers_to_draw]
        id_string = "_".join(map(str, final_used_ids))
        output_filename = f"{pbd_base_name}_{id_string}.png"

        should_process = False
        with set_lock:
            if output_filename not in generated_filenames_set:
                generated_filenames_set.add(output_filename)
                should_process = True
        
        if not should_process: continue
        
        char_output_folder = os.path.join(output_folder, pbd_base_name)
        if not os.path.exists(char_output_folder): os.makedirs(char_output_folder)
        output_path = os.path.join(char_output_folder, output_filename)
        
        dress_id_set = set(dress_layers_ids)
        futures.append(executor.submit(create_composite_task, layers_to_draw, base_info_for_coords, output_path, log_file, combination_context, img_folders, dress_id_set))

# --- 7. 程式主入口 ---
if __name__ == '__main__':
    LOG_FILENAME = "generation_log.txt"
    print(f"大一統智慧旗艦版啟動... 日誌紀錄：{LOG_FILENAME}")
    with open(LOG_FILENAME, 'w', encoding='utf-8') as log_file:
        log_file.write(f"--- 旗艦自動配對生成開始 ({datetime.now()}) ---\n")
        
        all_files = glob.glob('*')
        layout_files = []
        for f in all_files:
            if os.path.isdir(f): continue
            f_lower = f.lower()
            if 'sinfo' in f_lower or 'log' in f_lower or f_lower.endswith('_info.txt'): continue
            if f_lower.endswith('.pbd.txt') or f_lower.endswith('.pbd') or f_lower.endswith('.txt'):
                layout_files.append(f)
            
        for layout_file in layout_files:
            pbd_base = layout_file
            for ext in ['.pbd.txt', '.pbd', '.txt']:
                if pbd_base.lower().endswith(ext):
                    pbd_base = pbd_base[:-len(ext)]
                    break
            
            stripped_base = re.sub(r'_\d+$', '', pbd_base)
            
            candidates = [
                pbd_base + '.sinfo.txt',
                pbd_base + '.sinfo',
                pbd_base + '_info.txt',
                stripped_base + '.sinfo.txt',
                stripped_base + '.sinfo',
                stripped_base + '_info.txt'
            ]
            
            sinfo_file = None
            for cand in candidates:
                if os.path.exists(cand):
                    sinfo_file = cand
                    break
                    
            if sinfo_file:
                process_character(layout_file, sinfo_file, log_file)
            else:
                print(f"[警告] 找不到與 '{layout_file}' 相匹配的規則母檔，已跳過。")
                log_file.write(f"[警告] 找不到 '{layout_file}' 的相匹配規則母檔，已跳過。\n")
                
    print(f"\n所有任務全面竣工！請查閱 output 資料夾與 {LOG_FILENAME} 檔案。")
