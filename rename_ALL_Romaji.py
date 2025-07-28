import os
import csv
import argparse
from datetime import datetime
from pykakasi import kakasi

def convert_japanese_filename_to_romaji(filename):
    """
    將檔案名稱中的日文轉換為羅馬字。
    (此函數與先前版本相同)
    """
    kks = kakasi()
    base_name, extension = os.path.splitext(filename)
    result = kks.convert(base_name)
    temp_new_base = "".join([part['hepburn'] for part in result])
    final_parts = []
    for component in temp_new_base.split('_'):
        if component and component.isalpha():
            final_parts.append(component.capitalize())
        else:
            final_parts.append(component)
    new_base_name = "_".join(final_parts)
    return f"{new_base_name}{extension}"

def recover_from_log(log_filepath):
    """
    從指定的日誌檔案讀取紀錄，並將檔名復原。
    """
    if not os.path.exists(log_filepath):
        print(f"錯誤：日誌檔案 '{log_filepath}' 不存在。")
        return

    print(f"正在從日誌檔案 '{log_filepath}' 進行復原...")
    restored_count = 0
    
    try:
        with open(log_filepath, 'r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            # 跳過標頭
            header = next(reader)
            if header != ['original_path', 'new_path']:
                print("錯誤：日誌檔案格式不正確。")
                return

            for row in reader:
                original_path, new_path = row
                
                # --- 說明文件 1: 執行反向重新命名 ---
                if os.path.exists(new_path):
                    print(f"正在復原: {new_path}")
                    print(f"  -> 回到: {original_path}")
                    try:
                        os.rename(new_path, original_path)
                        restored_count += 1
                    except OSError as e:
                        print(f"  -> 錯誤：無法復原檔案。 {e}")
                else:
                    print(f"警告：找不到檔案 '{new_path}'，可能已被移動或刪除。跳過此檔案。")

    except Exception as e:
        print(f"讀取日誌檔案時發生錯誤：{e}")

    print(f"\n復原完成！總共復原了 {restored_count} 個檔案。")


def batch_rename_pngs_in_directory(root_dir):
    """
    遍歷目錄並重新命名 PNG 檔案，同時建立一個復原日誌。
    """
    if not os.path.isdir(root_dir):
        print(f"錯誤：目錄 '{root_dir}' 不存在。")
        return

    # --- 說明文件 2: 建立唯一的日誌檔 ---
    log_filename = f"rename_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    log_filepath = os.path.join(root_dir, log_filename)
    
    print(f"開始掃描目錄：{root_dir}")
    print(f"復原日誌將會儲存至：{log_filepath}\n")

    # 使用一個列表來暫存需要寫入的日誌紀錄
    log_records = []
    
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.lower().endswith('.png'):
                new_filename = convert_japanese_filename_to_romaji(filename)
                
                if new_filename != filename:
                    original_path = os.path.join(dirpath, filename)
                    new_path = os.path.join(dirpath, new_filename)
                    
                    # 將紀錄加入暫存列表
                    log_records.append([original_path, new_path])
    
    # --- 說明文件 3: 執行改名並寫入日誌 ---
    if not log_records:
        print("找不到需要重新命名的檔案。")
        return

    renamed_count = 0
    # 開啟日誌檔並寫入
    with open(log_filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['original_path', 'new_path']) # 寫入標頭
        
        for original_path, new_path in log_records:
            print(f"正在改名: {os.path.basename(original_path)} -> {os.path.basename(new_path)}")
            try:
                os.rename(original_path, new_path)
                writer.writerow([original_path, new_path]) # 寫入成功改名的紀錄
                renamed_count += 1
            except OSError as e:
                print(f"  -> 錯誤：無法重新命名檔案 {original_path}。 {e}")
                
    print(f"\n處理完成！總共重新命名了 {renamed_count} 個檔案。")
    print(f"復原日誌已成功建立：{log_filename}")


if __name__ == "__main__":
    # --- 說明文件 4: 設定命令列指令解析 ---
    parser = argparse.ArgumentParser(
        description="批次重新命名 PNG 檔案中的日文為羅馬字，並提供復原功能。",
        epilog="使用範例:\n"
               "  改名: python %(prog)s \"C:\\路徑\\到\\資料夾\"\n"
               "  復原: python %(prog)s -r \"C:\\路徑\\到\\資料夾\\rename_log_xxx.csv\"",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument(
        'directory', 
        nargs='?', 
        default=None, 
        help="要掃描的目標資料夾路徑。"
    )
    
    parser.add_argument(
        '-r', '--recover', 
        metavar='LOG_FILE', 
        help="從指定的日誌檔案進行復原。"
    )

    args = parser.parse_args()

    # 根據指令決定要執行哪個功能
    if args.recover:
        recover_from_log(args.recover)
    elif args.directory:
        batch_rename_pngs_in_directory(args.directory)
    else:
        # 如果沒有提供任何指令，顯示幫助訊息
        parser.print_help()
