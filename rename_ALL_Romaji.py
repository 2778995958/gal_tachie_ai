import os
import csv
import argparse
from datetime import datetime
from pykakasi import kakasi

def convert_japanese_filename_to_romaji(filename):
    """將檔案名稱中的日文轉換為羅馬字。"""
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
    """從指定的 CSV 日誌檔案讀取紀錄，並將檔名復原。此方法使用絕對路徑。"""
    # (此函數保持不變，繼續使用絕對路徑進行復原)
    if not os.path.exists(log_filepath):
        print(f"錯誤：日誌檔案 '{log_filepath}' 不存在。")
        return
    print(f"正在從日誌檔案 '{log_filepath}' 進行復原...")
    # ... (其餘程式碼與前一版本相同)
    restored_count = 0
    try:
        with open(log_filepath, 'r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
            if header != ['original_path', 'new_path']:
                print("錯誤：日誌檔案格式不正確。")
                return
            for row in reader:
                original_path, new_path = row
                if os.path.exists(new_path):
                    print(f"正在復原: {os.path.basename(new_path)} -> {os.path.basename(original_path)}")
                    try:
                        os.rename(new_path, original_path)
                        restored_count += 1
                    except OSError as e:
                        print(f"  -> 錯誤：無法復原檔案。 {e}")
                else:
                    print(f"警告：找不到檔案 '{new_path}'，跳過此檔案。")
    except Exception as e:
        print(f"讀取日誌檔案時發生錯誤：{e}")
    print(f"\n復原完成！總共復原了 {restored_count} 個檔案。")


def batch_rename_pngs_in_directory(root_dir):
    """遍歷目錄並重新命名 PNG 檔案，並建立可攜帶的 .bat 復原檔和 .csv 日誌。"""
    # 將傳入的路徑轉換為絕對路徑，以確保一致性
    root_dir = os.path.abspath(root_dir)
    if not os.path.isdir(root_dir):
        print(f"錯誤：目錄 '{root_dir}' 不存在。")
        return

    run_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_filename = f"rename_log_{run_timestamp}.csv"
    bat_filename = f"recover_files_{run_timestamp}.bat"
    log_filepath = os.path.join(root_dir, log_filename)
    bat_filepath = os.path.join(root_dir, bat_filename)
    
    print(f"開始掃描目錄：{root_dir}")
    
    log_records = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.lower().endswith('.png'):
                # 忽略我們自己產生的日誌/批次檔
                if filename.startswith('rename_log_') or filename.startswith('recover_files_'):
                    continue
                new_filename = convert_japanese_filename_to_romaji(filename)
                if new_filename != filename:
                    original_path = os.path.join(dirpath, filename)
                    new_path = os.path.join(dirpath, new_filename)
                    log_records.append([original_path, new_path])
    
    if not log_records:
        print("找不到需要重新命名的檔案。")
        return

    print(f"預計將重新命名 {len(log_records)} 個檔案。")
    print(f".csv 日誌 (絕對路徑) 將儲存至：{log_filepath}")
    print(f".bat 復原檔 (相對路徑, 可攜帶) 將儲存至：{bat_filepath}\n")

    renamed_count = 0
    try:
        with open(log_filepath, 'w', newline='', encoding='utf-8') as csv_file, \
             open(bat_filepath, 'w', encoding='utf-8-sig') as bat_file:
            
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(['original_path', 'new_path'])
            
            # --- 說明文件 1: 寫入 .bat 檔案的標頭，使其可攜帶 ---
            bat_file.write('@ECHO OFF\n')
            bat_file.write('REM Change code page to UTF-8 to handle special characters\n')
            bat_file.write('CHCP 65001 > NUL\n')
            bat_file.write('REM Set the current directory to the location of this batch file to make it portable\n')
            bat_file.write('cd /d "%~dp0"\n')
            bat_file.write('ECHO Restoring file names from this folder...\n\n')

            for original_path, new_path in log_records:
                try:
                    os.rename(original_path, new_path)
                    
                    # --- 說明文件 2: 寫入不同格式的路徑 ---
                    # 1. CSV 日誌：寫入絕對路徑，供 Python 腳本使用
                    csv_writer.writerow([original_path, new_path])
                    
                    # 2. BAT 批次檔：寫入相對路徑，使其可攜帶
                    relative_new_path = os.path.relpath(new_path, root_dir)
                    original_basename = os.path.basename(original_path)
                    
                    ren_command = f'REN "{relative_new_path}" "{original_basename}"\n'
                    bat_file.write(ren_command)
                    
                    print(f"已改名: {os.path.basename(original_path)} -> {os.path.basename(new_path)}")
                    renamed_count += 1
                except OSError as e:
                    print(f"  -> 錯誤：無法重新命名檔案 {original_path}。 {e}")
            
            bat_file.write('\nECHO Recovery complete.\n')
            bat_file.write('PAUSE\n')

    except IOError as e:
        print(f"錯誤：無法寫入日誌或批次檔案。 {e}")
        return

    print(f"\n處理完成！總共重新命名了 {renamed_count} 個檔案。")
    print(f"若要復原，可直接執行可攜帶的批次檔：{bat_filename}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="批次重新命名 PNG 檔案中的日文為羅馬字，並提供復原功能。",
        epilog="使用範例:\n"
               "  改名 (並產生可攜帶的 .bat 復原檔): python %(prog)s \"C:\\路徑\\到\\資料夾\"\n"
               "  使用 Python 腳本復原 (需原始路徑): python %(prog)s -r \"C:\\路徑\\到\\資料夾\\rename_log_xxx.csv\"",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('directory', nargs='?', default=None, help="要掃描的目標資料夾路徑。")
    parser.add_argument('-r', '--recover', metavar='LOG_FILE', help="使用指定的 .csv 日誌檔案進行復原 (進階選項)。")
    args = parser.parse_args()

    if args.recover:
        recover_from_log(args.recover)
    elif args.directory:
        batch_rename_pngs_in_directory(args.directory)
    else:
        parser.print_help()
