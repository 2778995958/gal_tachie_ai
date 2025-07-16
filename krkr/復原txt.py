# -*- coding: utf-8 -*-

import sys
import os

# --- 參數設定 ---
# 建立一個包含所有可能編碼的列表，按成功率高低排序
ENCODINGS_TO_TRY = [
    'utf-16',
    'euc-jp',
    'cp932',
    'shift_jis',
    'utf-8',
]

# 新檔案的目標編碼
output_encoding = 'utf-8-sig'

# --- 主程式 ---
def analyze_and_convert_file(input_path, target_encoding):
    """
    輪流嘗試多種編碼來讀取檔案，成功後再進行轉換。
    """
    print(f"開始對檔案進行深度分析：{os.path.basename(input_path)}")
    print("-" * 30)

    # 1. 以二進位模式讀取檔案的原始數據
    try:
        with open(input_path, 'rb') as f_binary:
            raw_bytes = f_binary.read()
    except Exception as e:
        print(f"!! 錯誤：無法以二進位模式讀取檔案。 {e}")
        return

    # 2. 輪流用各種編碼進行解碼嘗試
    decoded_content = None
    successful_encoding = None
    for encoding in ENCODINGS_TO_TRY:
        try:
            content = raw_bytes.decode(encoding)
            print(f"✔️ 探測成功！檔案似乎是用 '{encoding}' 編碼。")
            decoded_content = content
            successful_encoding = encoding
            break  # 只要成功就跳出迴圈
        except UnicodeDecodeError:
            print(f"❌ 探測失敗：'{encoding}' 編碼不符。")
            continue # 繼續嘗試下一個

    print("-" * 30)

    # 3. 如果有任何一種編碼成功，就進行後續處理
    if decoded_content:
        # --- 標頭清理和儲存邏輯 ---
        try:
            lines = decoded_content.splitlines(True) # 將解碼後的內容按行分割
            if lines:
                first_line = lines[0]
                hash_pos = first_line.find('#')
                if hash_pos != -1:
                    lines[0] = first_line[hash_pos + 1:].lstrip()
                    print("-> 已自動清理檔案標頭。")

            # 組合輸出路徑
            file_dir = os.path.dirname(input_path)
            file_name_without_ext = os.path.splitext(os.path.basename(input_path))[0]
            output_name = f"{file_name_without_ext}_salvaged.csv"
            output_path = os.path.join(file_dir, output_name)

            # 寫入最終檔案
            with open(output_path, 'w', encoding=target_encoding) as f_out:
                f_out.writelines(lines)
            print(f"✔️ 轉換完成！已儲存為：'{output_name}'")

        except Exception as e:
            print(f"!! 錯誤：在處理或儲存檔案時發生問題。 {e}")
    else:
        print("!! 最終分析失敗：所有常見編碼都無法解讀此檔案。")
        print("   檔案可能已損壞，或它是一個無法直接讀取的專用二進位格式。")

# --- 程式進入點 ---
if __name__ == "__main__":
    if len(sys.argv) > 1:
        analyze_and_convert_file(sys.argv[1], output_encoding)
    else:
        print("使用方式：請將要分析的檔案拖曳到此 .py 程式的圖示上。")

    os.system('pause')