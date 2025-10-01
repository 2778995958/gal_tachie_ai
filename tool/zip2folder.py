import os
import re
import zipfile
import shutil

# --- 設定 ---

# 輸出資料夾的名稱
ZIPPED_FOLDER_NAME = 'zipped'

# --- 設定結束 ---

def natural_sort_key(s):
    """
    提供一個用於 sorted() 的 key，實現自然排序 (例如 'folder10' 會在 'folder2' 之後)。
    """
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split('([0-9]+)', s)]

def add_folder_to_zip(zipf, folder_path):
    """
    將整個資料夾 (包含其下的所有檔案和子資料夾) 加入到 ZipFile 物件中。
    
    :param zipf: zipfile.ZipFile 的實例。
    :param folder_path: 要加入壓縮檔的資料夾路徑。
    """
    base_folder_name = os.path.basename(folder_path)
    for root, _, files in os.walk(folder_path):
        for file in files:
            file_path = os.path.join(root, file)
            # 建立在 zip 檔內的相對路徑，以保留資料夾結構
            archive_name = os.path.join(base_folder_name, os.path.relpath(file_path, folder_path))
            zipf.write(file_path, arcname=archive_name)

def main():
    """
    主執行函數：尋找同層級的所有資料夾，並將它們兩兩一組進行壓縮。
    """
    print("--- 開始執行批量歸檔任務 (模式: 僅儲存) ---")
    
    script_dir = os.getcwd()
    dest_path = os.path.join(script_dir, ZIPPED_FOLDER_NAME)
    
    if os.path.exists(dest_path):
        print(f"偵測到舊的輸出資料夾 '{ZIPPED_FOLDER_NAME}'，正在清空...")
        shutil.rmtree(dest_path)
    os.makedirs(dest_path, exist_ok=True)
    
    try:
        source_folders = [item for item in os.listdir(script_dir)
                          if os.path.isdir(os.path.join(script_dir, item)) and item != ZIPPED_FOLDER_NAME]
    except Exception as e:
        print(f"讀取資料夾列表時發生錯誤: {e}")
        return

    sorted_folders = sorted(source_folders, key=natural_sort_key)

    if not sorted_folders:
        print("未在當前目錄下找到任何需要處理的資料夾。")
        print("請確保此腳本與您想歸檔的資料夾放在一起。")
        return

    print(f"將在 '{script_dir}' 中尋找資料夾...")
    print(f"找到 {len(sorted_folders)} 個待處理資料夾: {', '.join(sorted_folders)}")
    print(f"所有歸檔檔將儲存至: {dest_path}")
    print("-" * 30)

    for i in range(0, len(sorted_folders), 2):
        folders_to_zip = sorted_folders[i:i+2]
        
        zip_base_name = "_".join(folders_to_zip)
        zip_filename = f"{zip_base_name}.zip"
        zip_path = os.path.join(dest_path, zip_filename)
        
        print(f">> 正在建立歸檔檔: {zip_filename}")
        
        try:
            # --- 主要修改處 ---
            # 將壓縮模式從 ZIP_DEFLATED 改為 ZIP_STORED
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_STORED) as zipf:
                for folder_name in folders_to_zip:
                    folder_path = os.path.join(script_dir, folder_name)
                    print(f"   - 正在加入資料夾: {folder_name}")
                    add_folder_to_zip(zipf, folder_path)
            print(f"   > 成功建立: {zip_filename}")
        except Exception as e:
            print(f"   > 建立失敗: {e}")
            if os.path.exists(zip_path):
                os.remove(zip_path)

    print("-" * 30)
    print("--- 所有批量任務完成 ---")

if __name__ == "__main__":
    main()