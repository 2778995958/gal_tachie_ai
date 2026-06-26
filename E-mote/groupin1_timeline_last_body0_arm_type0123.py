import sys
import json
import os

def merge_timelines(input_path):
    """
    將包含多個時間軸的 JSON 檔案合併。
    最新動態長度修正版：
    1. 結構：將「最後一個」時間軸複製一份放在最前面。
    2. 過濾：只保留 'face'、'fade' 與 'arm_type' 標籤。
    3. 彈性：【核心修改】時間與總長度完全跟隨 arm_list 動態計算，不再留空、不再綁定4組。
    """
    
    # 💡 【在這邊修改你要的 arm_type 順序與組合】
    # 例如：[0, 1] 就只會跑2組；改為 [1] 就只會跑1組且從第0格開始！
    arm_list = [1] 
    
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
    
    all_labels.add('arm_type')
    sorted_labels = sorted(list(all_labels))

    # 在最外層宣告容器，供多組動作連續串接
    merged_variables_data = {label: [] for label in sorted_labels}

    # --- 4. 核心轉換邏輯：動態首尾串聯 ---
    # loop_idx 代表第幾組動作（從 0 開始），arm_val 代表要賦予的屬性數值
    for loop_idx, arm_val in enumerate(arm_list):
        for time_index, timeline in enumerate(processed_timelines):
            
            # 【關鍵修正】改用 loop_idx 計算全域時間點，消滅前面的空白斷層
            global_time = (loop_idx * single_loop_frames) + time_index

            variables_in_timeline = {
                var['label']: var.get('frameList', []) 
                for var in timeline.get('variableList', []) if 'label' in var
            }

            for label in sorted_labels:
                # 白名單過濾：只留 face, fade, arm_type
                if not (label.startswith('face') or label.startswith('fade') or label == 'arm_type'):
                    continue
                
                # 如果是 arm_type，強制寫入當前組別設定的 arm_val
                if label == 'arm_type':
                    new_frame = {
                        "time": global_time,
                        "content": {"value": arm_val, "easing": 0},
                        "type": 2
                    }
                    merged_variables_data[label].append(new_frame)
                    continue

                # 其餘 face 與 fade 的智慧擷取與時間重對齊
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

    # --- 5. 建立最終的輸出結構與總結尾標記 ---
    # 【關鍵修正】根據 arm_list 的實際長度動態計算總結尾時間
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
    output_path = f"{base_name}_converted.json"
    
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