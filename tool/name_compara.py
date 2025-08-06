import os
import shutil
import sys # 匯入 sys 模組來處理命令列參數

def find_and_move_duplicates_by_filename(old_dir, new_dir, dup_dir):
    """
    主函式，尋找 old_dir 中與 new_dir 內檔案同名的檔案（忽略大小寫），並將其移動。
    """
    # --- 步驟 1: 建立目標資料夾 ---
    if not os.path.exists(dup_dir):
        os.makedirs(dup_dir)
        print(f"已建立資料夾: {dup_dir}")

    # --- 步驟 2: 掃描新資料夾，建立檔名快取 ---
    print(f"\n步驟 1: 正在掃描 {new_dir} 中的檔案並建立檔名快取...")
    new_files_filenames = set()
    for root, _, files in os.walk(new_dir):
        for filename in files:
            # ★ 修改點：將檔名轉成小寫再加入集合，以忽略大小寫
            new_files_filenames.add(filename.lower())
    print(f"完成掃描。在新資料夾中找到 {len(new_files_filenames)} 個獨特的檔名。")

    # --- 步驟 3: 掃描舊資料夾，比對檔名並移動 ---
    print(f"\n步驟 2: 正在檢查 {old_dir} 中的檔案...")
    moved_count = 0
    processed_count = 0
    for root, _, files in os.walk(old_dir):
        # 避免掃描到我們自己建立的 dup_dir 資料夾
        if os.path.abspath(root).startswith(os.path.abspath(dup_dir)):
            continue

        for filename in files:
            processed_count += 1
            file_path = os.path.join(root, filename)
            
            # ★ 修改點：比對時，也將檔名轉成小寫
            # 核心邏輯：檢查檔名的小寫版本是否存在於新資料夾的檔名集合中
            if filename.lower() in new_files_filenames:
                # 計算檔案在 old_dir 中的相對路徑
                relative_subdir = os.path.relpath(root, old_dir)

                # 建立在 dup_dir 中對應的目標資料夾結構
                destination_dir = os.path.join(dup_dir, relative_subdir)
                if not os.path.exists(destination_dir):
                    os.makedirs(destination_dir)

                # 組合出最終的檔案目標路徑
                destination_path = os.path.join(destination_dir, filename)
                
                # 處理目標位置已存在同名檔案的邏輯
                counter = 1
                original_destination_path = destination_path
                while os.path.exists(destination_path):
                    name, ext = os.path.splitext(os.path.basename(original_destination_path))
                    destination_path = os.path.join(destination_dir, f"{name}_{counter}{ext}")
                    counter += 1

                try:
                    print(f"找到相同檔名: '{file_path}' -> 將移動至 {destination_path}")
                    shutil.move(file_path, destination_path)
                    moved_count += 1
                except Exception as e:
                    print(f"錯誤：移動檔案 '{file_path}' 時發生錯誤: {e}")

    print(f"\n處理完成！")
    print(f"總共檢查了 {processed_count} 個舊檔案。")
    print(f"移動了 {moved_count} 個相同檔名的檔案到 {dup_dir}。")

# --- 主程式執行區塊 ---
if __name__ == "__main__":
    # 檢查命令列參數數量是否正確
    if len(sys.argv) != 3:
        print("錯誤：參數數量不正確！")
        print("使用方式: python script_name.py <舊資料夾路徑> <新資料夾路徑>")
        print("範例: python script_name.py E:/image D:/img")
        sys.exit(1)

    # 從命令列取得路徑
    old_folder = sys.argv[1]
    new_folder = sys.argv[2]

    # 檢查提供的路徑是否存在且為資料夾
    if not os.path.isdir(old_folder):
        print(f"錯誤: 舊資料夾路徑不存在或不是一個資料夾 -> {old_folder}")
        sys.exit(1)
        
    if not os.path.isdir(new_folder):
        print(f"錯誤: 新資料夾路徑不存在或不是一個資料夾 -> {new_folder}")
        sys.exit(1)

    print("--- 檔案同名比對與移動工具 (忽略大小寫) ---")
    print(f"舊資料夾 (來源): {old_folder}")
    print(f"新資料夾 (比對目標): {new_folder}")
    
    # 將重複檔案資料夾設定在 old_folder 內部，並命名為 'dupimg'
    duplicate_folder = os.path.join(old_folder, 'dupimg')
    print(f"相同檔名的檔案將被移動至: {duplicate_folder} (並保持原始資料夾結構)")

    # 執行主程式
    find_and_move_duplicates_by_filename(old_folder, new_folder, duplicate_folder)
