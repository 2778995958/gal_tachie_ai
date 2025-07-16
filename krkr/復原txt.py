# -*- coding: utf-8 -*-

import sys
import os

# --- 參數設定 ---
# 一個包含所有可能編碼的列表，程式會自動嘗試
ENCODINGS_TO_TRY = [
    'utf-16',
    'euc-jp',
    'cp932',
    'shift_jis',
    'utf-8',
]

# 新檔案的目標編碼
output_encoding = 'utf-8-sig'

# --- 主要轉換函式 ---
def analyze_and_convert_file(input_path, target_encoding):
    """
    輪流嘗試多種編碼來讀取單一檔案，成功後再進行轉換。
    """
    print(f"開始分析檔案：{os.path.basename(input_path)}")
    print("-" * 30)

    try:
        with open(input_path, 'rb') as f_binary:
            raw_bytes = f_binary.read()
    except Exception as e:
        print(f"!! 錯誤：無法讀取檔案。 {e}")
        return

    decoded_content = None
    successful_encoding = None
    for encoding in ENCODINGS_TO_TRY:
        try:
            content = raw_bytes.decode(encoding)
            print(f"✔️ 探測成功！檔案編碼為 '{encoding}'。")
            decoded_content = content
            successful_encoding = encoding
            break
        except UnicodeDecodeError:
            print(f"❌ 探測失敗：'{encoding}' 編碼不符。")
            continue

    print("-" * 30)

    if decoded_content:
        try:
            lines = decoded_content.splitlines(True)
            if lines:
                first_line = lines[0]
                hash_pos = first_line.find('#')
                if hash_pos != -1:
                    lines[0] = first_line[hash_pos + 1:].lstrip()
                    print("-> 已自動清理檔案標頭。")

            file_dir = os.path.dirname(input_path)
            file_name_without_ext = os.path.splitext(os.path.basename(input_path))[0]
            output_name = f"{file_name_without_ext}_converted.csv"
            output_path = os.path.join(file_dir, output_name)
            
            with open(output_path, 'w', encoding=target_encoding) as f_out:
                f_out.writelines(lines)
            print(f"✔️ 轉換完成！已儲存為：'{output_name}'")
        except Exception as e:
            print(f"!! 錯誤：在處理或儲存檔案時發生問題。 {e}")
    else:
        print("!! 最終分析失敗：所有常見編碼都無法解讀此檔案。")

# --- 程式進入點 ---
if __name__ == "__main__":
    # 檢查是否有檔案被拖曳進來
    if len(sys.argv) > 1:
        # sys.argv[1:] 會取得除了腳本名稱外的所有引數(也就是所有拖曳的檔案)
        files_to_process = sys.argv[1:]
        total_files = len(files_to_process)
        print(f"偵測到 {total_files} 個檔案，準備開始批次處理...")
        print("=" * 40)

        # ★★★ 新增的迴圈邏輯，用來處理每一個檔案 ★★★
        for i, file_path in enumerate(files_to_process):
            print(f"\n--- 正在處理第 {i + 1} / {total_files} 個檔案 ---")
            analyze_and_convert_file(file_path, output_encoding)
            print("-" * 40)

        print("\n所有檔案處理完畢！")
    else:
        print("使用方式：請將一個或多個要轉換的檔案，一起拖曳到此 .py 程式的圖示上。")

    os.system('pause')
