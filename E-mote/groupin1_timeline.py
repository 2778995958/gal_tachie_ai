import sys
import json
import os

def merge_timelines(input_path):
    """
    將包含多個時間軸的 JSON 檔案合併為單一的連續時間軸 JSON 檔案。

    Args:
        input_path (str): 輸入的 JSON 檔案路徑 (例如 '1.json')。

    Returns:
        bool: 如果成功轉換則返回 True，否則返回 False。
    """
    # --- 1. 讀取並驗證輸入檔案 ---
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if 'id' not in data or 'value' not in data or not isinstance(data['value'], list):
            print(f"錯誤：輸入檔案 '{input_path}' 的格式不正確。它應該包含一個 'value' 列表。")
            return False

        source_timelines = data['value']
        if not source_timelines:
            print(f"錯誤：輸入檔案 '{input_path}' 的 'value' 列表是空的。")
            return False

    except FileNotFoundError:
        print(f"錯誤：找不到檔案 '{input_path}'。")
        return False
    except json.JSONDecodeError:
        print(f"錯誤：檔案 '{input_path}' 不是一個有效的 JSON 檔案。")
        return False
    except Exception as e:
        print(f"讀取檔案時發生未預期的錯誤：{e}")
        return False

    # ------------------- 修正點在這裡 -------------------
    #  原本錯誤的 'input_psth' 已被更正為 'input_path'
    print(f"成功讀取檔案 '{input_path}'，發現 {len(source_timelines)} 個時間軸。")
    # ---------------------------------------------------

    # --- 2. 準備合併資料 ---
    num_timelines = len(source_timelines)
    
    all_labels = set()
    for timeline in source_timelines:
        for variable in timeline.get('variableList', []):
            all_labels.add(variable['label'])

    merged_variables_data = {label: [] for label in sorted(list(all_labels))}

    # --- 3. 遍歷並合併時間軸 ---
    for time_index, timeline in enumerate(source_timelines):
        variables_in_timeline = {
            var['label']: var.get('frameList', []) 
            for var in timeline.get('variableList', [])
        }

        for label in merged_variables_data.keys():
            if label in variables_in_timeline and variables_in_timeline[label]:
                source_frame = variables_in_timeline[label][0]
                
                new_frame = {
                    "time": time_index,
                    "content": source_frame.get('content'),
                    "type": source_frame.get('type')
                }
                merged_variables_data[label].append(new_frame)

    # --- 4. 建立最終的輸出結構 ---
    final_variable_list = []
    for label, frame_list in merged_variables_data.items():
        if frame_list:
            frame_list.append({
                "time": num_timelines,
                "content": None,
                "type": 0
            })
        final_variable_list.append({"label": label, "frameList": frame_list})

    output_data = {
        "id": "emote_timeline",
        "value": {
            "loopBegin": -1,
            "loopEnd": -1,
            "lastTime": num_timelines,
            "variableList": final_variable_list,
            "diff": source_timelines[0].get('diff', 0),
            "label": source_timelines[0].get('label', 'merged_timeline')
        }
    }

    # --- 5. 寫入新的 JSON 檔案 ---
    output_path = os.path.splitext(input_path)[0] + '_converted.json'
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=1)
        print(f"轉換成功！已將結果儲存至 '{output_path}'")
        return True
    except Exception as e:
        print(f"寫入檔案時發生錯誤：{e}")
        return False

# --- 主程式入口 ---
if __name__ == "__main__":
    if len(sys.argv) > 1:
        input_file_path = sys.argv[1]
        print(f"正在處理檔案：{input_file_path}")
        merge_timelines(input_file_path)
    else:
        print("請將要轉換的 JSON 檔案拖曳到這個 .py 檔案的圖示上。")
    
    os.system("pause")