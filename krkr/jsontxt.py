import json
import os
import glob

def convert_json_file_to_txt(input_file_path, output_file_path):
    """
    讀取 JSON 檔案，並嚴格按照 key-欄位對應的原則，
    將其內容轉換為標準的 TSV (Tab 分隔) 檔案。
    """
    try:
        # 讀取並載入 JSON 檔案
        with open(input_file_path, 'r', encoding='utf-8') as json_file:
            data = json.load(json_file)

        # 定義欄位標頭，這是輸出的順序
        headers = [
            "layer_type", "name", "left", "top", "width", "height",
            "type", "opacity", "visible", "layer_id", "group_layer_id"
        ]

        # 開啟檔案準備寫入
        with open(output_file_path, 'w', encoding='utf-8') as f:
            # 寫入以 Tab 分隔的標頭
            f.write("#" + "\t".join(headers) + '\n')

            # *** 主要修改處 ***
            # 不再有 if/else 判斷，對所有物件使用相同的處理方式
            for item in data:
                # 根據 headers 的順序，從 item 中取得對應的值
                # item.get(h, "") 的意思是：嘗試取得 key 為 h 的值，如果不存在，則回傳空字串 ""
                row_data = [str(item.get(h, "")) for h in headers]
                
                # 將產生的資料列用 Tab 字元串接起來，並寫入檔案
                f.write("\t".join(row_data) + '\n')

    except json.JSONDecodeError:
        print(f"-> 錯誤：'{input_file_path}' 的內容並非有效的 JSON 格式，已跳過。")
    except Exception as e:
        print(f"-> 錯誤：處理 '{input_file_path}' 時發生未預期錯誤：{e}，已跳過。")

# --- 主程式執行區塊 (與之前相同) ---
if __name__ == "__main__":
    json_files = glob.glob('*.json')
    if not json_files:
        print("在目前目錄下找不到任何 .json 檔案。")
    else:
        print(f"偵測到 {len(json_files)} 個 JSON 檔案，開始批次轉換...")
        
        for input_filename in json_files:
            base_name = os.path.splitext(input_filename)[0]
            output_filename = base_name + '.txt'
            
            print(f"正在轉換: {input_filename}  ->  {output_filename}")
            convert_json_file_to_txt(input_filename, output_filename)
        
        print("\n所有轉換工作已全部完成！")