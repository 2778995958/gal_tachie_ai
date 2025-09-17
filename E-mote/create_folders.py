import os

# ===================================================================
# --- 設定區：請在這裡修改數字 ---
# 你可以自由更改下面的數字來決定要建立哪些編號的資料夾

START_NUMBER = 1    # 子資料夾的【起始】編號
END_NUMBER = 4     # 子資料夾的【結束】編號 (會包含這個數字)

# --- 設定結束 ---
# ===================================================================


def create_folders_with_subdirs(root_directory='.'):
    """
    在指定的根目錄及其所有子目錄中，為每個 .mmo 檔案建立一個對應的主資料夾，
    並在主資料夾內建立設定範圍的數字子資料夾。
    """
    print(f"正在從 '{os.path.abspath(root_directory)}' 開始掃描...")
    print(f"設定：將為每個主資料夾建立從 {START_NUMBER} 到 {END_NUMBER} 的子資料夾。")
    print("-" * 30)

    # 建立要執行的數字範圍 (+1 是因為 range 的結束值是不包含的)
    subdirs_range = range(START_NUMBER, END_NUMBER + 1)
    
    # os.walk 會遍歷指定目錄下的所有資料夾和檔案
    for dirpath, _, filenames in os.walk(root_directory):
        for filename in filenames:
            if filename.endswith('.mmo'):
                try:
                    # 取得主資料夾名稱
                    base_name = filename.split('.')[0]
                    folder_name = base_name.replace('_', '')
                    new_folder_path = os.path.join(dirpath, folder_name)
                    
                    # 建立主資料夾
                    os.makedirs(new_folder_path, exist_ok=True)
                    print(f"找到檔案：'{os.path.join(dirpath, filename)}' -> 已建立主資料夾：'{new_folder_path}'")
                    
                    # 在主資料夾內建立數字子資料夾
                    for i in subdirs_range:
                        numbered_subfolder_path = os.path.join(new_folder_path, str(i))
                        os.makedirs(numbered_subfolder_path, exist_ok=True)
                    
                    print(f"  └─ 已成功建立 {START_NUMBER} 到 {END_NUMBER} 的子資料夾。")

                except IndexError:
                    print(f"無法處理檔案名稱：'{filename}'，因為它不包含 '.'。")
                except Exception as e:
                    print(f"處理檔案 '{filename}' 時發生錯誤：{e}")

    print("-" * 30)
    print("\n處理完成。")


# 執行主函數
if __name__ == "__main__":
    create_folders_with_subdirs()