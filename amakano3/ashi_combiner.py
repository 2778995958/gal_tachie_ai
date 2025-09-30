import sys
import os
from PIL import Image

def process_images(large_image_path, small_images_folder):
    """
    批量將一個帶腿的大圖，與資料夾中多個不帶腿的小圖進行合併。
    """
    # --- 1. 建立輸出資料夾 ---
    ### << 修改點 1: 新的輸出資料夾結構 ###
    # 取得小圖資料夾的名稱，例如 "no_leg_pics"
    small_folder_name = os.path.basename(os.path.normpath(small_images_folder))
    # 建立新的輸出路徑，例如 "output/no_leg_pics"
    output_folder = os.path.join("output", small_folder_name)
    
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    print(f"所有合併後的圖片將儲存至 '{output_folder}' 資料夾中。")

    # --- 2. 載入大圖 (腿部來源) ---
    try:
        legs_img = Image.open(large_image_path).convert('RGBA')
        print(f"成功讀取大圖: {os.path.basename(large_image_path)}")
    except FileNotFoundError:
        print(f"錯誤：找不到指定的大圖檔案 '{large_image_path}'")
        return
    except Exception as e:
        print(f"讀取大圖時發生錯誤: {e}")
        return

    # --- 3. 遍歷小圖資料夾並處理 ---
    file_count = 0
    success_count = 0
    for filename in os.listdir(small_images_folder):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
            file_count += 1
            small_image_path = os.path.join(small_images_folder, filename)
            
            try:
                print(f"\n--- 正在處理第 {file_count} 張圖: {filename} ---")
                base_img = Image.open(small_image_path).convert('RGBA')
                
                # --- 自動設定切割點 ---
                y_cut_on_small_image = base_img.height - 1
                if y_cut_on_small_image < 0: y_cut_on_small_image = 0
                
                # --- 核心計算邏輯 ---
                if base_img.width == 0:
                    print("錯誤：小圖寬度為 0，跳過此檔案。")
                    continue
                
                scale_ratio = legs_img.width / base_img.width
                y_cut_on_large_image = int(y_cut_on_small_image * scale_ratio)

                # --- 裁切與縮放 ---
                torso_crop = base_img.crop((0, 0, base_img.width, y_cut_on_small_image))
                legs_crop = legs_img.crop((0, y_cut_on_large_image, legs_img.width, legs_img.height))
                
                new_legs_width = torso_crop.width
                if original_legs_width := legs_crop.width:
                    new_legs_height = int((new_legs_width / original_legs_width) * legs_crop.height)
                    resized_legs = legs_crop.resize((new_legs_width, new_legs_height), Image.Resampling.LANCZOS)
                else:
                    resized_legs = legs_crop

                # --- 使用 alpha_composite 進行高品質合併 ---
                final_height = torso_crop.height + resized_legs.height
                final_width = torso_crop.width
                
                final_canvas = Image.new('RGBA', (final_width, final_height), (0, 0, 0, 0))
                final_canvas.paste(torso_crop, (0, 0))
                
                legs_layer = Image.new('RGBA', final_canvas.size, (0, 0, 0, 0))
                legs_layer.paste(resized_legs, (0, torso_crop.height))

                final_image = Image.alpha_composite(final_canvas, legs_layer)

                # --- 儲存結果 ---
                ### << 修改點 2: 新的輸出檔名規則 ###
                # 取得原始檔名（不含副檔名），並確保儲存為 .png
                output_filename = os.path.splitext(filename)[0] + '.png'
                
                output_path = os.path.join(output_folder, output_filename)
                final_image.save(output_path)
                print(f"✅ 成功合併！已儲存至: {output_path}")
                success_count += 1

            except Exception as e:
                print(f"處理檔案 {filename} 時發生錯誤: {e}")

    print(f"\n--- 處理完成 ---")
    print(f"總共掃描 {file_count} 張圖片，成功合併 {success_count} 張。")


if __name__ == "__main__":
    print("批量圖片合併工具 (v3)")
    print("="*30)
    if len(sys.argv) == 3:
        item1 = sys.argv[1]
        item2 = sys.argv[2]
        
        if os.path.isfile(item1) and os.path.isdir(item2):
            process_images(item1, item2)
        elif os.path.isdir(item1) and os.path.isfile(item2):
            process_images(item2, item1)
        else:
            print("錯誤：拖曳的項目必須是一個檔案和一個資料夾。")
    else:
        print("如何使用：")
        print("1. 將一個「大圖檔案」和一個存放「小圖的資料夾」準備好。")
        print("2. 同時選中這兩個項目。")
        print(f"3. 將它們一起拖曳到 '{os.path.basename(__file__)}' 這個檔案的圖示上。")
    
    input("\n按 Enter 鍵結束...")