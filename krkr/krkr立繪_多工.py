# ==============================================================================
# 【大一統智慧全局 Z-Order 版 Ver. 49.0 - 官方隱藏機制全解鎖旗艦版】
# ==============================================================================
# 旗艦級重大更新：
# 1. 修正 Dummy 阻斷 Bug：遇到路徑為 dummy 的五官槽位時自動放行，不再誤判為缺檔而跳過表情。
# 2. 實作 FaceFolder 機制：完整解析 dress 規則第 6 欄，特定姿勢下自動重導向至專用五官路徑。
# 3. 實作 Layout Diff_ID 聯動：完整解析總表第 14 欄，自動激活並渲染與基礎圖層綁定的隱藏聯動圖層。
# 4. 100% 還原官方全局 Z-Order 鐵律：所有啟用圖層完全對照總表先天順序進行全局倒序 [::-1] 疊加。
# 5. 智慧型名稱後退降級搜索：完美修復「只有臉沒身體」問題，路徑不對時自動降級匹配純圖層名。
# 6. 5重圖片格式智慧相容：自動碰撞 {ID}.png, {名稱}.png 及其前綴組合，確保素材 100% 載入。
# 7. 智慧缺圖控管策略（MISSING_IMG_POLICY）：支援 0(缺圖都合), 1(衣服缺不合), 2(缺一不可)。
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
PRIORITY_OVERLAY_PATHS = {'かぶせ 水着12', '鬼面123', 'かぶせ 水着123', '追加_麦わら帽子123'} 

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
                    has_keyword = any(k in content for k in ['dress', 'face', 'layer_type', '#', 'bs_', 'fgname'])
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

