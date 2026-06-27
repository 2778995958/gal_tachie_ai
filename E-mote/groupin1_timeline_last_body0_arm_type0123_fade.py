import sys
import json
import os

def merge_timelines(input_path):
    """
    將包含多個時間軸的 JSON 檔案合併。
    終極客製化 + 雙重 Auto 版
    """
    
    # 💡 【在這邊修改你要的 arm_type 順序與組合】
    # 現在這裡也可以填入 "auto" 了！它會自動抓取原本檔案的 arm_type 數值。
    # 例如：arm_list = ["auto"] 或是 arm_list = [1, "auto"]
    arm_list = ["auto"] 
    
    # 💡 【在這邊設定你想要的 fade 客製化數值】
    # 填入數字（如 0, 1）：強制覆蓋。
    # 填入 "auto"：交由系統自動讀取原始檔案數值（若無則補 0）。
    fade_custom_settings = {
        "fade_a": "auto",
        "fade_b": "auto",
    }
    
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
    processed_timelines = [original_timelines[-1]] + original_timelines
    single_loop_frames = len(processed_timelines)
    print(f"發現 {len(original_timelines)} 個時間軸，單次動作處理後共 {single_loop_frames} 個影格。")

    # --- 3. 準備所有標籤 ---
    all_labels = set()
    for timeline in original_timelines:
        for variable in timeline.get('variableList', []):
            if 'label' in variable:
                all_labels.add(variable['label'])
    
    # 確保客製化的 fade 標籤一定會被包含在處理清單中
    for custom_label in fade_custom_settings.keys():
        all_labels.add(custom_label)
        
    all_labels.add('arm_type')
    sorted_labels = sorted(list(all_labels))

    # 在最外層宣告容器
    merged_variables_data = {label: [] for label in sorted_labels}

    # --- 4. 核心轉換邏輯 ---
    for loop_idx, arm_val in enumerate(arm_list):
        for time_index, timeline in enumerate(processed_timelines):
            
            global_time = (loop_idx * single_loop_frames) + time_index

            variables_in_timeline = {
                var['label']: var.get('frameList', []) 
                for var in timeline.get('variableList', []) if 'label' in var
            }

            for label in sorted_labels:
                # 白名單過濾
                if not (label.startswith('face') or label.startswith('fade') or label == 'arm_type'):
                    continue
                
                # 【優化】arm_type 判斷：只有當 arm_val 不是 "auto" 時才強制寫入固定值
                if label == 'arm_type' and arm_val != "auto":
                    new_frame = {
                        "time": global_time,
                        "content": {"value": arm_val, "easing": 0},
                        "type": 2
                    }
                    merged_variables_data[label].append(new_frame)
                    continue

                # 檢查是否為客製化的 fade 標籤，且排除 "auto"
                if label.startswith('fade') and label in fade_custom_settings and fade_custom_settings[label] != "auto":
                    custom_val = fade_custom_settings[label]
                    new_frame = {
                        "time": global_time,
                        "content": {"value": custom_val, "easing": 0},
                        "type": 2
                    }
                    merged_variables_data[label].append(new_frame)
                    continue

                # 這裡處理：face、設定為 "auto" 的 fade、以及當 arm_list 填了 "auto" 時的 arm_type
                target_frame = None
                if label in variables_in_timeline:
                    frames = variables_in_timeline[label]
                    if frames:
                        for frame in reversed(frames):
                            if frame.get('type') != 0 and frame.get('content') is not None:
                                target_frame = frame
                                break

                if target_frame:
                    new_frame = {
                        "time": global_time,
                        "content": target_frame.get('content'),
                        "type": target_frame.get('type')
                    }
                else:
                    new_frame = {
                        "time": global_time,
                        "content": {"value": 0, "easing": 0},
                        "type": 2
                    }
                
                merged_variables_data[label].append(new_frame)

    # --- 5. 建立最終的輸出結構 ---
    total_frames = len(arm_list) * single_loop_frames
    final_variable_list = []
    
    for label, frame_list in merged_variables_data.items():
        if frame_list:
            frame_list.append({
                "time": total_frames,
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
            "diff": original_timelines[-1].get('diff', 0), 
            "label": "merged_dynamic_extended"
        }
    }

    # --- 6. 寫入檔案 ---
    base_name = os.path.splitext(input_path)[0]
    output_path = f"{base_name}_fade_converted.json"
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=1)
        print(f"轉換成功！已動態產生共 {len(arm_list)} 組串接動作。結果已儲存至 '{output_path}'")
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