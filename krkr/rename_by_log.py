import os
import sys

# --- 設定 ---
# Log 檔案所在的資料夾名稱
LOG_SOURCE_DIR = "StringHashDumper_Output"

# 需要重新命名的檔案和資料夾所在的根目錄
TARGET_RENAME_DIR = "Extractor_Output"

# Log 檔案的名稱列表
LOG_FILES = ["DirectoryHash.log", "FileNameHash.log"]

# 分隔符號
SEPARATOR = "##YSig##"
# --- 設定結束 ---

def build_hash_map():
    """
    讀取 Log 檔案並建立一個 Hash 對應原始檔名的字典。
    返回值:
        一個字典，鍵(key)是 Hash 字串，值(value)是原始檔名。
    """
    hash_to_name_map = {}
    print("正在讀取 Log 檔案並建立對應表...")

    for log_file in LOG_FILES:
        log_path = os.path.join(LOG_SOURCE_DIR, log_file)

        if not os.path.exists(log_path):
            print(f"警告：找不到 Log 檔案 '{log_path}'，已跳過。")
            continue

        try:
            with open(log_path, 'r', encoding='utf-16') as f:
                for line in f:
                    # 去除行尾的換行符並檢查分隔符是否存在
                    clean_line = line.strip()
                    if SEPARATOR in clean_line:
                        # 分割原始路徑和 Hash
                        original_part, hash_value = clean_line.split(SEPARATOR, 1)
                        
                        # 處理原始路徑，例如 "system/" 會變成 "system"
                        original_name = original_part.strip('/')
                        
                        # 將對應關係存入字典
                        hash_to_name_map[hash_value] = original_name
        except Exception as e:
            print(f"讀取檔案 '{log_path}' 時發生錯誤: {e}")
    
    print(f"對應表建立完成！總共讀取到 {len(hash_to_name_map)} 筆對應資料。")
    return hash_to_name_map

def rename_files_and_folders(root_dir, hash_map):
    """
    遍歷指定的目錄，並根據 hash_map 重新命名檔案和資料夾。
    參數:
        root_dir (str): 要進行重新命名的根目錄。
        hash_map (dict): Hash 與原始檔名的對應字典。
    """
    if not os.path.isdir(root_dir):
        print(f"錯誤：找不到目標資料夾 '{root_dir}'。請確認資料夾名稱是否正確，以及腳本是否放在正確的位置。")
        return

    print(f"\n開始掃描並重新命名 '{root_dir}' 中的檔案和資料夾...")
    rename_count = 0

    # 使用 os.walk 由下而上 (topdown=False) 遍歷
    # 這樣可以確保我們先處理完子資料夾的內容，再重新命名子資料夾本身
    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=False):
        
        # 1. 重新命名檔案
        for filename in filenames:
            if filename in hash_map:
                old_path = os.path.join(dirpath, filename)
                new_name = hash_map[filename]
                new_path = os.path.join(dirpath, new_name)
                
                try:
                    os.rename(old_path, new_path)
                    print(f"  [檔案] '{filename}' -> '{new_name}'")
                    rename_count += 1
                except OSError as e:
                    print(f"  [錯誤] 無法重新命名檔案 '{old_path}': {e}")

        # 2. 重新命名資料夾
        for dirname in dirnames:
            if dirname in hash_map:
                old_path = os.path.join(dirpath, dirname)
                new_name = hash_map[dirname]
                new_path = os.path.join(dirpath, new_name)

                try:
                    os.rename(old_path, new_path)
                    print(f"  [目錄] '{dirname}' -> '{new_name}'")
                    rename_count += 1
                except OSError as e:
                    print(f"  [錯誤] 無法重新命名目錄 '{old_path}': {e}")

    print(f"\n處理完成！總共重新命名了 {rename_count} 個項目。")

# --- 主程式執行區 ---
if __name__ == "__main__":
    # 建立對應表
    mapping = build_hash_map()
    
    # 如果對應表是空的，就沒有必要繼續執行
    if not mapping:
        print("無法建立任何對應關係，程式即將結束。")
        sys.exit()

    # 執行重新命名
    rename_files_and_folders(TARGET_RENAME_DIR, mapping)