import json
import csv
import os
from PIL import Image

# --- 常數設定 ---
JSON_FILE = 'as_eyecatch.pbd.json'
CSV_FILE = 'imagediffmap.csv'
IMAGE_DIRECTORY = '.'  # 圖片來源目錄 ('.' 表示目前目錄)
OUTPUT_DIRECTORY = '.' # 圖片輸出目錄 ('.' 表示目前目錄)

def load_layer_map(json_path):
    """
    載入 as_eyecatch.pbd.json 檔案，
    並建立一個從 'name' (例如 'anj1') 對應到 
    'layerFilename.png' (例如 'アイキャッチ杏珠1.png') 的字典。
    """
    print(f"正在讀取圖層對應表: {json_path}...")
    layer_map = {}
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        for item in data:
            if 'name' in item and 'layerFilename' in item:
                filename = item['layerFilename'] + '.png'
                layer_map[item['name']] = filename
                
        print(f"成功載入 {len(layer_map)} 個圖層對應。")
        return layer_map
        
    except FileNotFoundError:
        print(f"錯誤：找不到 JSON 檔案 '{json_path}'。")
        return None
    except json.JSONDecodeError:
        print(f"錯誤：JSON 檔案 '{json_path}' 格式不正確。")
        return None
    except Exception as e:
        print(f"讀取 JSON 時發生未預期的錯誤: {e}")
        return None

def process_composites(csv_path, layer_map):
    """
    讀取 CSV 檔案，並根據定義的順序合成圖片。
    """
    print(f"\n開始處理 CSV 檔案: {csv_path}...")
    
    try:
        with open(csv_path, 'r', encoding='utf-16') as f:
            reader = csv.reader(f)
            
            for i, row in enumerate(reader):
                if len(row) < 4:
                    print(f"警告：第 {i+1} 行格式不符，已跳過。")
                    continue
                    
                output_name = row[0] + '.png'
                layer_names_str = row[3]  # 例如 "com:base:chara"
                
                # --- 修改開始 (V5 邏輯) ---
                
                all_layers = layer_names_str.split(':')
                
                if len(all_layers) != 3:
                    print(f"警告：在 '{layer_names_str}' 中的圖層數量不為 3，已跳過 {output_name}。")
                    continue

                # 根據你發現的固定順序 (中層:底層:面層)
                middle_layer = all_layers[0]
                base_layer = all_layers[1]
                top_layer = all_layers[2]
                
                # 建立正確的堆疊順序 (底層 -> 中層 -> 面層)
                stack_order = [base_layer, middle_layer, top_layer]
                
                # --- 修改結束 ---

                print(f"--- 處理中: {output_name} ---")
                print(f"  CSV 欄位: {layer_names_str} (中:底:面)")
                print(f"  堆疊順序: {' -> '.join(stack_order)} (底->中->面)")
                
                canvas = None
                
                # 執行合成
                try:
                    for layer_name in stack_order:
                        if layer_name not in layer_map:
                            print(f"  錯誤：在 JSON 中找不到圖層 '{layer_name}' 的定義。")
                            raise Exception(f"Missing layer definition: {layer_name}")
                            
                        image_filename = layer_map[layer_name]
                        image_path = os.path.join(IMAGE_DIRECTORY, image_filename)
                        
                        if not os.path.exists(image_path):
                            print(f"  錯誤：找不到圖片檔案 '{image_path}'。")
                            raise FileNotFoundError()

                        layer_image = Image.open(image_path).convert('RGBA')
                        
                        if canvas is None:
                            canvas = layer_image
                            print(f"  [底層] 載入: {image_filename}")
                        else:
                            canvas = Image.alpha_composite(canvas, layer_image)
                            print(f"  [疊加] 載入: {image_filename}")
                            
                    # 儲存結果
                    if canvas:
                        output_path = os.path.join(OUTPUT_DIRECTORY, output_name)
                        canvas.save(output_path)
                        print(f"  ✅ 成功儲存: {output_path}\n")

                except Exception as e:
                    print(f"  ❌ 處理 {output_name} 時發生錯誤: {e}\n")
                    
    except FileNotFoundError:
        print(f"錯誤：找不到 CSV 檔案 '{csv_path}'。")
    except Exception as e:
        print(f"讀取 CSV 時發生未預期的錯誤: {e}")

# --- 程式執行入口 ---
if __name__ == "__main__":
    layer_map = load_layer_map(JSON_FILE)
    
    if layer_map:
        process_composites(CSV_FILE, layer_map)
    else:
        print("因無法載入圖層對應表，程式已停止。")