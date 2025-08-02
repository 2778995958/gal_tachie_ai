import os
import shutil

def organize_folders_within(parent_dir):
    """
    在指定的父目錄 (parent_dir) 中，將其下一層的子資料夾
    整理到 '1', '2', '3' 資料夾中。

    Args:
        parent_dir (str): 要進行整理的資料夾路徑。
    """
    print(f"--- 正在處理資料夾: [{parent_dir}] ---")

    # --- 步驟 1: 在父目錄中建立目標資料夾 ---
    destination_names = ['1', '2', '3']
    for name in destination_names:
        path = os.path.join(parent_dir, name)
        if not os.path.exists(path):
            os.makedirs(path)
            # print(f"在 {parent_dir} 中建立了資料夾: {name}")

    # --- 步驟 2: 取得並排序該目錄下的子資料夾 ---
    try:
        all_items = os.listdir(parent_dir)
        # 篩選出所有子資料夾，並排除 '1', '2', '3' 本身
        subfolders_to_organize = [
            f for f in all_items 
            if os.path.isdir(os.path.join(parent_dir, f)) and f not in destination_names
        ]
        
        subfolders_to_organize.sort()

        if not subfolders_to_organize:
            print("找不到可供整理的子資料夾，跳過。")
            return

    except FileNotFoundError:
        print(f"錯誤：找不到路徑 '{parent_dir}'。")
        return

    # --- 步驟 3: 分組並移動資料夾 ---
    for i in range(0, len(subfolders_to_organize), 3):
        group = subfolders_to_organize[i:i+3]

        for index, folder_name in enumerate(group):
            # 組內的順序 (0, 1, 2) 對應到目標資料夾名稱 ('1', '2', '3')
            dest_folder_name = destination_names[index]
            
            source_path = os.path.join(parent_dir, folder_name)
            destination_path = os.path.join(parent_dir, dest_folder_name, folder_name)

            try:
                shutil.move(source_path, destination_path)
                print(f"  已移動 '{folder_name}' -> '{dest_folder_name}/{folder_name}'")
            except Exception as e:
                print(f"  移動 '{source_path}' 時發生錯誤: {e}")

    print(f"--- 完成處理: [{parent_dir}] ---\n")


def process_all_main_folders(root_dir='.'):
    """
    遍歷根目錄下的所有主資料夾，並對每一個都執行整理。
    """
    print("程式開始，準備遍歷所有主要資料夾...")
    
    # 取得根目錄下所有項目，篩選出資料夾
    try:
        main_folders = [
            f for f in os.listdir(root_dir) 
            if os.path.isdir(os.path.join(root_dir, f))
        ]
        
        if not main_folders:
            print("在根目錄下找不到任何主要資料夾可供處理。")
            return

        # 對每一個主資料夾，執行內部分類函式
        for folder in main_folders:
            main_folder_path = os.path.join(root_dir, folder)
            organize_folders_within(main_folder_path)
            
        print("全部處理完畢！")

    except FileNotFoundError:
        print(f"錯誤：找不到根目錄 '{root_dir}'。")


# --- 執行主程式 ---
if __name__ == "__main__":
    # 將 '.' 改成你的專案根目錄，如果 .py 檔就放在根目錄，則不需要改
    process_all_main_folders(root_dir='.')
