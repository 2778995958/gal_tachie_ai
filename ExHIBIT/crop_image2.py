import cv2
import numpy as np
from PIL import Image
import os
import glob
from collections import Counter

# 請只用這個函式，替換掉你程式碼中的同名函式

def slice_by_grid_learning(image_path, output_dir, patch_size=30, threshold=0.7):
    """
    (最終完美版：嚴格均切 Pizza 策略)
    1. 學習網格規則。
    2. 根據規則進行嚴格等距、等尺寸的裁切，不對切片做任何額外處理。
    """
    try:
        print(f"  > [策略初始化] 載入圖片...")
        source_image = cv2.imread(image_path)
        if source_image is None:
            print(f"  > ⚠️ 錯誤：無法讀取圖片 {os.path.basename(image_path)}")
            return

        h, w = source_image.shape[:2]
        base_name = os.path.splitext(os.path.basename(image_path))[0]
        
        # --- 步驟一：學習網格規則 (此部分不變) ---
        print(f"  > [學習階段] 正在偵測特徵點以學習網格規則...")
        ps = min(patch_size, w // 4, h // 4)
        if ps < 10:
            print("  > ⚠️ 圖片尺寸過小或patch_size設定過小，無法執行此策略。")
            return
            
        template_tl = source_image[0:ps, 0:ps]
        res_tl = cv2.matchTemplate(source_image, template_tl, cv2.TM_CCOEFF_NORMED)
        loc_tl = np.where(res_tl >= threshold)

        def filter_points(locations, patch_size):
            points = []
            for pt in zip(*locations[::-1]):
                if not any(abs(pt[0] - p_stored[0]) < patch_size * 0.5 and abs(pt[1] - p_stored[1]) < patch_size * 0.5 for p_stored in points):
                    points.append(pt)
            return sorted(points)

        tl_points = filter_points(loc_tl, ps)
        
        if len(tl_points) < 2:
            print(f"  > ⚠️ 未能找到足夠的特徵點來推斷網格。請嘗試降低 CORNER_MATCH_THRESHOLD。")
            Image.open(image_path).save(os.path.join(output_dir, f"{base_name}_uncut.png"), 'PNG')
            return

        rows = {}
        for x, y in tl_points:
            found_row = False
            for row_y in rows:
                if abs(y - row_y) < ps:
                    rows[row_y].append(x)
                    found_row = True
                    break
            if not found_row:
                rows[y] = [x]
        
        x_steps = []
        for row_y in rows:
            row_xs = sorted(rows[row_y])
            for i in range(len(row_xs) - 1):
                x_steps.append(row_xs[i+1] - row_xs[i])
        
        if not x_steps:
             print(f"  > ⚠️ 找到的特徵點無法構成多列網格。")
             Image.open(image_path).save(os.path.join(output_dir, f"{base_name}_uncut.png"), 'PNG')
             return

        most_common_step = Counter(x_steps).most_common(1)[0][0]
        row_y_coords = sorted(rows.keys())
        start_x = min(x for row in rows.values() for x in row)

        print(f"  > [學習完成] 網格規則 -> 水平步長/寬度: {most_common_step}px, 總行數: {len(row_y_coords)}")

        # --- 步驟二：應用規則進行嚴格均勻裁切 ---
        print(f"  > [裁切階段] 正在根據學習到的網格規則進行嚴格均切...")
        pil_img = Image.open(image_path)
        specific_output_folder = os.path.join(output_dir, base_name)
        os.makedirs(specific_output_folder, exist_ok=True)
        
        count = 0
        # 假設所有表情的高度都一樣，等於原圖高度
        sprite_h = h 

        for row_y in row_y_coords:
            num_cols = (w - start_x) // most_common_step + 1
            for i in range(num_cols):
                # 根據學習到的規則，計算出每一個網格的精確位置
                x = start_x + i * most_common_step
                
                # 如果計算出的下一個切片起點已經非常靠近圖片邊緣，則停止
                if x > w - most_common_step * 0.5: break

                # 定義嚴格的、等尺寸的裁切框
                box = (x, 0, x + most_common_step, sprite_h)
                cropped_img = pil_img.crop(box)

                # ✨✨✨ 關鍵修正點：刪除了裁掉空白的程式碼 ✨✨✨
                # 現在，cropped_img 會被直接儲存，保留其原始的、均一的網格尺寸。

                count += 1
                output_filename = f"{base_name}_{count:03}.png"
                output_path = os.path.join(specific_output_folder, output_filename)
                cropped_img.save(output_path, 'PNG')

        print(f"  > [裁切完成] 已成功儲存 {count} 張尺寸均一的圖片。")

    except Exception as e:
        print(f"  > ❌ 處理 '{os.path.basename(image_path)}' 時發生致命錯誤: {e}")

# --- 主程式執行區 ---
if __name__ == "__main__":
    SOURCE_FOLDER = 'png'
    MAIN_OUTPUT_FOLDER = 'cropped_pizza_cut'

    # --- 參數調整區 ---
    CORNER_PATCH_SIZE = 20 # 可以嘗試減小此值，例如 30 或 20
    CORNER_MATCH_THRESHOLD = 0.9
    # ------------------

    print("===== 開始執行「Pizza均切」策略 =====")
    print(f"設定: 樣本尺寸={CORNER_PATCH_SIZE}px, 匹配閾值={CORNER_MATCH_THRESHOLD}")
    
    os.makedirs(MAIN_OUTPUT_FOLDER, exist_ok=True)
    
    image_paths = glob.glob(os.path.join(SOURCE_FOLDER, '*.png')) + \
                  glob.glob(os.path.join(SOURCE_FOLDER, '*.jpg'))

    if not image_paths:
        print(f"在 '{SOURCE_FOLDER}' 資料夾中找不到任何圖片檔案。")
    else:
        for path in image_paths:
            print(f"\n--- 正在分析圖片: {os.path.basename(path)} ---")
            slice_by_grid_learning(path, MAIN_OUTPUT_FOLDER, CORNER_PATCH_SIZE, CORNER_MATCH_THRESHOLD)

    print("\n===== 所有圖片均已處理完成！ =====")
