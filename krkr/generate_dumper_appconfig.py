import os
import sys
import glob

def generate_tjs_from_txts(input_files):
    """
    讀取多個 Kirikiri 的圖層定義 .txt 檔案，
    並將它們合併成一個用於匯出所有圖層檔案和關聯 .sinfo 檔案的 TJS 腳本。
    """
    # --- 1. 基本設定 ---
    image_extension = ".tlg"
    sinfo_extension = ".sinfo"
    output_tjs_path = "appconfig.tjs"

    # --- 2. 準備 TJS 腳本內容 ---
    tjs_script_content = []
    total_files_to_dump = 0
    
    # 使用集合 (set) 來避免重複加入相同的檔名
    files_to_dump = set()

    # --- 3. 遍歷所有輸入的 .txt 檔案 ---
    for input_txt_path in input_files:
        if not os.path.exists(input_txt_path):
            print(f"警告：找不到檔案 '{input_txt_path}'，已跳過。")
            continue

        print(f"正在處理 '{input_txt_path}'...")
        
        base_filename_full = os.path.splitext(os.path.basename(input_txt_path))[0]
        
        # *** 新增的邏輯：處理 .sinfo 檔案 ***
        # 取得第一個底線前的部分作為 sinfo 檔名
        sinfo_base_name = base_filename_full.split('_')[0]
        files_to_dump.add(f"{sinfo_base_name}{sinfo_extension}")
        files_to_dump.add(f"{sinfo_base_name}{sinfo_extension}.txt") # 也嘗試 .sinfo.txt

        try:
            with open(input_txt_path, 'r', encoding='utf-8-sig') as f_in:
                headers = f_in.readline().strip().split('\t')
                
                try:
                    layer_id_col_index = headers.index('layer_id')
                    layer_type_col_index = headers.index('#layer_type')
                except ValueError:
                    print(f"警告：'{input_txt_path}' 缺少必要的欄位，已跳過。")
                    continue

                for line in f_in:
                    if not line.strip() or '\t' not in line:
                        continue
                    
                    columns = line.strip().split('\t')
                    
                    if len(columns) > max(layer_type_col_index, layer_id_col_index):
                        layer_type = columns[layer_type_col_index]
                        layer_id = columns[layer_id_col_index]

                        if layer_type == '0' and layer_id:
                            image_filename = f"{base_filename_full}_{layer_id}{image_extension}"
                            files_to_dump.add(image_filename)
        except Exception as e:
            print(f"處理 '{input_txt_path}' 時發生錯誤: {e}")

    # --- 4. 根據收集到的檔名清單產生 TJS 腳本 ---
    for filename in sorted(list(files_to_dump)): # 排序讓腳本內容更有條理
        tjs_block = (
            f'try {{ Scripts.evalStorage("{filename}"); }}\n'
            f'catch{{}}'
        )
        tjs_script_content.append(tjs_block)

    # --- 5. 寫入合併後的 TJS 檔案 ---
    if not tjs_script_content:
        print("警告：沒有找到任何可匯出的檔案。")
        return
        
    with open(output_tjs_path, 'w', encoding='utf-16') as f_out:
        f_out.write("// Kirikiri Batch Dumper Script (with .sinfo support)\n")
        f_out.write(f"// Generated from {len(input_files)} file(s).\n\n")
        f_out.write("\n".join(tjs_script_content))
        f_out.write("\n\nSystem.exit();\n")

    print("="*30)
    print(f"成功！已產生 '{output_tjs_path}'。")
    print(f"總共將嘗試匯出 {len(tjs_script_content)} 個檔案。")
    print("請將此檔案放到遊戲的 'unencrypted' 資料夾內再執行遊戲。")


# --- 腳本執行入口 ---
if __name__ == "__main__":
    if len(sys.argv) > 1:
        input_files = []
        for arg in sys.argv[1:]:
            input_files.extend(glob.glob(arg))
        
        if not input_files:
            print("錯誤：找不到任何符合的 .txt 檔案。")
        else:
            generate_tjs_from_txts(input_files)
    else:
        print("請提供要轉換的 .txt 檔案路徑。")
        print("用法 1 (指定多個檔案): python generate_batch_dumper.py file1.txt file2.txt")

        print("用法 2 (使用萬用字元): python generate_batch_dumper.py *.txt")
