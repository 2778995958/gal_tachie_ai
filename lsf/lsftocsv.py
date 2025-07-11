import os
import glob
import csv
import re
from typing import List, NamedTuple

# --- 資料結構定義 (不變) ---
class Rect(NamedTuple):
    left: int
    top: int
    right: int
    bottom: int

class LayerInfo(NamedTuple):
    source_file: str
    name: str
    rect: Rect
    index: int
    state: int

# --- 通用版 LSF 解析函式 ---
def parse_lsf_universal(byte_data: bytes, source_filename: str) -> List[LayerInfo]:
    """
    使用通用的正規表示式，解析所有類型的 LSF 檔案。
    """
    layers = []
    
    # --- 最終修正點 ---
    # 使用一個更通用的正規表示式，不再寫死 'Jerusha'
    # [\w_]+ 匹配一個以上的字母、數字或底線
    # \d{3} 匹配結尾的三個數字
    # 這能匹配 '01_Jerusha_p_l_001' 以及 '02_some_other_name_005' 等
    matches = list(re.finditer(b'[\w_]+_\d{3}', byte_data))

    for match in matches:
        try:
            # 直接使用正規表示式匹配到的完整結果作為檔名
            name = match.group(0).decode('ascii')
            
            # 名稱長度必須合理，過短的可能是誤判
            if len(name) < 5: 
                continue

            anchor_pos = match.start()
            
            # 使用我們之前破解的精確位移量讀取資料
            rect = Rect(
                left=int.from_bytes(byte_data[anchor_pos + 128 : anchor_pos + 130], 'little'),
                top=int.from_bytes(byte_data[anchor_pos + 132 : anchor_pos + 134], 'little'),
                right=int.from_bytes(byte_data[anchor_pos + 136 : anchor_pos + 138], 'little'),
                bottom=int.from_bytes(byte_data[anchor_pos + 140 : anchor_pos + 142], 'little')
            )
            
            index_val = byte_data[anchor_pos + 152]
            state_val = byte_data[anchor_pos + 153]

            layers.append(LayerInfo(
                source_file=source_filename,
                name=name,
                rect=rect,
                index=index_val,
                state=state_val
            ))
        except Exception as e:
            # 發生任何錯誤都只針對單一錨點，不影響整個檔案的解析
            # print(f"  - 解析錨點 '{match.group(0)}' 時出錯: {e}")
            continue
            
    return layers

# --- 主程式 ---
def main():
    # 搜尋當前目錄下的所有 .lsf 檔案
    LSF_DIR = '.' 
    OUTPUT_CSV_FILE = 'lsf_universal_export.csv'

    lsf_files_to_process = glob.glob(os.path.join(LSF_DIR, '*.lsf'))
    
    if not lsf_files_to_process:
        print(f"錯誤：在當前目錄 '{os.path.abspath(LSF_DIR)}' 中找不到任何 .lsf 檔案。")
        return

    print(f"找到 {len(lsf_files_to_process)} 個 LSF 檔案，開始使用通用解析器進行處理...")
    
    all_layers_data = []

    for lsf_path in lsf_files_to_process:
        lsf_filename = os.path.basename(lsf_path)
        print(f"  - 正在解析: {lsf_filename}")
        try:
            with open(lsf_path, 'rb') as f:
                lsf_data = f.read()
            layers_from_file = parse_lsf_universal(lsf_data, lsf_filename)
            all_layers_data.extend(layers_from_file)
        except Exception as e:
            print(f"    處理檔案時發生致命錯誤: {e}")

    if not all_layers_data:
        print("解析完成，但未能從任何檔案中提取到圖層資料。")
        return

    try:
        with open(OUTPUT_CSV_FILE, 'w', newline='', encoding='utf-8-sig') as csvfile:
            header = ['source_lsf', 'layer_name', 'rect_left', 'rect_top', 'rect_right', 'rect_bottom', 'index', 'state']
            writer = csv.writer(csvfile)
            writer.writerow(header)
            for layer in all_layers_data:
                writer.writerow([
                    layer.source_file, layer.name,
                    layer.rect.left, layer.rect.top,
                    layer.rect.right, layer.rect.bottom,
                    layer.index, layer.state
                ])
        print(f"\n✅ 通用解析完成！所有檔案的資料已匯出至: {OUTPUT_CSV_FILE}")
    except Exception as e:
        print(f"\n寫入 CSV 檔案時發生錯誤: {e}")

if __name__ == "__main__":
    main()