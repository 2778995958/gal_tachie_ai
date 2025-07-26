import os
import csv
from PIL import Image, ImageChops

# --- 設定 ---
# 包含所有來源圖片 (bg, cg 等) 的資料夾
SOURCE_FOLDER = 'cg' 
# 輸出資料夾
OUTPUT_FOLDER = 'output'
# 規則定義檔
DEFINITION_FILE = 'visual.txt'

def parse_definitions(filepath):
    """
    解析 visual.txt 檔案，回傳一個包含所有合成任務的列表。
    """
    if not os.path.exists(filepath):
        print(f"[嚴重錯誤] 規則檔案 '{filepath}' 不存在！")
        return None

    tasks = []
    with open(filepath, 'r', encoding='utf-8') as f:
        # 使用 csv.reader 來處理帶有引號的欄位
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            # 忽略空行或註解行
            if not row or row[0].strip().startswith('//'):
                continue
            
            try:
                # 1. 提取色調 (前三個值)
                tint_color = tuple(map(int, row[0:3]))

                # 2. 提取所有圖片檔名 (尋找包含 .png 的欄位)
                image_layers = [
                    field.strip() for field in row if field.strip().lower().endswith('.png')
                ]

                if not image_layers:
                    continue

                # 3. 決定輸出檔名：通常是最後一個圖層的檔名
                #    如果只有一個圖層，輸出檔名就是它自己
                output_filename = image_layers[-1]

                tasks.append({
                    "line_num": i + 1,
                    "tint": tint_color,
                    "layers": image_layers,
                    "output_name": output_filename
                })
            except (ValueError, IndexError) as e:
                print(f"[警告] 無法解析第 {i+1} 行: {row}。錯誤: {e}")

    return tasks

def main():
    """
    主函式，讀取規則、執行合成與色調調整。
    """
    print("--- 開始執行規則檔驅動的圖片合成任務 ---")

    # 檢查來源資料夾是否存在
    if not os.path.isdir(SOURCE_FOLDER):
        print(f"[嚴重錯誤] 來源資料夾 '{SOURCE_FOLDER}' 不存在！")
        return

    # 讀取並解析 visual.txt
    tasks = parse_definitions(DEFINITION_FILE)
    if tasks is None:
        return
        
    print(f"從 '{DEFINITION_FILE}' 中成功解析 {len(tasks)} 個合成任務。")

    # 建立輸出資料夾
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    # 逐一執行合成任務
    for task in tasks:
        output_path = os.path.join(OUTPUT_FOLDER, task['output_name'])
        
        # 檢查輸出檔案是否已存在，若存在則跳過
        if os.path.exists(output_path):
            # print(f"[跳過] 檔案已存在: {output_path}")
            continue
        
        print(f"--- 正在處理: {task['output_name']} (來源行: {task['line_num']}) ---")
        
        try:
            # 1. 開啟基礎圖片
            base_image_path = os.path.join(SOURCE_FOLDER, task['layers'][0])
            composed_img = Image.open(base_image_path).convert('RGBA')

            # 2. 疊加其他圖層 (如果有的話)
            if len(task['layers']) > 1:
                for layer_name in task['layers'][1:]:
                    layer_path = os.path.join(SOURCE_FOLDER, layer_name)
                    with Image.open(layer_path).convert('RGBA') as layer_img:
                        print(f"  > 疊加圖層: {layer_name}")
                        composed_img.paste(layer_img, (0, 0), mask=layer_img)
            
            # 3. 套用色調濾鏡
            tint_color = task['tint']
            # 如果色調不是純白 (255,255,255)，則進行處理
            if tint_color != (255, 255, 255):
                print(f"  > 套用色調: {tint_color}")
                # 建立一個與圖片同尺寸的純色圖層
                tint_layer = Image.new('RGBA', composed_img.size, tint_color)
                # 使用 "multiply" 混合模式來上色，這能有效保留暗部細節
                composed_img = ImageChops.multiply(composed_img, tint_layer)

            # 4. 儲存最終結果
            composed_img.save(output_path, 'PNG')
            print(f"  -> 已成功儲存至: {output_path}")

        except FileNotFoundError as e:
            print(f"  [錯誤] 找不到檔案: {e.filename}。請檢查檔案是否存在於 '{SOURCE_FOLDER}'。")
        except Exception as e:
            print(f"  [錯誤] 處理 {task['output_name']} 時發生未知錯誤: {e}")

    print("\n--- 所有任務已完成 ---")

if __name__ == '__main__':
    main()