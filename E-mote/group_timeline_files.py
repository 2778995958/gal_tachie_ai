import os
import json
import hashlib
import shutil

# ==============================================================================
# --- 設定區 ---
# ==============================================================================
BASE_FOLDER = "."
TIMELINE_TEMP_FOLDER = "time"
MMO_FOLDER_PATH = "."
OUTPUT_FOLDER = "output"
OPERATION_MODE = "copy"

# ==============================================================================
# --- 核心函式 (get_hash_for_grouping 已更新) ---
# ==============================================================================

def find_timeline_control_recursively(data_structure):
    """遞迴搜尋函式，深入尋找 'timelineControl'。"""
    if isinstance(data_structure, dict):
        if 'timelineControl' in data_structure:
            return data_structure['timelineControl']
        for value in data_structure.values():
            result = find_timeline_control_recursively(value)
            if result is not None: return result
    elif isinstance(data_structure, list):
        for item in data_structure:
            result = find_timeline_control_recursively(item)
            if result is not None: return result
    return None

def get_hash_for_grouping(file_path):
    """
    【最新版】讀取 timeline 檔案，只提取所有 "diff": 0 的物件，
    然後對這個集合計算標準化的 hash。
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            timeline_list = json.load(f)
        
        # 確保我們處理的是一個列表
        if not isinstance(timeline_list, list):
            return None

        # 步驟 1: 只篩選出 "diff": 0 的物件
        diff0_objects = [obj for obj in timeline_list if isinstance(obj, dict) and obj.get("diff") == 0]
        
        # 如果沒有任何 "diff": 0 的物件，也算是一種有效的狀態
        # 步驟 2: 對篩選後的結果進行標準化並計算 hash
        canonical_string = json.dumps(diff0_objects, sort_keys=True, separators=(',', ':'))
        
        hasher = hashlib.md5()
        hasher.update(canonical_string.encode('utf-8'))
        return hasher.hexdigest()

    except (IOError, FileNotFoundError, json.JSONDecodeError):
        return None

# ==============================================================================
# --- 流程主體 (已更新為呼叫新的 hash 函數) ---
# ==============================================================================

def run_extraction_phase():
    """階段一：從根目錄的 JSON 中提取 timeline 檔案。"""
    print("--- 階段一：開始提取 Timeline 資料 ---")
    output_path_full = os.path.join(BASE_FOLDER, TIMELINE_TEMP_FOLDER)
    os.makedirs(output_path_full, exist_ok=True)
    success_count = 0; skipped_count = 0
    for filename in os.listdir(BASE_FOLDER):
        if filename.endswith(".json") and not filename.endswith("_timeline.json"):
            input_file_path = os.path.join(BASE_FOLDER, filename)
            try:
                with open(input_file_path, 'r', encoding='utf-8') as f: data = json.load(f)
                timeline_data = find_timeline_control_recursively(data)
                if timeline_data is not None:
                    base_name = os.path.splitext(filename)[0]
                    output_filename = f"{base_name}_timeline.json"
                    output_file_path = os.path.join(output_path_full, output_filename)
                    with open(output_file_path, 'w', encoding='utf-8') as f: json.dump(timeline_data, f, ensure_ascii=False, indent=2)
                    success_count += 1
                else: skipped_count += 1
            except Exception: skipped_count += 1
    print(f"提取完成！成功生成 {success_count} 個 timeline 檔案，跳過 {skipped_count} 個檔案。")

def run_grouping_phase():
    """階段二：根據 "diff": 0 的內容進行分組。"""
    print("\n--- 階段二：開始進行檔案分組 (精準比對模式) ---")
    
    timeline_folder_full = os.path.join(BASE_FOLDER, TIMELINE_TEMP_FOLDER)
    if not os.path.isdir(timeline_folder_full) or not os.listdir(timeline_folder_full):
        print(f"🤷 在 '{TIMELINE_TEMP_FOLDER}' 資料夾中找不到 timeline 檔案，無法進行分組。")
        return

    content_groups = {}
    for filename in os.listdir(timeline_folder_full):
        if filename.endswith("_timeline.json"):
            file_path = os.path.join(timeline_folder_full, filename)
            # 【已更新】呼叫新的 hash 函數
            file_hash = get_hash_for_grouping(file_path)
            if file_hash:
                if file_hash not in content_groups: content_groups[file_hash] = []
                content_groups[file_hash].append(os.path.basename(file_path))
    
    if not content_groups:
        print("🤷 分析 timeline 檔案失敗，無法進行分組。")
        return
        
    print(f"🔍 分析完成！所有檔案將被歸入 {len(content_groups)} 個不同的內容分組中。準備整理...")
    
    output_base_full = os.path.join(BASE_FOLDER, OUTPUT_FOLDER)
    os.makedirs(output_base_full, exist_ok=True)
    action_func = shutil.copy if OPERATION_MODE == "copy" else shutil.move
    
    group_counter = 1
    for file_list_basenames in content_groups.values():
        group_folder_name = f"{group_counter}組"
        group_path = os.path.join(output_base_full, group_folder_name)
        group_time_path = os.path.join(group_path, "time")
        group_mmo_path = os.path.join(group_path, "mmo")
        os.makedirs(group_time_path, exist_ok=True); os.makedirs(group_mmo_path, exist_ok=True)
        
        print(f"  🗂️  正在處理 '{group_folder_name}' (包含 {len(file_list_basenames)} 個檔案)...")
        
        for timeline_basename in file_list_basenames:
            timeline_path = os.path.join(timeline_folder_full, timeline_basename)
            action_func(timeline_path, group_time_path)
            base_name = timeline_basename.replace("_timeline.json", "")
            mmo_filename = f"{base_name}.mmo"
            mmo_source_path = os.path.join(MMO_FOLDER_PATH, mmo_filename)
            if os.path.exists(mmo_source_path):
                action_func(mmo_source_path, group_mmo_path)
            else:
                print(f"    ⚠️ 警告：找不到對應的 MMO 檔案: {mmo_filename}")
        group_counter += 1
    print("分組完成！")

# --- 程式入口 ---
if __name__ == "__main__":
    run_extraction_phase()
    run_grouping_phase()
    print("\n🎉 --- 所有任務執行完畢 --- 🎉")