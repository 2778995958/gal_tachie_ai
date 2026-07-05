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

def create_zip_archive(zip_path, file_list):
    """
    根據提供的檔案列表（包含相對路徑與完整路徑），建立一個 ZIP 壓縮檔。
    """
    print(f"    正在建立 ZIP 檔: {os.path.basename(zip_path)} ({len(file_list)} 個檔案)...")
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_STORED) as zipf:
            for rel_path, full_path in file_list:
                # write 的第一個參數是實體檔案路徑，arcname 是在 ZIP 裡顯示的相對路徑
                zipf.write(full_path, arcname=rel_path)
        print(f"    > 成功建立: {os.path.basename(zip_path)}")
        return True
    except Exception as e:
        print(f"    > 建立失敗: {e}")
        return False

def process_folder(source_path, dest_path, base_zip_name, max_size_bytes):
    """
    遞迴收集該資料夾及所有子資料夾內的檔案，並以頂層資料夾名稱進行分批壓縮。
    """
    file_entries = []
    
    try:
        # 使用 os.walk 深入此頂層資料夾內的所有子目錄
        for dirpath, dirnames, filenames in os.walk(source_path):
            for filename in filenames:
                full_path = os.path.join(dirpath, filename)
                # 計算檔案相對於頂層資料夾（例如 'a'）的相對路徑，用來排序以及在 ZIP 內建立目錄結構
                rel_path = os.path.relpath(full_path, source_path)
                file_entries.append((rel_path, full_path))
                
        # 依照相對路徑進行自然排序（會先排完子資料夾 1，再排子資料夾 2）
        file_entries.sort(key=lambda x: natural_sort_key(x[0]))
        
        if not file_entries:
            print(f"  > 資料夾 '{base_zip_name}' 及其子資料夾內沒有任何檔案，已跳過。")
            return
            
        print(f"  包含所有子資料夾共找到 {len(file_entries)} 個檔案，準備開始分批壓縮...")

    except Exception as e:
        print(f"  讀取資料夾 '{base_zip_name}' 內容時發生錯誤: {e}")
        return

    zip_counter = 1
    current_zip_files = []
    current_zip_size = 0

    for rel_path, full_path in file_entries:
        file_size = os.path.getsize(full_path)

        if file_size > max_size_bytes:
            print(f"  警告：檔案 '{rel_path}' ({file_size / 1024 / 1024:.2f} MB) 本身就超過了 {MAX_ZIP_SIZE_MB} MB 的上限，將被跳過。")
            continue

        if current_zip_files and (current_zip_size + file_size > max_size_bytes):
            zip_filename = f"{base_zip_name}_{zip_counter}.zip"
            zip_path = os.path.join(dest_path, zip_filename)
            create_zip_archive(zip_path, current_zip_files)
            
            zip_counter += 1
            current_zip_files = []
            current_zip_size = 0

        # 將此檔案（包含路徑資訊）加入當前的壓縮批次
        current_zip_files.append((rel_path, full_path))
        current_zip_size += file_size

    if current_zip_files:
        zip_filename = f"{base_zip_name}_{zip_counter}.zip"
        zip_path = os.path.join(dest_path, zip_filename)
        create_zip_archive(zip_path, current_zip_files)

def main():
    """
    主執行函數：尋找同層級的所有頂層資料夾並逐一處理。
    """
    print("--- 開始執行頂層資料夾批量分割壓縮任務 ---")
    
    script_dir = os.getcwd()
    dest_path = os.path.join(script_dir, ZIPPED_FOLDER_NAME)
    os.makedirs(dest_path, exist_ok=True)
    
    # 恢復原版：只撈取跟腳本同層級的頂層資料夾
    source_folders = [item for item in os.listdir(script_dir)
                      if os.path.isdir(os.path.join(script_dir, item)) and item != ZIPPED_FOLDER_NAME]

    if not source_folders:
        print("未在當前目錄下找到任何需要處理的資料夾。")
        print("請確保此腳本與您想壓縮的資料夾放在一起。")
        return

    print(f"將在 '{script_dir}' 中尋找頂層資料夾...")
    print(f"找到 {len(source_folders)} 個待處理頂層資料夾: {', '.join(source_folders)}")
    print(f"所有壓縮檔將儲存至: {dest_path}")
    print("-" * 25)

    max_size_bytes = MAX_ZIP_SIZE_MB * 1024 * 1024

    for folder_name in source_folders:
        print(f"\n>>>>> 開始處理頂層資料夾: [{folder_name}] <<<<<")
        source_path = os.path.join(script_dir, folder_name)
        process_folder(source_path, dest_path, folder_name, max_size_bytes)

    print("-" * 25)
    print("--- 所有批量任務完成 ---")

if __name__ == "__main__":
    main()