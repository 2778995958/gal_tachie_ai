# 1. 匯入必要的函式庫
import os
import cv2
import numpy as np
from PIL import Image

# ==============================================================================
# 變數設定
# ==============================================================================
FACE_DIR = 'face'
FUKU_DIR = 'fuku'
OUTPUT_DIR = 'output'  # 所有合成結果會儲存在這裡

# 我們將使用最穩健的「模板匹配」方法
# TM_CCOEFF_NORMED 在多數情況下效果最好
MATCH_METHOD = cv2.TM_CCOEFF_NORMED
# ==============================================================================

def find_coordinates(body_path, template_face_path):
    """
    使用模板匹配找到臉部在身體上的最佳座標。(已修正格式問題)

    :param body_path: 身体圖片的路徑
    :param template_face_path: 用於定位的模板表情圖片路徑
    :return: 找到的左上角座標 (x, y)，如果失敗則回傳 None
    """
    try:
        body_img = cv2.imread(body_path, cv2.IMREAD_UNCHANGED)
        template_img = cv2.imread(template_face_path, cv2.IMREAD_UNCHANGED)

        if body_img is None or template_img is None:
            print(f"    [錯誤] 無法讀取圖片: {body_path} 或 {template_face_path}")
            return None

        # --- 👇 這是修正的核心部分 👇 ---
        
        # 1. 檢查並處理身體圖片的格式
        # 如果圖片是 4 通道 (BGRA)，就將其轉換為 3 通道 (BGR)
        if body_img.shape[2] == 4:
            body_img = cv2.cvtColor(body_img, cv2.COLOR_BGRA2BGR)
            
        # 2. 檢查並處理模板圖片的格式
        # 同樣，如果模板是 4 通道，也轉換為 3 通道
        if template_img.shape[2] == 4:
            template_img = cv2.cvtColor(template_img, cv2.COLOR_BGRA2BGR)
            
        # --- 👆 修正結束 👆 ---

        # 現在兩張圖片保證都是 BGR 格式，可以安全地進行模板匹配
        result = cv2.matchTemplate(body_img, template_img, cv2.TM_CCOEFF_NORMED)
        _, _, _, max_loc = cv2.minMaxLoc(result)
        
        return max_loc # max_loc is (x, y)
    
    except Exception as e:
        print(f"    [錯誤] 在模板匹配中發生錯誤: {e}")
        return None

# find_coordinates 函式保持不變，我們只更新 main 函式

def main():
    """
    主執行函式，處理所有批次任務。(採用身體輪廓作為遮罩)
    """
    print("===== 開始批次合成任務 (採用身體輪廓遮罩模式) =====")
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    if not os.path.isdir(FACE_DIR):
        print(f"[錯誤] '{FACE_DIR}' 資料夾不存在！")
        return

    for face_folder_name in os.listdir(FACE_DIR):
        if not face_folder_name.endswith('F'):
            continue
        char_id = face_folder_name[:-1]
        
        print(f"\n--- 正在處理角色 ID: {char_id} ---")
        
        face_folder_path = os.path.join(FACE_DIR, face_folder_name)
        body_filename = f"{char_id}P000.png"
        body_path = os.path.join(FUKU_DIR, body_filename)

        if not os.path.isfile(body_path):
            print(f"  [跳過] 找不到對應的身體檔案: {body_path}")
            continue

        expression_files = [f for f in os.listdir(face_folder_path) if f.lower().endswith('.png')]
        if not expression_files:
            print(f"  [跳過] 在 {face_folder_path} 中找不到任何 .png 表情檔案。")
            continue
            
        print("  [定位] 使用第一張表情計算座標...")
        template_face_path = os.path.join(face_folder_path, expression_files[0])
        
        coords = find_coordinates(body_path, template_face_path)
        
        if coords is None:
            print(f"  [錯誤] 無法為角色 {char_id} 定位座標。跳過此角色。")
            continue
            
        print(f"  [成功] 座標已定位: {coords}。現在開始合成所有表情。")

        # 為了合成，用 Pillow 載入身體圖片
        body_pil = Image.open(body_path).convert("RGBA")
        
        char_output_dir = os.path.join(OUTPUT_DIR, char_id)
        os.makedirs(char_output_dir, exist_ok=True)
        
        for exp_filename in expression_files:
            try:
                expression_path = os.path.join(face_folder_path, exp_filename)
                expression_pil = Image.open(expression_path).convert("RGBA")
                
                # --- 👇 這是實現你想法的核心邏輯 👇 ---
                
                # 1. 取得表情自身的遮罩 (Mask A)
                mask_expression = expression_pil.getchannel('A')

                # 2. 取得身體對應區域的遮罩 (Mask B)
                x, y = coords
                w, h = expression_pil.size
                # 定義表情將要貼上的方框區域
                box = (x, y, x + w, y + h) 
                # 從身體圖片上裁切出這個區域
                body_region_pil = body_pil.crop(box) 
                # 取得這個區域的遮罩
                mask_body = body_region_pil.getchannel('A')

                # 3. 計算最終的「有效貼上範圍」遮罩 (A & B)
                # 將 Pillow 遮罩轉為 NumPy 陣列以進行位元運算，效率最高
                mask_expression_np = np.array(mask_expression)
                mask_body_np = np.array(mask_body)
                # cv2.bitwise_and 會找出兩個遮罩重疊(都不透明)的部分
                final_mask_np = cv2.bitwise_and(mask_expression_np, mask_body_np)
                
                # 將合併後的 NumPy 遮罩轉回 Pillow Image 物件
                final_mask_pil = Image.fromarray(final_mask_np)

                # 4. 使用最終遮罩進行貼上
                # 建立一個身體圖片的副本來進行貼上
                final_image = body_pil.copy()
                final_image.paste(expression_pil, coords, final_mask_pil)
                
                # --- 👆 核心邏輯結束 👆 ---
                
                output_filename = f"{char_id}_{os.path.splitext(exp_filename)[0]}.png"
                output_path = os.path.join(char_output_dir, output_filename)
                
                final_image.save(output_path)
                print(f"    -> 已合成並儲存: {output_path}")

            except Exception as e:
                print(f"    [錯誤] 在合成檔案 {exp_filename} 時發生錯誤: {e}")

    print("\n===== 所有任務完成 =====")


# 執行主函式
if __name__ == "__main__":
    # 確保你定義了其他必要的全域變數
    FACE_DIR = 'face'
    FUKU_DIR = 'fuku'
    OUTPUT_DIR = 'output'
    main()
