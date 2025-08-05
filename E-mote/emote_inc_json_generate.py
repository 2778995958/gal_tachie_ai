import os
import glob
import json
import copy
import re
from itertools import product

# --- 區塊 1: JSON 範本定義 ---
# (此區塊與之前相同)
def get_base_timeline_template():
    """回傳一個空白的、符合 e-mote 格式的單一時間軸範本。"""
    # ... 完整的範本定義與之前相同 ...
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

# --- 區塊 2: 核心處理邏輯 (最終版) ---

def parse_inc_file_fully(file_path):
    """從 .inc 檔案中解析所有差分類別及其選項 (包含'無し')。"""
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
    """將組合好的資料轉換為巢狀資料夾結構"""
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

def convert_structure_to_json_list(nested_dict, folder_order):
    """遞迴地將巢狀字典轉換為 e-mote 的 folder/children 列表結構"""
    if not isinstance(nested_dict, dict) or not folder_order:
        return create_timeline_children(nested_dict)

    output_list = []
    remaining_folders = folder_order[1:]
    for key, value in sorted(nested_dict.items()):
        folder = {"type": "folder", "label": key, "children": convert_structure_to_json_list(value, remaining_folders)}
        output_list.append(folder)
    return output_list
    
def create_timeline_children(expressions):
    """將最終的組合表情物件列表轉換為 timeline 列表"""
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
    # 1. 定義所有要參與組合的「修飾屬性」類別。
    #    列表順序 = 資料夾層級順序
    MODIFIER_CATEGORIES = ["髪型", "頬", "手袋", "前髪", "頭部装飾", "マフラー", "陰毛"]
    
    # 2. 【新功能】在此填入本次執行不想組合的類別名稱
    #    例如: EXCLUDED_MODIFIERS = ["陰毛", "手袋"]
    EXCLUDED_MODIFIERS = ["陰毛", "手袋", "マフラー"]
    
    # 3. 定義主要的表情類別
    EXPRESSION_CATEGORY = "表情"
    # --- 設定結束 ---

    inc_files = glob.glob('*.inc')
    if not inc_files: print("在目前資料夾中找不到任何 .inc 檔案。")
    else: print(f"找到了 {len(inc_files)} 個 .inc 檔案: {', '.join(inc_files)}")

    all_file_folders = []

    for file_path in inc_files:
        print(f"\n--- 正在處理檔案: {file_path} ---")
        basename = os.path.splitext(os.path.basename(file_path))[0]
        
        all_data = parse_inc_file_fully(file_path)
        if not all_data or EXPRESSION_CATEGORY not in all_data:
            print(f"在 {file_path} 中找不到 '{EXPRESSION_CATEGORY}' 資料，已跳過。")
            continue

        expressions = [e for e in all_data.get(EXPRESSION_CATEGORY, []) if e['name'] not in ['無し', '']]
        
        # (修正) 準備組合列表時，尊重 EXCLUDED_MODIFIERS 設定
        active_categories_for_combo = [cat for cat in MODIFIER_CATEGORIES if cat in all_data and cat not in EXCLUDED_MODIFIERS]
        
        modifier_lists_with_category = []
        for cat in active_categories_for_combo:
            modifier_lists_with_category.append([{'category': cat, 'pattern': p} for p in all_data[cat]])

        if not modifier_lists_with_category:
            modifier_combinations = [[]]
        else:
            modifier_combinations = list(product(*modifier_lists_with_category))

        print(f"找到 {len(expressions)} 個主表情, {len(modifier_combinations)} 種修飾組合，總計將生成 {len(expressions) * len(modifier_combinations)} 個組合表情。")

        combined_expression_data = []
        for expression in expressions:
            for mod_combo in modifier_combinations:
                merged_params = {}
                base_name_part = f"{basename}_{expression['name']}{expression['id']}"
                suffix_parts = []
                folder_path_parts = []

                for mod_item in mod_combo:
                    category_name = mod_item['category']
                    pattern = mod_item['pattern']
                    
                    merged_params.update(pattern['params'])
                    
                    # (修正) 建立帶有檔名前綴的、唯一的資料夾路徑
                    folder_path_parts.append(f"{basename}{category_name}_{pattern['name']}")
                    suffix_parts.append(f"{category_name}_{pattern['id']}")
                
                merged_params.update(expression['params'])
                final_name = f"{base_name_part}_{'_'.join(suffix_parts)}" if suffix_parts else base_name_part
                
                combined_timeline = {"name": final_name, "params": merged_params}
                combined_expression_data.append({"folder_path": folder_path_parts, "timeline": combined_timeline})

        if combined_expression_data:
            nested_structure = build_nested_folders(combined_expression_data, active_categories_for_combo)
            file_main_folder = {
                "type": "folder",
                "label": basename,
                "children": convert_structure_to_json_list(nested_structure, active_categories_for_combo)
            }
            all_file_folders.append(file_main_folder)

    if all_file_folders:
        print(f"\n--- 處理完成，準備寫入最終 JSON ---")
        final_object = {"value": all_file_folders, "id": "emote_timelinelist"}
        final_json_string = json.dumps(final_object, indent=1, ensure_ascii=False)
        
        output_filename = "output_final_prefixed.json"
        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write(final_json_string)
        print(f"\n成功！所有排列組合已生成並寫入 '{output_filename}' 檔案。")
    else:
        print("\n沒有從任何檔案中解析出可用的資料，未生成 JSON 檔案。")