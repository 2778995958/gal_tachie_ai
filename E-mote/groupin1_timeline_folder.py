import sys
import json
import os

def find_timelines(nodes):
    """
    遞迴地從巢狀結構中尋找並提取所有的時間軸物件。
    """
    timelines = []
    for item in nodes:
        if item.get("type") == "folder" and "children" in item:
            timelines.extend(find_timelines(item["children"]))
        elif "variableList" in item:
            timelines.append(item)
    return timelines

def merge_timelines_stacked(input_path):
    """
    將多個時間軸以「疊加」方式合併，並確保輸出的第0格和第1格內容相同。
    """
    # --- 1. 讀取並驗證輸入檔案 ---
    print(f"開始處理檔案：'{input_path}'")
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        original_timelines = find_timelines(data['value'])
        
        if not original_timelines:
            print(f"錯誤：在檔案 '{input_path}' 中找不到任何有效的時間軸資料。")
            return False

    except Exception as e:
        print(f"讀取檔案時發生錯誤：{e}")
        return False

    print(f"成功找到 {len(original_timelines)} 個獨立時間軸，準備進行疊加。")

    # --- 2. 準備合併資料 ---
    all_labels = set()
    for timeline in original_timelines:
        for variable in timeline.get('variableList', []):
            if 'label' in variable:
                all_labels.add(variable['label'])

    sorted_labels = sorted(list(all_labels))
    merged_variables_data = {label: [] for label in sorted_labels}
    
    default_content = {"value": 0, "easing": 0}
    last_known_frame = {
        label: {"content": default_content, "type": 2}
        for label in sorted_labels
    }

    # --- ★ 修改點 1：時間偏移初始值改為 1 ---
    # 這樣可以空出 time: 0 的位置給我們複製第 1 格的內容
    time_offset = 1
    print("套用規則：最終輸出的第0格與第1格將會相同。")

    # --- 3. 核心轉換邏輯：疊加時間軸 ---
    for i, timeline in enumerate(original_timelines):
        timeline_duration = timeline.get('lastTime', 0)
        print(f"  - 處理第 {i+1}/{len(original_timelines)} 個時間軸 (長度: {timeline_duration})...")
        
        variables_in_timeline = {
            var['label']: var.get('frameList', [])
            for var in timeline.get('variableList', [])
        }

        for label in sorted_labels:
            if label in variables_in_timeline:
                frame_list = sorted(variables_in_timeline[label], key=lambda x: x.get('time', 0))
                
                if not frame_list or frame_list[0].get('time', 0) != 0:
                    merged_variables_data[label].append({
                        "time": time_offset,
                        "content": last_known_frame[label]['content'],
                        "type": last_known_frame[label]['type']
                    })

                for frame in frame_list:
                    if frame.get('type', 0) == 0:
                        continue
                    
                    new_frame = {
                        "time": frame['time'] + time_offset,
                        "content": frame['content'],
                        "type": frame['type']
                    }
                    merged_variables_data[label].append(new_frame)
                    last_known_frame[label] = new_frame
            else:
                merged_variables_data[label].append({
                    "time": time_offset,
                    "content": last_known_frame[label]['content'],
                    "type": last_known_frame[label]['type']
                })
        
        time_offset += timeline_duration

    # --- 4. 建立最終的輸出結構 ---
    print(f"所有時間軸疊加完畢，最終總長度為: {time_offset}")
    final_variable_list = []
    for label, frame_list in merged_variables_data.items():
        # --- ★ 修改點 2：插入第 0 格 ---
        # 複製第 1 格的內容到第 0 格
        if frame_list:
            # 找到時間點最小的影格（也就是新的第 1 格）
            first_frame = min(frame_list, key=lambda x: x['time'])
            frame_zero = {
                "time": 0,
                "content": first_frame['content'],
                "type": first_frame['type']
            }
            # 將第 0 格插入到列表最前面
            frame_list.insert(0, frame_zero)

        # 清理可能存在的重複時間點影格，只保留最後一個
        unique_frames = {frame['time']: frame for frame in frame_list}
        sorted_unique_frames = sorted(unique_frames.values(), key=lambda x: x['time'])

        # 在總時間軸的末端為每個參數加上結束標記
        sorted_unique_frames.append({
            "time": time_offset,
            "content": None,
            "type": 0
        })
        final_variable_list.append({"label": label, "frameList": sorted_unique_frames})

    output_data = {
        "id": "emote_timeline",
        "value": {
            "loopBegin": -1,
            "loopEnd": -1,
            "lastTime": time_offset,
            "variableList": final_variable_list,
            "diff": original_timelines[0].get('diff', 0), 
            "label": "merged_timeline_stacked"
        }
    }

    # --- 5. 寫入新的 JSON 檔案 ---
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
        merge_timelines_stacked(input_file_path)
    else:
        print("使用方式：請將要轉換的 JSON 檔案拖曳到這個 .py 檔案的圖示上。")
    
    os.system("pause")