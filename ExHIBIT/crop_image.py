from PIL import Image
import os
import glob

def process_and_save_image(image_path, num_divisions, main_output_dir): # <--- 修改：增加一個參數
    """
    將單一圖片進行水平裁切，並儲存到指定的主輸出資料夾中。

    :param image_path: 來源圖片的完整路徑
    :param num_divisions: 要裁切成的等份數量
    :param main_output_dir: 統一存放結果的主資料夾名稱 (例如 'cropped')
    """
    try:
        base_name = os.path.splitext(os.path.basename(image_path))[0]
        
        # --- ✨ 主要修改處 ✨ ---
        # 建立一個以原檔名命名的子資料夾，但路徑是在主輸出資料夾底下
        # 例如，路徑會變成 'cropped/00040000F'
        output_folder = os.path.join(main_output_dir, base_name)

        # 檢查子資料夾是否存在，不存在才建立
        # 注意：這裡我們假設主資料夾 'cropped' 已經在主程式區塊被建立了
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
            print(f"--- 已在 '{main_output_dir}' 中建立資料夾: {base_name} ---")

        img = Image.open(image_path)
        width, height = img.size
        print(f"處理中: {image_path} (尺寸: {width}x{height}, 模式: {img.mode})")

        crop_width = width // num_divisions

        for i in range(num_divisions):
            left = i * crop_width
            upper = 0
            right = (i + 1) * crop_width
            lower = height

            if i == num_divisions - 1:
                right = width

            box = (left, upper, right, lower)
            cropped_img = img.crop(box)

            output_filename = f"{base_name}_{i+1:03}.png"
            output_path = os.path.join(output_folder, output_filename)
            
            cropped_img.save(output_path, 'PNG')

        print(f"✅ {base_name} 已成功處理並儲存 {num_divisions} 張裁切圖片。\n")

    except FileNotFoundError:
        print(f"❌ 錯誤：找不到檔案 '{image_path}'。")
    except Exception as e:
        print(f"❌ 處理 '{image_path}' 時發生未預期的錯誤: {e}")

# --- 主程式執行區 ---
if __name__ == "__main__":
    # --- 設定區 ---
    SOURCE_FOLDER = 'png'
    NUMBER_OF_DIVISIONS = 27
    
    # --- ✨ 新增設定 ✨ ---
    # 設定統一輸出的主資料夾名稱
    MAIN_OUTPUT_FOLDER = 'cropped'

    print("===== 開始批次處理圖片 =====")
    
    # --- ✨ 新增動作 ✨ ---
    # 在開始處理前，先建立統一輸出的主資料夾 'cropped'
    # exist_ok=True 表示如果資料夾已經存在，也不會報錯
    os.makedirs(MAIN_OUTPUT_FOLDER, exist_ok=True)
    
    if not os.path.isdir(SOURCE_FOLDER):
        print(f"錯誤：找不到來源資料夾 '{SOURCE_FOLDER}'。")
    else:
        image_extensions = ('*.jpg', '*.jpeg', '*.png')
        all_paths = []
        for ext in image_extensions:
            all_paths.extend(glob.glob(os.path.join(SOURCE_FOLDER, ext)))

        if not all_paths:
            print(f"在 '{SOURCE_FOLDER}' 資料夾中找不到任何圖片檔案。")
        else:
            for path in all_paths:
                if os.path.isfile(path):
                    # --- ✨ 修改處 ✨ ---
                    # 呼叫函式時，把主輸出資料夾名稱傳遞進去
                    process_and_save_image(path, NUMBER_OF_DIVISIONS, MAIN_OUTPUT_FOLDER)
            
            print("===== 所有圖片處理完成！ =====")