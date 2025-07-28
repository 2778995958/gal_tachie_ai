import os

def convert_sinfo_to_utf8_txt(directory='.', input_encoding='shift_jis'):
    """
    將指定目錄下所有 .sinfo 檔案從日文編碼轉換為 UTF-8 編碼的 .txt 檔案。

    Args:
        directory (str): 要處理的目錄路徑。預設為當前目錄。
        input_encoding (str): .sinfo 檔案的原始編碼。預設為 'shift_jis'。
                              常見的日文編碼還有 'cp932'。
    """
    print(f"開始在 '{directory}' 目錄中轉換檔案...")
    
    converted_count = 0
    failed_files = []

    for filename in os.listdir(directory):
        if filename.endswith(".sinfo"):
            sinfo_filepath = os.path.join(directory, filename)
            txt_filename = os.path.splitext(filename)[0] + ".txt"
            txt_filepath = os.path.join(directory, txt_filename)

            print(f"正在處理檔案: {filename} ...")
            try:
                # 以指定編碼讀取 .sinfo 檔案
                with open(sinfo_filepath, 'r', encoding=input_encoding, errors='replace') as infile:
                    content = infile.read()
                
                # 以 UTF-8 編碼寫入 .txt 檔案
                with open(txt_filepath, 'w', encoding='utf-8') as outfile:
                    outfile.write(content)
                
                print(f"成功轉換 {filename} 為 {txt_filename}")
                converted_count += 1

            except UnicodeDecodeError as e:
                print(f"錯誤：無法解碼檔案 {filename} - {e}")
                failed_files.append(filename)
            except Exception as e:
                print(f"處理檔案 {filename} 時發生未知錯誤：{e}")
                failed_files.append(filename)
    
    print("\n--- 轉換完成 ---")
    print(f"總共轉換了 {converted_count} 個檔案。")
    if failed_files:
        print("以下檔案轉換失敗：")
        for f in failed_files:
            print(f"- {f}")
    else:
        print("所有檔案都成功轉換。")

if __name__ == "__main__":
    # 您可以在這裡指定要處理的目錄。
    # 如果 .sinfo 檔案在腳本同一個目錄下，則不需要更改。
    # 例如：convert_sinfo_to_utf8_txt(directory='C:/我的資料夾/sinfo檔案')
    
    # 選擇您認為最合適的原始日文編碼，'shift_jis' 或 'cp932'
    # 如果遇到亂碼，可以嘗試更換 input_encoding 的值
    convert_sinfo_to_utf8_txt(input_encoding='shift_jis') 
    # 或者嘗試 convert_sinfo_to_utf8_txt(input_encoding='cp932')