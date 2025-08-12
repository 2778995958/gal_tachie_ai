import sys
import json
import os

def merge_timelines(input_path):
    """
    將包含多個時間軸的 JSON 檔案合併為單一的連續時間軸 JSON 檔案。
    套用規則：將來源的第0格，用於輸出的第0和第1格，並在結尾添加結束標記。
    lastTime 固定為 -1。

    Args:
        input_path (str): 輸入的 JSON 檔案路徑。

    Returns:
        bool: 如果成功轉換則返回 True，否則返回 False。
    """
    # --- 1. 讀取並驗證輸入檔案 ---
    print(f"開始處理檔案：'{input_path}'")
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if 'id' not in data or 'value' not in data or not isinstance(data['value'], list):
            print(f"錯誤：輸入檔案 '{input_path}' 的格式不正確。")
            return False

        original_timelines = data['value']
        if not original_timelines:
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

    # --- 2. 根據規則建立處理列表：將第0格複製一份放到最前面 ---
    processed_timelines = [original_timelines[0]] + original_timelines
    
    num_frames = len(processed_timelines)
    print(f"成功讀取檔案，發現 {len(original_timelines)} 個獨立時間軸。")
    print(f"套用規則後，將處理並產生 {num_frames} 個影格 (第0格重複一次)。")

    # --- 3. 準備合併資料 ---
    all_labels = set()
    for timeline in original_timelines:
        for variable in timeline.get('variableList', []):
            if 'label' in variable:
                all_labels.add(variable['label'])

    sorted_labels = sorted(list(all_labels))
    merged_variables_data = {label: [] for label in sorted_labels}

    # --- 4. 核心轉換邏輯 ---
    for time_index, timeline in enumerate(processed_timelines):
        variables_in_timeline = {
            var['label']: var.get('frameList', []) 
            for var in timeline.get('variableList', []) if 'label' in var
        }

        for label in sorted_labels:
            source_frame_data = None
            if label in variables_in_timeline and variables_in_timeline[label]:
                source_frame_data = variables_in_timeline[label][0]
                new_frame = {
                    "time": time_index,
                    "content": source_frame_data.get('content'),
                    "type": source_frame_data.get('type')
                }
            else:
                new_frame = {
                    "time": time_index,
                    "content": {"value": 0, "easing": 0},
                    "type": 2
                }
            
            merged_variables_data[label].append(new_frame)

    # --- 5. 建立最終的輸出結構 ---
    final_variable_list = []
    for label, frame_list in merged_variables_data.items():
        if frame_list:
            frame_list.append({
                "time": num_frames,
                "content": None,
                "type": 0
            })
        final_variable_list.append({"label": label, "frameList": frame_list})

    output_data = {
        "id": "emote_timeline",
        "value": {
            "loopBegin": -1,
            "loopEnd": -1,
            # 【修正關鍵】根據您的要求，將 lastTime 固定為 -1
            "lastTime": -1,
            "variableList": final_variable_list,
            "diff": original_timelines[0].get('diff', 0), 
            "label": "merged_timeline"
        }
    }

    # --- 6. 寫入新的 JSON 檔案 ---
    base_name = os.path.splitext(input_path)[0]
    output_path = f"{base_name}_converted.json"
    
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
        merge_timelines(input_file_path)
    else:
        print("使用方式：請將要轉換的 JSON 檔案拖曳到這個 .py 檔案的圖示上。")
    
    os.system("pause")