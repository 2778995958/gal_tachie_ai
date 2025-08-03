import cv2
import numpy as np
from PIL import Image
import os
import glob
from collections import Counter

def slice_by_corner_matching(image_path, output_dir, patch_size=50, threshold=0.75):
    """
    (使用者策略版：特徵點星座定位法)
    透過匹配原圖四個角的特徵，來定位並裁切每一個獨立的 Sprite。
    """
    try:
        print(f"  > [策略初始化] 載入圖片並學習角落特徵...")
        source_image = cv2.imread(image_path)
        if source_image is None:
            print(f"  > ⚠️ 錯誤：無法讀取圖片 {os.path.basename(image_path)}")
            return

        h, w = source_image.shape[:2]
        base_name = os.path.splitext(os.path.basename(image_path))[0]
        
        # 1. 學習角落特徵樣本
        # 確保 patch_size 不會超過圖片尺寸
        ps = min(patch_size, w // 2, h // 2)
        if ps == 0:
            print("  > ⚠️ 圖片尺寸過小，無法執行此策略。")
            return

        template_tl = source_image[0:ps, 0:ps]
        template_tr = source_image[0:ps, w-ps:w]
        
        print(f"  > [特徵學習完成] 左上角樣本尺寸: {ps}x{ps}, 右上角樣本尺寸: {ps}x{ps}")

        # 2. 搜尋所有特徵匹配點
        print(f"  > [全圖搜尋] 正在尋找所有左上角和右上角的匹配點...")
        res_tl = cv2.matchTemplate(source_image, template_tl, cv2.TM_CCOEFF_NORMED)
        loc_tl = np.where(res_tl >= threshold)

        res_tr = cv2.matchTemplate(source_image, template_tr, cv2.TM_CCOEFF_NORMED)
        loc_tr = np.where(res_tr >= threshold)

        # 3. 過濾與配對匹配點
        # 過濾相鄰的點，得到更精確的候選列表
        def filter_points(locations, patch_size):
            points = []
            for pt in zip(*locations[::-1]): # (x, y)
                is_overlapping = False
                for p_stored in points:
                    if abs(pt[0] - p_stored[0]) < patch_size * 0.5 and abs(pt[1] - p_stored[1]) < patch_size * 0.5:
                        is_overlapping = True
                        break
                if not is_overlapping:
                    points.append(pt)
            return sorted(points)

        tl_points = filter_points(loc_tl, ps)
        tr_points = filter_points(loc_tr, ps)
        
        print(f"  > [搜尋完成] 找到 {len(tl_points)} 個左上角候選點，{len(tr_points)} 個右上角候選點。")
        if not tl_points or not tr_points:
            print(f"  > ⚠️ 未能找到足夠的特徵點，請嘗試降低 CORNER_MATCH_THRESHOLD。")
            return

        # 4. 尋找最可能的 Sprite 寬度並確定所有裁切框
        print(f"  > [配對分析] 正在尋找最佳的 Sprite 寬度...")
        width_candidates = []
        for p_tl in tl_points:
            for p_tr in tr_points:
                # 條件：y座標非常接近，且 tr 在 tl 右邊
                if abs(p_tl[1] - p_tr[1]) < 5 and p_tr[0] > p_tl[0]:
                    width_candidates.append(p_tr[0] - p_tl[0] + ps)
        
        if not width_candidates:
            print(f"  > ⚠️ 無法配對任何左上角與右上角特徵點。")
            return

        # 投票選出最常見的寬度
        width_counts = Counter(width_candidates)
        most_common_width = width_counts.most_common(1)[0][0]
        print(f"  > [寬度確定] 最有可能的 Sprite 寬度為: {most_common_width} 像素。")

        # 5. 根據左上角點和計算出的寬度，定義所有裁切框
        print(f"  > [最終裁切] 根據 {len(tl_points)} 個左上角定位點進行裁切...")
        pil_img = Image.open(image_path)
        
        specific_output_folder = os.path.join(output_dir, base_name)
        os.makedirs(specific_output_folder, exist_ok=True)
        
        for i, (x, y) in enumerate(tl_points):
            box = (x, 0, x + most_common_width, h) # y 從0開始，高度為整張圖高
            cropped_img = pil_img.crop(box)
            
            output_filename = f"{base_name}_{i+1:03}.png"
            output_path = os.path.join(specific_output_folder, output_filename)
            cropped_img.save(output_path, 'PNG')
            
        print(f"  > [裁切完成] 已成功儲存 {len(tl_points)} 張裁切圖片。")

    except Exception as e:
        print(f"  > ❌ 處理 '{os.path.basename(image_path)}' 時發生致命錯誤: {e}")


# --- 主程式執行區 (全新) ---
if __name__ == "__main__":
    SOURCE_FOLDER = 'png'
    MAIN_OUTPUT_FOLDER = 'cropped_by_user_strategy'

    # --- 參數調整區 ---
    # 參數1: 從角落抓取特徵樣本的大小（像素）
    CORNER_PATCH_SIZE = 20 

    # 參數2: 模板匹配的相似度閾值 (0.0 到 1.0)
    # 如果找不到足夠的特徵點，可以適當降低此數值，例如 0.7
    CORNER_MATCH_THRESHOLD = 0.9
    # ------------------

    print("===== 開始執行「特徵點星座定位法」裁切 =====")
    print(f"設定: 樣本尺寸={CORNER_PATCH_SIZE}px, 匹配閾值={CORNER_MATCH_THRESHOLD}")
    
    os.makedirs(MAIN_OUTPUT_FOLDER, exist_ok=True)
    
    image_paths = glob.glob(os.path.join(SOURCE_FOLDER, '*.png')) + \
                  glob.glob(os.path.join(SOURCE_FOLDER, '*.jpg'))

    if not image_paths:
        print(f"在 '{SOURCE_FOLDER}' 資料夾中找不到任何圖片檔案。")
    else:
        for path in image_paths:
            print(f"\n--- 正在分析圖片: {os.path.basename(path)} ---")
            slice_by_corner_matching(path, MAIN_OUTPUT_FOLDER, CORNER_PATCH_SIZE, CORNER_MATCH_THRESHOLD)


    print("\n===== 所有圖片均已處理完成！ =====")
