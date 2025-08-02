from PIL import Image
import os
import glob

# 這個函式本身不需要任何修改，因為它的設計已經足夠靈活
def process_and_save_image(image_path, num_divisions, main_output_dir):
    """
    將單一圖片進行水平裁切，並儲存到指定的主輸出資料夾中。
    """
    try:
        base_name = os.path.splitext(os.path.basename(image_path))[0]
        
        output_folder = os.path.join(main_output_dir, base_name)

        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        img = Image.open(image_path)
        width, height = img.size
        
        # 為了避免重複輸出處理訊息，將其移到主迴圈中
        # print(f"處理中: {image_path} ...") 

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

        # 為了避免洗版，可以在成功時保持安靜，或只輸出簡易訊息
        # print(f"✅ {base_name} 已成功處理並儲存 {num_divisions} 張裁切圖片。\n")

    except FileNotFoundError:
        print(f"❌ 錯誤：找不到檔案 '{image_path}'。")
    except Exception as e:
        print(f"❌ 處理 '{image_path}' 時發生未預期的錯誤: {e}")

# --- 主程式執行區 ---
if __name__ == "__main__":
    # --- 設定區 ---
    SOURCE_FOLDER = 'png'
    MAIN_OUTPUT_FOLDER = 'cropped'

    # --- ✨ 主要修改處 ✨ ---
    # 將單一數字改成一個清單(list)，裡面可以放所有你想測試的裁切數量
    DIVISION_SETTINGS = [27, 28, 29] # <--- 在這裡修改或增加你的設定

    print("===== 開始批次處理圖片 =====")
    
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
            # --- ✨ 主要修改處：使用雙層迴圈 ✨ ---

            # 第一層迴圈：遍歷所有圖片檔案
            for path in all_paths:
                if os.path.isfile(path):
                    print(f"\n--- 正在處理圖片: {path} ---")
                    # 第二層迴圈：遍歷你的所有裁切設定
                    for divisions in DIVISION_SETTINGS:
                        print(f"  > 應用設定: 裁切 {divisions} 等份...")
                        
                        # 建立以設定值為名的資料夾路徑，例如 'cropped/27'
                        setting_output_dir = os.path.join(MAIN_OUTPUT_FOLDER, str(divisions))
                        os.makedirs(setting_output_dir, exist_ok=True)

                        # 呼叫函式，傳入圖片路徑、當前的裁切數量、以及對應的輸出資料夾
                        process_and_save_image(path, divisions, setting_output_dir)

            print("\n===== 所有圖片及設定均已處理完成！ =====")
