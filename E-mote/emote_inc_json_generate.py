import os
import glob
import json
import copy
import re
import sys
from itertools import product

# --- 區塊 1: JSON 範本定義 ---
def get_base_timeline_template():
    """回傳一個基礎的、空白的單一時間軸範本，用於兩種模式。"""
    # ... 範本定義與之前相同 ...
    return {
        "loopBegin": -1, "loopEnd": -1, "lastTime": -1, "diff": 0, "label": "預設標籤",
        "variableList": [
            {"label": "move_UD", "frameList": [{"time": 0, "content": {"value": 0.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "move_LR", "frameList": [{"time": 0, "content": {"value": 0.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "head_UD", "frameList": [{"time": 0, "content": {"value": 0.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "head_LR", "frameList": [{"time": 0, "content": {"value": 0.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "head_slant", "frameList": [{"time": 0, "content": {"value": 0.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "body_UD", "frameList": [{"time": 0, "content": {"value": 0.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "body_LR", "frameList": [{"time": 0, "content": {"value": 0.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "body_slant", "frameList": [{"time": 0, "content": {"value": 0.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "act_sp", "frameList": [{"time": 0, "content": {"value": 0.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "act_sp2", "frameList": [{"time": 0, "content": {"value": 0.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "act_sp3", "frameList": [{"time": 0, "content": {"value": 0.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "face_eye_open", "frameList": [{"time": 0, "content": {"value": 0.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "face_eye_sp", "frameList": [{"time": 0, "content": {"value": 0.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "face_eye_hi", "frameList": [{"time": 0, "content": {"value": 0.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "face_eye_LR", "frameList": [{"time": 0, "content": {"value": 0.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "face_eye_UD", "frameList": [{"time": 0, "content": {"value": 0.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "face_hitomi_sp", "frameList": [{"time": 0, "content": {"value": 0.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "face_eyebrow", "frameList": [{"time": 0, "content": {"value": 40.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "face_eyebrow_sp", "frameList": [{"time": 0, "content": {"value": 0.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "face_mouth", "frameList": [{"time": 0, "content": {"value": 42.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "face_mouth_sp", "frameList": [{"time": 0, "content": {"value": 0.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "face_talk", "frameList": [{"time": 0, "content": {"value": 0.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "face_tears", "frameList": [{"time": 0, "content": {"value": 0.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "face_cheek", "frameList": [{"time": 0, "content": {"value": 0.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "arm_type", "frameList": [{"time": 0, "content": {"value": 0.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "fade_a", "frameList": [{"time": 0, "content": {"value": 0.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "fade_b", "frameList": [{"time": 0, "content": {"value": 0.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "fade_c", "frameList": [{"time": 0, "content": {"value": 0.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "fade_d", "frameList": [{"time": 0, "content": {"value": 0.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "fade_e", "frameList": [{"time": 0, "content": {"value": 0.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "fade_q", "frameList": [{"time": 0, "content": {"value": 0.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "fade_r", "frameList": [{"time": 0, "content": {"value": 0.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "fade_s", "frameList": [{"time": 0, "content": {"value": 0.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "fade_t", "frameList": [{"time": 0, "content": {"value": 0.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "fade_u", "frameList": [{"time": 0, "content": {"value": 0.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "fade_v", "frameList": [{"time": 0, "content": {"value": 0.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "fade_w", "frameList": [{"time": 0, "content": {"value": 1.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "fade_x", "frameList": [{"time": 0, "content": {"value": 1.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "fade_y", "frameList": [{"time": 0, "content": {"value": 1.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "fade_z", "frameList": [{"time": 0, "content": {"value": 1.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "vr_LR", "frameList": [{"time": 0, "content": {"value": 0.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]},
            {"label": "vr_UD", "frameList": [{"time": 0, "content": {"value": 0.0, "easing": 0}, "type": 2}, {"time": 1, "content": None, "type": 0}]}
        ]
    }
# --- 區塊 2: 核心處理邏輯 ---

def parse_inc_file_fully(file_path):
    """從 .inc 檔案中解析所有差分類別及其選項。"""
    # ... 此函數與之前版本相同 ...
    all_categories = {}
    dif_definitions = {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f: content = f.read()
    except UnicodeDecodeError:
        try:
            with open(file_path, 'r', encoding='shift-jis') as f: content = f.read()
        except Exception as e:
            print(f"錯誤: 無法讀取檔案 {file_path}, 原因: {e}"); return {}
    
    dif_match = re.search(r'#dif\s*(.*?)\s*#', content, re.DOTALL)
    if dif_match:
        for line in dif_match.group(1).strip().split('\n'):
            parts = line.strip().split()
            if len(parts) >= 2: dif_definitions[parts[0]] = parts[1]

    pattern_content_match = re.search(r'#pattern\s*(.*?)\s*#', content, re.DOTALL)
    if not pattern_content_match: return {}
    pattern_content = pattern_content_match.group(1)

    header_regex = re.compile(r'^%(\w+)\s+(\S+)\s+(.*)', re.MULTILINE)
    matches = list(header_regex.finditer(pattern_content))
    
    for i, match in enumerate(matches):
        digit, item_id, item_name = match.groups()
        category_name = dif_definitions.get(digit)
        if not category_name: continue

        start_pos = match.end()
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(pattern_content)
        body = pattern_content[start_pos:end_pos].strip()
        
        if category_name not in all_categories: all_categories[category_name] = []
        
        item = {"id": item_id, "name": item_name.strip(), "params": {}}
        for param_line in body.split('\n'):
            param_parts = param_line.strip().split(maxsplit=1)
            if len(param_parts) == 2:
                key, value_str = param_parts
                try: item["params"][key] = float(value_str) if '.' in value_str else int(value_str)
                except ValueError: pass
        
        all_categories[category_name].append(item)
            
    return all_categories

def build_nested_folders(combination_data, folder_order):
    """將組合好的資料轉換為巢狀資料夾結構。"""
    if not folder_order:
        # 如果沒有修飾屬性，直接回傳扁平列表 (現在是單一的合併後timeline)
        return [data['timeline'] for data in combination_data]

    root = {}
    for data in combination_data:
        current_level = root
        for i, folder_name in enumerate(folder_order):
            key = data['folder_path'][i]
            if key not in current_level:
                if i == len(folder_order) - 1: current_level[key] = []
                else: current_level[key] = {}
            current_level = current_level[key]
        current_level.append(data['timeline'])
    return root

def convert_structure_to_json_list(nested_data, folder_order):
    """遞迴地將巢狀結構轉換為 e-mote 的 folder/children 列表結構"""
    if not folder_order:
        # 到達最深層，直接回傳已包含最終 timeline 物件的列表
        return nested_data

    output_list = []
    remaining_folders = folder_order[1:]
    for key, value in sorted(nested_data.items()):
        folder = {"type": "folder", "label": key, "children": convert_structure_to_json_list(value, remaining_folders)}
        output_list.append(folder)
    return output_list
    
def create_separate_timeline_children(expressions):
    """為 'separate_files' 模式將組合表情物件轉換為 timeline 列表"""
    base_template = get_base_timeline_template()
    children = []
    for expr in sorted(expressions, key=lambda x: x['name']):
        new_timeline = copy.deepcopy(base_template)
        new_timeline['label'] = expr['name']
        variable_map = {var['label']: var for var in new_timeline['variableList']}
        for param_name, param_value in expr['params'].items():
            if param_name in variable_map:
                variable_map[param_name]['frameList'][0]['content']['value'] = param_value
        children.append(new_timeline)
    return children

# --- 區塊 3: 主程式執行區 ---

if __name__ == "__main__":
    # --- 使用者設定 ---
    # 1. 輸出模式:
    #    "separate_files"     -> 每一個組合都是獨立的 timeline
    #    "combined_per_folder" -> 同一組合下的所有表情，合併為一個多影格 timeline
    OUTPUT_MODE = "combined_per_folder"
    
    MODIFIER_CATEGORIES = ["髪型", "頬", "手袋", "前髪", "頭部装飾", "マフラー"]
    EXCLUDED_MODIFIERS = ["陰毛"]
    EXPRESSION_CATEGORY = "表情"
    # --- 設定結束 ---

    if len(sys.argv) > 1:
        inc_files = [f for f in sys.argv[1:] if f.lower().endswith('.inc')]
        print("--- 拖放模式 ---")
    else:
        inc_files = glob.glob('*.inc')
        print("--- 批次模式 ---")
    
    if not inc_files:
        print("在目前資料夾中找不到任何 .inc 檔案。")
        if sys.platform == "win32": input("請按 Enter 鍵結束...")
        sys.exit()

    print(f"準備處理 {len(inc_files)} 個 .inc 檔案: {', '.join(os.path.basename(f) for f in inc_files)}")

    # --- 資料處理與組合 ---
    all_file_folders = []
    for file_path in inc_files:
        print(f"\n--- 正在處理檔案: {os.path.basename(file_path)} ---")
        basename = os.path.splitext(os.path.basename(file_path))[0]
        
        all_data = parse_inc_file_fully(file_path)
        if not all_data or EXPRESSION_CATEGORY not in all_data:
            print(f"在 {file_path} 中找不到 '{EXPRESSION_CATEGORY}' 資料，已跳過。")
            continue

        expressions = sorted([e for e in all_data.get(EXPRESSION_CATEGORY, []) if e['name'] not in ['無し', '']], key=lambda x: x['name'])
        active_categories_for_combo = [cat for cat in MODIFIER_CATEGORIES if cat in all_data and cat not in EXCLUDED_MODIFIERS]
        
        modifier_lists_with_category = [[{'category': cat, 'pattern': p} for p in all_data[cat]] for cat in active_categories_for_combo]
        modifier_combinations = list(product(*modifier_lists_with_category)) if modifier_lists_with_category else [[]]

        print(f"找到 {len(expressions)} 個主表情, {len(modifier_combinations)} 種修飾組合。")

        # --- 根據輸出模式決定生成邏輯 ---
        if OUTPUT_MODE == 'separate_files':
            # 模式1: 每個組合都是獨立的 timeline
            combination_data = []
            for expression in expressions:
                for mod_combo in modifier_combinations:
                    merged_params = {}
                    base_name_part = f"{basename}_{expression['name']}{expression['id']}"
                    suffix_parts, folder_path_parts = [], []
                    for item in mod_combo:
                        merged_params.update(item['pattern']['params'])
                        folder_path_parts.append(f"{basename}{item['category']}_{item['pattern']['name']}")
                        suffix_parts.append(f"{item['category']}_{item['pattern']['id']}")
                    merged_params.update(expression['params'])
                    final_name = f"{base_name_part}_{'_'.join(suffix_parts)}" if suffix_parts else base_name_part
                    
                    timeline_obj = {"name": final_name, "params": merged_params}
                    combination_data.append({"folder_path": folder_path_parts, "timeline": timeline_obj})

            nested_structure = build_nested_folders(combination_data, active_categories_for_combo)
            # 在這裡，最深層的 children 是 create_separate_timeline_children 產生的
            # 我們需要一個修改版的 convert_structure
            def convert_to_separate_json(nested_data, folder_order):
                if not folder_order: return create_separate_timeline_children(nested_data)
                output_list = []
                for key, value in sorted(nested_data.items()):
                    folder = {"type": "folder", "label": key, "children": convert_to_separate_json(value, folder_order[1:])}
                    output_list.append(folder)
                return output_list

            children = convert_to_separate_json(nested_structure, active_categories_for_combo)

        elif OUTPUT_MODE == 'combined_per_folder':
            # 模式2: 每個組合是一個多影格 timeline
            combination_data = []
            for mod_combo in modifier_combinations:
                # 為這個修飾組合建立一個 timeline
                combined_timeline_obj = get_base_timeline_template()
                num_frames = len(expressions)

                for variable in combined_timeline_obj['variableList']:
                    label, last_value = variable['label'], variable['frameList'][0]['content']['value']
                    new_frame_list = []
                    for t, expression in enumerate(expressions):
                        # 合併參數: 修飾 -> 表情
                        merged_params = {}
                        suffix_parts, folder_path_parts = [], []
                        for item in mod_combo:
                            merged_params.update(item['pattern']['params'])
                            folder_path_parts.append(f"{basename}{item['category']}_{item['pattern']['name']}")
                            suffix_parts.append(f"{item['category']}_{item['pattern']['id']}")
                        merged_params.update(expression['params'])
                        
                        current_value = merged_params.get(label, last_value)
                        new_frame_list.append({"time": t, "content": {"value": current_value, "easing": 0}, "type": 2})
                        last_value = current_value
                    
                    new_frame_list.append({"time": num_frames, "content": None, "type": 0})
                    variable['frameList'] = new_frame_list

                combined_timeline_obj['lastTime'] = num_frames
                combined_timeline_obj['label'] = "_".join([p.split('_')[-1] for p in folder_path_parts]) or "Default"
                
                combination_data.append({"folder_path": folder_path_parts, "timeline": combined_timeline_obj})
            
            nested_structure = build_nested_folders(combination_data, active_categories_for_combo)
            children = convert_structure_to_json_list(nested_structure, active_categories_for_combo)

        else:
            print(f"錯誤：未知的 OUTPUT_MODE '{OUTPUT_MODE}'。")
            continue

        all_file_folders.append({"type": "folder", "label": basename, "children": children})

    # --- 最終檔案寫入 ---
    if all_file_folders:
        final_object = {"value": all_file_folders, "id": "emote_timelinelist"}
        final_json_string = json.dumps(final_object, indent=1, ensure_ascii=False)
        output_filename = f"output_{OUTPUT_MODE}.json"
        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write(final_json_string)
        print(f"\n成功！已生成 '{output_filename}' 檔案。")
    else:
        print("\n沒有從任何檔案中解析出可用的資料，未生成 JSON 檔案。")

    if sys.platform == "win32":
        input("處理完畢，請按 Enter 鍵結束...")
