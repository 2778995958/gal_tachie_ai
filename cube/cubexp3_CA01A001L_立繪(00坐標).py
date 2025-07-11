import os
import glob
from PIL import Image
from collections import defaultdict

# --- 1. 設定區 ---
SOURCE_IMAGES_DIR = 'images'
OUTPUT_DIR = 'output_images'

def process_image_groups():
    """
    主函式，負責掃描圖片、分組並進行合成。
    """
    print("▶️  開始掃描來源資料夾...")
    # 建立一個路徑來尋找所有 png 圖片
    source_path_pattern = os.path.join(SOURCE_IMAGES_DIR, '*.png')
    all_image_paths = glob.glob(source_path_pattern)

    if not all_image_paths:
        print(f"❌ 錯誤：在 '{SOURCE_IMAGES_DIR}' 資料夾中找不到任何 .png 檔案。")
        return

    print(f"🔍 找到了 {len(all_image_paths)} 張圖片。現在開始分組...")

    # 使用 defaultdict 自動建立清單來儲存分組後的檔案路徑
    # defaultdict(list) 的意思是，當我們存取一個不存在的 key 時，它會自動建立一個空清單
    image_groups = defaultdict(list)
    for img_path in all_image_paths:
        # os.path.basename 會取得檔案名稱 (例如 "CA01X001L.png")
        filename = os.path.basename(img_path)
        # 取得前 5 個字元作為群組的 key
        group_key = filename[:5]
        image_groups[group_key].append(img_path)

    print(f"✅ 分組完成！總共有 {len(image_groups)} 個角色群組。")
    print("-" * 30)

    # 確保主輸出資料夾存在
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 遍歷每一個群組來處理
    for group_key, file_paths in image_groups.items():
        print(f"\n✨ 正在處理群組: {group_key}")

        # 依字母順序排序，確保第一個是基礎圖 (例如 001L 會在 002M 前面)
        file_paths.sort()

        # 第一個檔案就是我們的基礎圖
        base_image_path = file_paths[0]
        # 剩下的是要疊加的圖層
        layer_image_paths = file_paths[1:]

        # 為這個角色群組建立專屬的輸出資料夾
        character_output_dir = os.path.join(OUTPUT_DIR, group_key)
        os.makedirs(character_output_dir, exist_ok=True)
        print(f"  > 已建立/確認輸出資料夾: {character_output_dir}")

        try:
            # 載入基礎圖
            base_img = Image.open(base_image_path).convert("RGBA")
            base_filename = os.path.basename(base_image_path)
            
            # --- 步驟 1: 儲存基礎圖 ---
            output_base_path = os.path.join(character_output_dir, base_filename)
            if os.path.exists(output_base_path):
                print(f"  [✓] 基礎圖已存在，跳過: {base_filename}")
            else:
                base_img.save(output_base_path)
                print(f"  [+] 已儲存基礎圖: {base_filename}")

            # 如果這個群組只有一張圖，就沒有圖層要處理
            if not layer_image_paths:
                print("  > 此群組只有一張基礎圖，沒有其他圖層。")
                continue

            # --- 步驟 2: 合成並儲存每一個圖層 ---
            for layer_path in layer_image_paths:
                layer_filename = os.path.basename(layer_path)
                output_composite_path = os.path.join(character_output_dir, layer_filename)

                if os.path.exists(output_composite_path):
                    print(f"    [✓] 合成圖已存在，跳過: {layer_filename}")
                    continue

                print(f"    合成中: {base_filename} + {layer_filename} ...")
                try:
                    layer_img = Image.open(layer_path).convert("RGBA")
                    
                    # 建立一個基礎圖的複本來進行貼上，避免汙染原始基礎圖
                    composite_img = base_img.copy()
                    
                    # 進行貼上，座標為 (0,0)，使用圖層本身作為遮罩以處理透明度
                    composite_img.paste(layer_img, (0, 0), layer_img)
                    
                    # 儲存合成後的圖片
                    composite_img.save(output_composite_path)

                except FileNotFoundError:
                    print(f"    ! 警告：找不到圖層檔案 {layer_path}，跳過此組合。")
                except Exception as e:
                    print(f"    ! 錯誤：處理 {layer_filename} 時發生錯誤: {e}")

        except FileNotFoundError:
            print(f"  ! 錯誤：找不到基礎圖檔案 {base_image_path}，跳過此群組。")
        except Exception as e:
            print(f"  ! 處理群組 {group_key} 時發生未預期的錯誤: {e}")

    print(f"\n--- ✅ 所有圖片群組處理完成！ ---")


# --- 程式執行的進入點 ---
if __name__ == "__main__":
    process_image_groups()