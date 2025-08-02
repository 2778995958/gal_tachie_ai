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

def main():
    """
    主執行函式，處理所有批次任務。
    """
    print("===== 開始批次合成任務 =====")
    
    # 2. 建立輸出資料夾
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 3. 遍歷 face 資料夾中的每一個角色子資料夾
    if not os.path.isdir(FACE_DIR):
        print(f"[錯誤] 'face' 資料夾不存在！")
        return

    for face_folder_name in os.listdir(FACE_DIR):
        # 取得角色 ID (例如從 '00040004F' 得到 '00040004')
        if not face_folder_name.endswith('F'):
            continue
        char_id = face_folder_name[:-1]
        
        print(f"\n--- 正在處理角色 ID: {char_id} ---")
        
        # 4. 構建對應的路徑
        face_folder_path = os.path.join(FACE_DIR, face_folder_name)
        body_filename = f"{char_id}P000.png"
        body_path = os.path.join(FUKU_DIR, body_filename)

        # 檢查對應的身體檔案是否存在
        if not os.path.isfile(body_path):
            print(f"  [跳過] 找不到對應的身體檔案: {body_path}")
            continue

        # 5. 尋找該角色的所有表情圖片
        expression_files = [f for f in os.listdir(face_folder_path) if f.endswith('.png')]
        if not expression_files:
            print(f"  [跳過] 在 {face_folder_path} 中找不到任何 .png 表情檔案。")
            continue
            
        # 6. 【最佳化】僅使用第一張表情來定位座標
        print("  [定位] 使用第一張表情計算座標...")
        template_face_path = os.path.join(face_folder_path, expression_files[0])
        print(f"    - 模板: {template_face_path}")
        print(f"    - 身體: {body_path}")
        
        coords = find_coordinates(body_path, template_face_path)
        
        if coords is None:
            print(f"  [錯誤] 無法為角色 {char_id} 定位座標。跳過此角色。")
            continue
            
        print(f"  [成功] 座標已定位: {coords}。現在開始合成所有表情。")

        # 7. 套用座標到該角色的所有表情上
        
        # 為了合成，用 Pillow 載入一次身體圖片
        body_pil = Image.open(body_path).convert("RGBA")
        
        # 建立該角色的專屬輸出資料夾
        char_output_dir = os.path.join(OUTPUT_DIR, char_id)
        os.makedirs(char_output_dir, exist_ok=True)
        
        for exp_filename in expression_files:
            try:
                expression_path = os.path.join(face_folder_path, exp_filename)
                expression_pil = Image.open(expression_path).convert("RGBA")
                
                # 建立一個身體圖片的副本來進行貼上，避免在原圖上重複操作
                final_image = body_pil.copy()
                
                # 使用 Pillow 的 paste 功能進行完美合成
                final_image.paste(expression_pil, coords, expression_pil)
                
                # 組合出輸出的檔案名稱
                output_filename = f"{char_id}_{os.path.splitext(exp_filename)[0]}.png"
                output_path = os.path.join(char_output_dir, output_filename)
                
                # 儲存結果
                final_image.save(output_path)
                print(f"    -> 已合成並儲存: {output_path}")

            except Exception as e:
                print(f"    [錯誤] 在合成檔案 {exp_filename} 時發生錯誤: {e}")

    print("\n===== 所有任務完成 =====")


# 執行主函式
if __name__ == "__main__":
    main()