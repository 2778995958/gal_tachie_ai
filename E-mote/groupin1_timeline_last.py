import sys
import json
import os

def merge_timelines(input_path):
    """
    將包含多個時間軸的 JSON 檔案合併。
    修正版：
    1. 結構：將「最後一個」時間軸複製一份放在最前面。
    2. 內容：智慧抓取「最後一個有效數值」(忽略 type 0 的結束標記)。
    3. 安全性：修復了遇到空 frameList (如 fade_a) 會報錯的問題。
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

    except Exception as e:
        print(f"讀取檔案時發生錯誤：{e}")
        return False

    # --- 2. 根據規則建立處理列表：將【最後一個】複製一份放到最前面 ---
    # 使用 [-1] 獲取列表最後一個時間軸
    processed_timelines = [original_timelines[-1]] + original_timelines
    
    num_frames = len(processed_timelines)
    print(f"發現 {len(original_timelines)} 個時間軸，處理後共 {num_frames} 個影格。")

    # --- 3. 準備合併資料 ---
    all_labels = set()
    for timeline in original_timelines:
        for variable in timeline.get('variableList', []):
            if 'label' in variable:
                all_labels.add(variable['label'])

    sorted_labels = sorted(list(all_labels))
    merged_variables_data = {label: [] for label in sorted_labels}

    # --- 4. 核心轉換邏輯 (加入防錯機制) ---
    for time_index, timeline in enumerate(processed_timelines):
        variables_in_timeline = {
            var['label']: var.get('frameList', []) 
            for var in timeline.get('variableList', []) if 'label' in var
        }

        for label in sorted_labels:
            target_frame = None
            
            # 【關鍵修正】：尋找最後一個「有效」的影格
            if label in variables_in_timeline:
                frames = variables_in_timeline[label]
                
                # 如果清單不是空的，我們從後面開始往前找 (reversed)
                if frames:
                    for frame in reversed(frames):
                        # 條件：Type不等於0 (0通常是結束標記) 且 content 不是 null
                        if frame.get('type') != 0 and frame.get('content') is not None:
                            target_frame = frame
                            break
                    
                    # 如果全部都是 Type 0 (極少見)，或者是空的，就保持 target_frame 為 None

            # 建立新影格
            if target_frame:
                new_frame = {
                    "time": time_index,
                    "content": target_frame.get('content'),
                    "type": target_frame.get('type')
                }
            else:
                # 如果是空清單 (如 fade_a) 或找不到有效值，給予預設值 0
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
            # 加入結束標記
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
            "lastTime": -1,
            "variableList": final_variable_list,
            # 使用最後一個時間軸的 diff (若無則用0)
            "diff": original_timelines[-1].get('diff', 0), 
            "label": "merged_last_valid"
        }
    }

    # --- 6. 寫入檔案 ---
    base_name = os.path.splitext(input_path)[0]
    output_path = f"{base_name}_converted.json"
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=1)
        print(f"轉換成功！結果已儲存至 '{output_path}'")
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
        print("使用方式：請將 JSON 檔案拖曳到這個 .py 檔案的圖示上。")
    
    os.system("pause")