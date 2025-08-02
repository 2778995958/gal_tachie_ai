import os
import shutil

# --- 參數設定 ---
# 你可以根據需求修改來源資料夾的路徑
# '.' 代表目前程式碼所在的資料夾
SOURCE_DIRECTORY = '.'

def organize_folders():
    """
    將來源資料夾中的子資料夾，依名稱排序後，
    每3個一組，分別移動到 '1', '2', '3' 資料夾中。
    """
    print("程式開始執行...")

    # --- 步驟 1: 建立目標資料夾 ---
    # 目標資料夾的名稱列表
    destination_folders = ['1', '2', '3']
    for folder_name in destination_folders:
        # 組合出完整的目標資料夾路徑
        path = os.path.join(SOURCE_DIRECTORY, folder_name)
        # 檢查資料夾是否存在，若否則建立
        if not os.path.exists(path):
            os.makedirs(path)
            print(f"已建立目標資料夾: {path}")

    # --- 步驟 2: 取得並排序所有來源資料夾 ---
    try:
        # 列出所有在來源路徑下的項目，並篩選出資料夾
        all_items = os.listdir(SOURCE_DIRECTORY)
        # 使用 os.path.isdir 來確認是否為資料夾，並排除目標資料夾本身
        source_folders = [f for f in all_items if os.path.isdir(os.path.join(SOURCE_DIRECTORY, f)) and f not in destination_folders]
        
        # 依名稱排序
        source_folders.sort()

        if not source_folders:
            print("在指定的路徑下找不到任何要處理的資料夾。")
            return

        print(f"找到 {len(source_folders)} 個資料夾準備處理。")

    except FileNotFoundError:
        print(f"錯誤：找不到指定的來源路徑 '{SOURCE_DIRECTORY}'。請確認路徑是否正確。")
        return

    # --- 步驟 3: 分組並移動資料夾 ---
    # 使用 range 的第三個參數 (step) 來一次跳3個
    for i in range(0, len(source_folders), 3):
        # 從排序好的列表中取出3個資料夾成為一組
        group = source_folders[i:i+3]

        # 遍歷這一組中的資料夾
        for index, folder_name in enumerate(group):
            # 原始路徑
            source_path = os.path.join(SOURCE_DIRECTORY, folder_name)
            # 根據組內的順序 (0, 1, 2) 決定目標資料夾 (1, 2, 3)
            # index 是 0, 1, 2...，對應的目標資料夾是 '1', '2', '3'
            destination_path = os.path.join(SOURCE_DIRECTORY, destination_folders[index], folder_name)

            try:
                # 移動資料夾
                shutil.move(source_path, destination_path)
                print(f"已移動 '{source_path}' -> '{destination_path}'")
            except Exception as e:
                print(f"移動 '{source_path}' 時發生錯誤: {e}")
    
    print("所有資料夾處理完畢！")


# --- 執行主程式 ---
if __name__ == "__main__":
    organize_folders()