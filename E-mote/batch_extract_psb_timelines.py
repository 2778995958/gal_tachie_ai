import sys
import json
import os

def extract_from_dict(d, collected_poses):
    """
    深度遞迴掃描劇本結構，尋找所有 PSB 檔案的變數快照
    """
    if not isinstance(d, dict):
        return
    
    # 檢查是否符合劇本中的 redraw -> imageFile -> file (*.psb) 與 options -> variables 結構
    if "file" in d and isinstance(d["file"], str) and d["file"].endswith(".psb"):
        psb_name = d["file"]
        options = d.get("options")
        if isinstance(options, dict) and "variables" in options:
            variables = options["variables"]
            if isinstance(variables, dict) and variables:
                # 嚴格白名單過濾：只留 face, fade, arm_type
                filtered_vars = {}
                for k, v in variables.items():
                    if k.startswith("face") or k.startswith("fade") or k == "arm_type":
                        filtered_vars[k] = v
                
                if filtered_vars:
                    if psb_name not in collected_poses:
                        collected_poses[psb_name] = []
                    
                    # 排序 Key 以確保內容一致性，進行精準去重
                    serialized = json.dumps(filtered_vars, sort_keys=True)
                    if serialized not in [item[0] for item in collected_poses[psb_name]]:
                        collected_poses[psb_name].append((serialized, filtered_vars))
                        
    # 繼續向內層字典與列表遞迴搜尋
    for v in d.values():
        if isinstance(v, dict):
            extract_from_dict(v, collected_poses)
        elif isinstance(v, list):
            extract_from_list(v, collected_poses)

def extract_from_list(l, collected_poses):
    """
    遞迴掃描列表結構
    """
    if not isinstance(l, list):
        return
    for item in l:
        if isinstance(item, dict):
            extract_from_dict(item, collected_poses)
        elif isinstance(item, list):
            extract_from_list(item, collected_poses)

def main():
    target_dir = os.getcwd()
    files_to_process = []

    # --- 1. 判斷輸入路徑（支援拖曳劇本資料夾、劇本檔案或直接執行） ---
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if os.path.isdir(arg):
            target_dir = arg
            files_to_process = [os.path.join(target_dir, f) for f in os.listdir(target_dir) if f.endswith('.json')]
        elif os.path.isfile(arg):
            files_to_process = [arg]
            target_dir = os.path.dirname(arg)
    else:
        files_to_process = [os.path.join(target_dir, f) for f in os.listdir(target_dir) if f.endswith('.json')]

    # 防呆過濾：跳過我們自己產出的轉換結果檔案
    files_to_process = [
        f for f in files_to_process 
        if not (f.endswith('_combined_list.json') or f.endswith('_converted.json'))
    ]

    if not files_to_process:
        print("❌ 未找到任何需要處理的劇本 JSON 檔案。")
        os.system("pause")
        return

    print(f"🚀 開始一鍵分析共 {len(files_to_process)} 個劇本檔案並串接單一時間軸...")

    # 全域收集容器
    all_collected_poses = {}

    # --- 2. 遞迴掃描劇本並去重 ---
    for file_path in files_to_process:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            extract_from_dict(data, all_collected_poses)
        except Exception as e:
            print(f"❌ 讀取劇本 {os.path.basename(file_path)} 失敗: {e}")

    print("\n--- 提取去重完畢，開始串接成單一長時間軸 ---")

    # --- 3. 遍歷結果，依照你提供的 .py 邏輯串接時間軸 ---
    for psb_name, unique_poses_tuples in all_collected_poses.items():
        clean_psb_name = os.path.splitext(psb_name)[0]
        
        # 轉換出純變數字典的清單
        unique_poses = [item[1] for item in unique_poses_tuples]
        if not unique_poses:
            continue
            
        print(f"\n角色 PSB: 【{psb_name}】共發現 {len(unique_poses)} 個不重複動作")
        
        # 💡 【核心邏輯 1】比照範本結構：將「最後一個」動作複製一份放在最前面
        processed_timelines = [unique_poses[-1]] + unique_poses
        num_frames = len(processed_timelines)
        
        # 收集所有動作中出現過的全部標籤
        all_labels = set()
        for pose in processed_timelines:
            all_labels.update(pose.keys())
            
        sorted_labels = sorted(list(all_labels))
        merged_variables_data = {label: [] for label in sorted_labels}
        
        # 💡 【核心邏輯 2】循序轉換：將每個動作分配到對應的時間點 (Time 0, 1, 2...)
        for time_index, pose_vars in enumerate(processed_timelines):
            for label in sorted_labels:
                # 取得當前動作中該標籤的值，若無則預設補 0
                val = pose_vars.get(label, 0)
                
                new_frame = {
                    "time": time_index,
                    "content": {"value": val, "easing": 0},
                    "type": 2
                }
                merged_variables_data[label].append(new_frame)
                
        # 💡 【核心邏輯 3】建立最終的輸出結構與總結尾標記
        final_variable_list = []
        for label in sorted_labels:
            frame_list = merged_variables_data[label]
            # 加入結束標記
            frame_list.append({
                "time": num_frames,
                "content": None,
                "type": 0
            })
            # 完美複製範本欄位順序：label 在前，frameList 在後
            final_variable_list.append({"label": label, "frameList": frame_list})
            
        # 完美複製 groupin1_timeline_last_body0.py 的外殼
        output_data = {
            "id": "emote_timeline",
            "value": {
                "loopBegin": -1,
                "loopEnd": -1,
                "lastTime": -1,
                "variableList": final_variable_list,
                "diff": 0, 
                "label": "merged_last_valid"
            }
        }
        
        # 輸出檔名，例如：ちえ_橫_普通c1_converted.json
        output_filename = f"{clean_psb_name}_converted.json"
        output_path = os.path.join(target_dir, output_filename)
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                # 💡 使用 indent=1 對齊你提供的檔案縮排格式
                json.dump(output_data, f, ensure_ascii=False, indent=1)
            print(f"  ➡️  [一鍵直出成功] 已產生連續時間軸: '{output_filename}' (共 {num_frames} 個影格)")
        except Exception as e:
            print(f"  ❌ 寫入檔案 {output_filename} 失敗: {e}")

    print("\n所有劇本的一鍵時間軸序列化工作已全部完成！")
    os.system("pause")

if __name__ == "__main__":
    main()