def find_layer_id(p, path_to_id, layer_df):
    """智慧型多層級路徑匹配器：支持精確對齊與局部後綴相容，完美杜絕『同名圖層』指鹿為馬"""
    if not p or p.lower() == 'dummy': return None
    
    # 1. 第一優先：記憶體快取精確匹配
    if p in path_to_id: return path_to_id[p]
    norm_p = normalize_path_string(p)
    if norm_p in path_to_id: return path_to_id[norm_p]
    
    # 2. 第二優先：針對局部描述，反向進行完整路徑後綴精確對齊
    if '/' in p:
        p_clean = p.strip('/')
        norm_p_clean = normalize_path_string(p_clean)
        
        for _, row in layer_df.iterrows():
            if row['full_path_slash'].endswith(p_clean):
                return row['layer_id']
        for _, row in layer_df.iterrows():
            if row['full_path_underscore'].endswith(norm_p_clean):
                return row['layer_id']
                
    # 3. 保底盲配：切出最後一節圖層名稱進行模糊匹配
    last_part = p.split('/')[-1]
    if last_part in path_to_id: return path_to_id[last_part]
    norm_last = normalize_path_string(last_part)
    if norm_last in path_to_id: return path_to_id[norm_last]
    
    return None

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
                # 💡 核心優化：一路讀到第 14 欄，抓取官方隱藏的 diff_id 聯動圖層
                diff_id_val = ""
                if len(row) >= 14 and row[13].strip():
                    diff_id_val = row[13].strip()
                    
                parsed_data.append({
                    'layer_id': int(row[9].strip()), 'name': row[1].strip(),
                    'left': int(row[2].strip()), 'top': int(row[3].strip()),
                    'width': int(row[4].strip()) if len(row) > 4 and row[4].strip().isdigit() else 0,
                    'height': int(row[5].strip()) if len(row) > 5 and row[5].strip().isdigit() else 0,
                    'opacity': int(row[7].strip()) if len(row) > 7 and row[7].strip().isdigit() else 255,
                    'group_layer_id': int(row[10].strip()) if len(row) > 10 and row[10].strip().isdigit() else 0,
                    'diff_id': diff_id_val
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
        
        valid_parts = [p for p in layers_to_draw if p['width'] > 0 and p['height'] > 0]
        if not valid_parts: return
        
        first_part = valid_parts[0]
        min_x, min_y = first_part['left'] - base_x, first_part['top'] - base_y
        max_x, max_y = min_x + first_part['width'], min_y + first_part['height']

        for part_info in valid_parts[1:]:
            dx, dy = part_info['left'] - base_x, part_info['top'] - base_y
            min_x, min_y = min(min_x, dx), min(min_y, dy)
            max_x, max_y = max(max_x, dx + part_info['width']), max(max_y, dy + part_info['height'])
        
        canvas_width, canvas_height = max_x - min_x, max_y - min_y
        master_canvas = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))

        # 貼圖與多重格式智慧搜索
        for part_info in valid_parts:
            part_img = None
            lid = part_info['layer_id']
            lname = part_info.get('name', '')
            
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
                continue 

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
    layer_diff_map = {} # 儲存總表中的聯動 diff_id 映射
    for _, r in layer_df.iterrows():
        path_to_id[r['full_path_slash']] = r['layer_id']
        path_to_id[r['full_path_underscore']] = r['layer_id']
        path_to_id[normalize_path_string(r['full_path_slash'])] = r['layer_id']
        path_to_id[r['name']] = r['layer_id']
        path_to_id[normalize_path_string(r['name'])] = r['layer_id']
        if r['diff_id']:
            layer_diff_map[r['layer_id']] = int(r['diff_id'])

    img_folders = [pbd_base_name, stripped_base_name]

    face_rules = defaultdict(list)
    conditional_faces = defaultdict(list)
    facegroup_order = [r['group_name'] for r in sinfo_rules if r['type'] == 'facegroup']
    fgname_rules = [r for r in sinfo_rules if r['type'] == 'fgname']
    fgalias_rules = [r for r in sinfo_rules if r['type'] == 'fgalias']
    
    all_dress_rules_raw = [r['data'] for r in sinfo_rules if r['type'] == 'dress']
    
    dress_rules = defaultdict(lambda: defaultdict(list))
    dress_bases = defaultdict(list)
    # 💡 核心還原：建立姿勢與 facefolder 的映射字典
    face_folders = defaultdict(dict) 

    for row in all_dress_rules_raw:
        dress_name = row[1].strip()
        kind = row[2].strip()
        if kind == 'base' and len(row) >= 4:
            base_path = row[3].strip()
            if base_path and base_path.lower() != 'dummy':
                if base_path not in dress_bases[dress_name]:
                    dress_bases[dress_name].append(base_path)
                    
    for row in all_dress_rules_raw:
        dress_name = row[1].strip()
        kind = row[2].strip()
        if kind == 'diff' and len(row) >= 5:
            diff_id = row[3].strip()
            diff_path = row[4].strip()
            if diff_path and diff_path.lower() != 'dummy':
                if diff_path not in dress_rules[dress_name][diff_id]:
                    dress_rules[dress_name][diff_id].append(diff_path)
            # 💡 核心還原：讀取服裝規則第 6 欄的 facefolder 定義
            if len(row) >= 6 and row[5].strip():
                ff_path = row[5].strip()
                if ff_path.lower() != 'dummy':
                    face_folders[dress_name][diff_id] = ff_path
                    
    for dress_name, base_paths in dress_bases.items():
        if dress_name in dress_rules:
            for diff_id in dress_rules[dress_name]:
                dress_rules[dress_name][diff_id] = base_paths + dress_rules[dress_name][diff_id]
        else:
            dress_rules[dress_name]["通常"] = list(base_paths)

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

    final_face_rules = defaultdict(list)
    for k, v in face_rules.items(): final_face_rules[k].extend(v)
    for k, v in generated_face_rules.items(): final_face_rules[k].extend(v)
    if not final_face_rules: return

    print(f"[INFO] 啟動平行執行緒處理，最大 Worker 數: {MAX_WORKERS}...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []
        for dress_name, diffs in dress_rules.items():
            for diff_id, dress_paths in diffs.items():
                current_dress_key = f"{dress_name}_{diff_id}"
                
                dress_layers_ids = []
                for p in dress_paths:
                    lid = find_layer_id(p, path_to_id, layer_df)
                    if lid is None and '/' in p:
                        last_part = p.split('/')[-1]
                        lid = find_layer_id(last_part, path_to_id, layer_df)
                        
                    if lid is not None:
                        dress_layers_ids.append(lid)
                    else:
                        with log_lock:
                            log_file.write(f"[服裝路徑未匹配] 配置 '{current_dress_key}': 部件 '{p}' 在總表中找不到。\n")
                
                if not dress_layers_ids:
                    continue
                
                active_face_rules = {}
                for f_name, f_paths in final_face_rules.items():
                    active_face_rules[f_name] = list(f_paths)
                    
                for f_name, rules_list in conditional_faces.items():
                    for condition_str, path in rules_list:
                        if evaluate_face_condition(condition_str, dress_name, diff_id):
                            active_face_rules[f_name] = [path]
                            break 
                
                # 💡 核心還原：提取當前服裝姿勢是否存在 facefolder 專用目錄
                current_ff = face_folders[dress_name].get(diff_id, None)
                
                submit_face_combinations(executor, futures, active_face_rules, dress_layers_ids, path_to_id, layer_df, pbd_base_name, current_dress_key, generated_filenames_set, log_file, output_folder, img_folders, current_ff, layer_diff_map)
        
        concurrent.futures.wait(futures)
    print(f"『{pbd_base_name}』全局 Z-Order 智慧版合成工作順利完工！")

# --- 6. 核心排序與組合發送引擎 ---
def submit_face_combinations(executor, futures, face_rule_dict, dress_layers_ids, path_to_id, layer_df, pbd_base_name, dress_info_str, generated_filenames_set, log_file, output_folder, img_folders, face_folder, layer_diff_map):
    
    dress_id_set = set(dress_layers_ids)
    all_needed_ids_set = set(dress_layers_ids)
    
    for face_paths in face_rule_dict.values():
         for p in face_paths:
             if p.lower() == 'dummy': continue # 💡 完美修正：dummy 圖層跳過不計入查找，防範阻斷
             if '*' in p:
                 prefix_slash = p.replace('*', '')
                 if face_folder: prefix_slash = f"{face_folder}/{prefix_slash}"
                 prefix_underscore = normalize_path_string(prefix_slash)
                 for full_path, lid in path_to_id.items():
                     if full_path.startswith(prefix_slash) or full_path.startswith(prefix_underscore):
                         all_needed_ids_set.add(lid)
             else:
                 # 💡 完美還原：若存在 face_folder，優先拼接查找
                 lid = None
                 if face_folder:
                     lid = find_layer_id(f"{face_folder}/{p}", path_to_id, layer_df)
                 if lid is None:
                     lid = find_layer_id(p, path_to_id, layer_df)
                 if lid: all_needed_ids_set.add(lid)

    filtered_df = layer_df[layer_df['layer_id'].isin(all_needed_ids_set)].copy()
    layer_info_map = filtered_df.set_index('layer_id').to_dict('index')

    for face_name, face_paths in face_rule_dict.items():
        combination_context = f"組合 '{dress_info_str} + {face_name}'"
        face_layers_ids = []
        all_paths_found = True
        
        for p in face_paths:
            if p.lower() == 'dummy': continue # 💡 完美修正：遇到 dummy 放行不報錯
            if '*' in p:
                prefix_slash = p.replace('*', '')
                if face_folder: prefix_slash = f"{face_folder}/{prefix_slash}"
                prefix_underscore = normalize_path_string(prefix_slash)
                matched_lids = [lid for full_path, lid in path_to_id.items() if full_path.startswith(prefix_slash) or full_path.startswith(prefix_underscore)]
                if matched_lids: face_layers_ids.extend(matched_lids)
                else: all_paths_found = False
            else:
                # 💡 完美還原：FaceFolder 優先路徑探測機制
                lid = None
                if face_folder:
                    lid = find_layer_id(f"{face_folder}/{p}", path_to_id, layer_df)
                if lid is None:
                    lid = find_layer_id(p, path_to_id, layer_df)
                    
                if lid is None: all_paths_found = False
                else: face_layers_ids.append(lid)
        
        if not all_paths_found: continue

        # ==================== 【100% 還原官方全局 Z-Order 倒序】 ====================
        current_active_set = set(dress_layers_ids + face_layers_ids)
        
        # 💡 核心還原：大總表 diff_id 聯動機制
        additional_linked_ids = set()
        for active_id in current_active_set:
            if active_id in layer_diff_map:
                additional_linked_ids.add(layer_diff_map[active_id])
        current_active_set.update(additional_linked_ids)
        
        # 進行總表先天順序提取與反轉渲染
        ordered_ids = [int(lid) for lid in layer_df['layer_id'].values if lid in current_active_set][::-1]
        # ====================================================================================
        
        layers_to_draw = []
        missing_dress = False
        missing_face = False
        
        for lid in ordered_ids:
            if lid in layer_info_map:
                info = layer_info_map[lid].copy()
                info['layer_id'] = lid
                layers_to_draw.append(info)
                
                lname = info.get('name', '')
                if info['width'] == 0 or info['height'] == 0: continue
                
                part_img_found = False
                for folder in img_folders:
                    if os.path.exists(os.path.join(folder, f"{folder}_{lid}.png")) or os.path.exists(os.path.join(folder, f"{lid}.png")) or (lname and (os.path.exists(os.path.join(folder, f"{folder}_{lname}.png")) or os.path.exists(os.path.join(folder, f"{lname}.png")))):
                        part_img_found = True
                        break
                if not part_img_found:
                    if lid in dress_id_set: missing_dress = True
                    else: missing_face = True
                    with log_lock:
                        log_file.write(f"[圖層缺失] {combination_context}: 找不到圖層 ID {lid} ({lname}) 的實體圖片。\n")

        if not layers_to_draw: continue
        
        if MISSING_IMG_POLICY == 1 and missing_dress:
            with log_lock: log_file.write(f"[原則跳過] {combination_context}: 衣服/身體圖層有缺，依控管策略(1)阻斷合成。\n")
            continue
        elif MISSING_IMG_POLICY == 2 and (missing_dress or missing_face):
            with log_lock: log_file.write(f"[原則跳過] {combination_context}: 組合中存有缺件，依控管策略(2)阻斷合成。\n")
            continue

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