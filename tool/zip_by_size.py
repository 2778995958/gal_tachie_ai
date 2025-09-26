import os
import re
import zipfile

# --- 請在這裡修改設定 ---

# 每個 ZIP 檔的大小上限 (MB)
MAX_ZIP_SIZE_MB = 700

# 輸出資料夾的名稱
ZIPPED_FOLDER_NAME = 'zipped'

# --- 設定結束 ---


def natural_sort_key(s):
    """
    提供一個用於 sorted() 的 key，實現自然排序 (例如 'file10' 會在 'file2' 之後)。
    """
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split('([0-9]+)', s)]

def create_zip_archive(zip_path, source_folder, file_list):
    """
    根據提供的檔案列表，建立一個 ZIP 壓縮檔。
    """
    print(f"    正在建立 ZIP 檔: {os.path.basename(zip_path)} ({len(file_list)} 個檔案)...")
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for filename in file_list:
                file_path = os.path.join(source_folder, filename)
                zipf.write(file_path, arcname=filename)
        print(f"    > 成功建立: {os.path.basename(zip_path)}")
        return True
    except Exception as e:
        print(f"    > 建立失敗: {e}")
        return False

def process_folder(source_path, dest_path, base_zip_name, max_size_bytes):
    """
    處理單一資料夾內的所有檔案，將其分批壓縮。
    """
    try:
        all_files = [f for f in os.listdir(source_path) if os.path.isfile(os.path.join(source_path, f))]
        sorted_files = sorted(all_files, key=natural_sort_key)
        
        if not sorted_files:
            # 優化後的提示訊息
            print(f"  > 資料夾 '{base_zip_name}' 頂層沒有檔案 (可能只含子資料夾或為空)，已跳過。")
            return
            
        print(f"  找到 {len(sorted_files)} 個檔案，準備開始分批壓縮...")

    except Exception as e:
        print(f"  讀取檔案列表時發生錯誤: {e}")
        return

    zip_counter = 1
    current_zip_files = []
    current_zip_size = 0

    for filename in sorted_files:
        file_path = os.path.join(source_path, filename)
        file_size = os.path.getsize(file_path)

        if file_size > max_size_bytes:
            print(f"  警告：檔案 '{filename}' ({file_size / 1024 / 1024:.2f} MB) 本身就超過了 {MAX_ZIP_SIZE_MB} MB 的上限，將被跳過。")
            continue

        if current_zip_files and (current_zip_size + file_size > max_size_bytes):
            zip_filename = f"{base_zip_name}_{zip_counter}.zip"
            zip_path = os.path.join(dest_path, zip_filename)
            create_zip_archive(zip_path, source_path, current_zip_files)
            
            zip_counter += 1
            current_zip_files = []
            current_zip_size = 0

        current_zip_files.append(filename)
        current_zip_size += file_size

    if current_zip_files:
        zip_filename = f"{base_zip_name}_{zip_counter}.zip"
        zip_path = os.path.join(dest_path, zip_filename)
        create_zip_archive(zip_path, source_path, current_zip_files)

def main():
    """
    主執行函數：尋找同層級的所有資料夾並逐一處理。
    """
    print("--- 開始執行批量壓縮任務 ---")
    
    script_dir = os.getcwd()
    dest_path = os.path.join(script_dir, ZIPPED_FOLDER_NAME)
    os.makedirs(dest_path, exist_ok=True)
    
    source_folders = [item for item in os.listdir(script_dir)
                      if os.path.isdir(os.path.join(script_dir, item)) and item != ZIPPED_FOLDER_NAME]

    if not source_folders:
        print("未在當前目錄下找到任何需要處理的資料夾。")
        print("請確保此腳本與您想壓縮的資料夾放在一起。")
        return

    print(f"將在 '{script_dir}' 中尋找資料夾...")
    print(f"找到 {len(source_folders)} 個待處理資料夾: {', '.join(source_folders)}")
    print(f"所有壓縮檔將儲存至: {dest_path}")
    print("-" * 25)

    max_size_bytes = MAX_ZIP_SIZE_MB * 1024 * 1024

    for folder_name in source_folders:
        print(f"\n>>>>> 開始處理資料夾: [{folder_name}] <<<<<")
        source_path = os.path.join(script_dir, folder_name)
        process_folder(source_path, dest_path, folder_name, max_size_bytes)

    print("-" * 25)
    print("--- 所有批量任務完成 ---")

if __name__ == "__main__":
    main()