import cv2
import numpy as np
from PIL import Image
import os
import glob
from collections import Counter

# calculate_grid_boxes 函式保持不變，無需修改
def calculate_grid_boxes(source_image, patch_size=30, threshold=0.7):
    try:
        h, w = source_image.shape[:2]
        ps = int(min(patch_size, w / 4, h / 4))
        if ps < 10: return None
        template_tl = source_image[0:ps, 0:ps]
        res_tl = cv2.matchTemplate(source_image, template_tl, cv2.TM_CCOEFF_NORMED)
        loc_tl = np.where(res_tl >= threshold)
        def filter_points(locations, patch_size_filter):
            points = []
            for pt in zip(*locations[::-1]):
                if not any(abs(pt[0] - p_stored[0]) < patch_size_filter and abs(pt[1] - p_stored[1]) < patch_size_filter for p_stored in points):
                    points.append(pt)
            return sorted(points)
        tl_points = filter_points(loc_tl, ps)
        if len(tl_points) < 2: return None
        rows = {}
        for x, y in tl_points:
            found_row = False
            for row_y in rows:
                if abs(y - row_y) < ps:
                    rows[row_y].append(x); found_row = True; break
            if not found_row: rows[y] = [x]
        all_x = sorted([x for row in rows.values() for x in row])
        cols = []
        for x in all_x:
            if not any(abs(x - cx) < ps for cx in cols):
                cols.append(x)
        num_cols = len(cols)
        if num_cols < 2: return None
        start_x = all_x[0]; end_x = all_x[-1]
        avg_step = (end_x - start_x) / (num_cols - 1)
        row_y_coords = sorted(rows.keys())
        sprite_h = h; boxes = []
        for row_y in row_y_coords:
            for i in range(num_cols):
                x = round(start_x + i * avg_step)
                width = round(avg_step)
                if x + width > w + 2: continue
                boxes.append((x, 0, width, sprite_h))
        return boxes
    except Exception:
        return None

# ✨ 總指揮函式更新 ✨
# 請只用這個函式，替換掉你程式碼中的同名函式

def process_image_with_verification(image_path, output_dir, params):
    """
    (總指揮)
    帶有品質檢驗與智能重試的總執行流程。
    (最終修正：失敗後，將原圖直接儲存在主輸出資料夾)
    """
    base_name = os.path.splitext(os.path.basename(image_path))[0]
    print(f"\n--- 正在處理圖片: {base_name}.png ---")

    try:
        source_image = cv2.imread(image_path)
        pil_img = Image.open(image_path)
        original_width = source_image.shape[1]

        current_threshold = params['threshold']
        current_patch_size = params['patch_size']
        
        for i in range(params['max_retries']):
            print(f"  > [嘗試 {i+1}/{params['max_retries']}] 使用參數 PatchSize={current_patch_size}, Threshold={current_threshold:.2f} 進行預演...")
            
            predicted_boxes = calculate_grid_boxes(source_image, current_patch_size, current_threshold)

            if predicted_boxes:
                min_x = min(box[0] for box in predicted_boxes)
                max_x_end = max(box[0] + box[2] for box in predicted_boxes)
                total_span_width = max_x_end - min_x
                print(f"    > [品質檢驗] 原始寬度: {original_width}, 預測網格總跨度: {total_span_width}, 数量: {len(predicted_boxes)}")

                if abs(original_width - total_span_width) <= params['width_tolerance']:
                    print(f"    > ✅ 驗證通過！網格尺寸精確。準備執行最終裁切...")
                    # 成功的圖片，放入子資料夾
                    specific_output_folder = os.path.join(output_dir, base_name)
                    os.makedirs(specific_output_folder, exist_ok=True)
                    for j, (x, y, w, h) in enumerate(predicted_boxes):
                        cropped_img = pil_img.crop((x, y, x + w, h))
                        cropped_img.save(os.path.join(specific_output_folder, f"{base_name}_{j+1:03}.png"), 'PNG')
                    print(f"  > [裁切完成] 已成功儲存 {len(predicted_boxes)} 張尺寸均一的圖片。")
                    return

            print(f"    > ⚠️ 驗證失敗或無法計算網格。準備根據策略 '{params['retry_strategy']}' 調整參數重試...")
            
            if params['retry_strategy'] == 'patch_size':
                current_patch_size -= params['patch_size_step']
                if current_patch_size < params['min_patch_size']:
                    print(f"  > ❌ PatchSize 已達下限，停止重試。")
                    break
            else:
                current_threshold -= params['threshold_step']
                if current_threshold < params['min_threshold']:
                    print(f"  > ❌ Threshold 已達下限，停止重試。")
                    break
        
        # ✨ 關鍵修正點：失敗後，將原圖儲存到最外層的主輸出資料夾 ✨
        print(f"  > ❌ 重試多次後仍無法得到完美結果。將儲存原圖至主輸出資料夾。")
        uncut_output_path = os.path.join(output_dir, f"{base_name}_UNCUT.png")
        pil_img.save(uncut_output_path, 'PNG')

    except Exception as e:
        print(f"  > ❌ 處理 '{base_name}.png' 時發生致命錯誤: {e}")

# --- ✨ 主程式執行區：擁有完整控制權 ✨ ---
if __name__ == "__main__":
    SOURCE_FOLDER = 'png'
    MAIN_OUTPUT_FOLDER = 'cropped_final_control'

    # --- 參數調整區 ---
    PARAMS = {
        # --- 初始參數 ---
        "patch_size": 20,           # 初始偵測樣本的大小 (像素)
        "threshold": 0.9,           # 初始相似度閾值 (建議設高一點，讓程式有空間可以降低)
        
        # --- 重試策略與參數 ---
        "retry_strategy": "patch_size", # "threshold" 或 "patch_size"，決定重試時要調整哪個參數
        "max_retries": 5,           # 智能重試的最大次數
        "threshold_step": 0.05,     # 如果策略是 a'threshold'，每次重試降低多少
        "patch_size_step": 2,       # 如果策略是 'patch_size'，每次重試減小多少像素
        "min_threshold": 0.65,      # 閾值的下限，低於此值則停止重試
        "min_patch_size": 10,       # PatchSize 的下限，低於此值則停止重試

        # --- 品質檢驗參數 ---
        "width_tolerance": 0        # 允許的最終寬度總誤差 (像素)
    }
    # ------------------

    print("===== 開始執行「可自訂策略的」最終裁切程式 =====")
    print(f"使用參數: {PARAMS}")
    
    os.makedirs(MAIN_OUTPUT_FOLDER, exist_ok=True)
    
    image_paths = glob.glob(os.path.join(SOURCE_FOLDER, '*.png')) + glob.glob(os.path.join(SOURCE_FOLDER, '*.jpg'))

    if not image_paths:
        print(f"在 '{SOURCE_FOLDER}' 資料夾中找不到任何圖片檔案。")
    else:
        for path in image_paths:
            process_image_with_verification(path, MAIN_OUTPUT_FOLDER, PARAMS)

    print("\n===== 所有圖片均已處理完成！ =====")
