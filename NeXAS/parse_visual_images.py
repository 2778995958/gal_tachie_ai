import os
import pandas as pd
from PIL import Image
import glob

# --- 1. 設定區 ---
# 你的原始圖片來源資料夾
SOURCE_IMAGES_DIR = 'images'
# 所有合成圖片會直接儲存在這個資料夾，不再有子資料夾
OUTPUT_DIR = 'output_images'

# --- 2. 處理單一 CSV 檔案的函式 (已更新) ---
def process_csv_file(csv_path):
    """
    此函式負責處理單一一個 CSV 檔案的圖片合成邏輯。
    """
    print(f"\n{'='*25}")
    print(f"▶️  開始處理檔案: {csv_path}")
    print(f"{'='*25}")

    try:
        df = pd.read_csv(csv_path)
        grouped = df.groupby('base_filename')

        for base_name, group_df in grouped:
            # [修改] 移除了角色代碼(character_code)的分組邏輯
            print(f"\n--- 正在處理基於底圖 '{base_name}' 的合成 ---")

            base_image_path = os.path.join(SOURCE_IMAGES_DIR, base_name)
            
            try:
                base_img = Image.open(base_image_path).convert("RGBA")
                print(f"  > 已載入底圖: {base_name}")

                # [修改] 輸出路徑直接使用主輸出資料夾
                output_base_path = os.path.join(OUTPUT_DIR, base_name)
                if not os.path.exists(output_base_path):
                    base_img.save(output_base_path)
                    print(f"  > 已複製底圖至輸出資料夾")
                else:
                    print(f"  [✓] 底圖已存在: {base_name}")

            except FileNotFoundError:
                print(f"  ! 錯誤：找不到底圖檔案 {base_image_path}，跳過此群組。")
                continue

            for index, row in group_df.iterrows():
                if pd.isna(row['delta_filename']):
                    continue

                output_filename = row['delta_filename']
                # [修改] 輸出路徑直接使用主輸出資料夾
                output_path = os.path.join(OUTPUT_DIR, output_filename)

                if os.path.exists(output_path):
                    print(f"    [✓] 已存在，跳過: {output_filename}")
                    continue

                print(f"    合成中: {output_filename} ...")
                
                try:
                    delta_image_name = row['delta_filename']
                    delta_image_path = os.path.join(SOURCE_IMAGES_DIR, delta_image_name)
                    paste_x, paste_y = row['offset_x'], row['offset_y']
                    
                    delta_img = Image.open(delta_image_path).convert("RGBA")
                    composite_img = base_img.copy()
                    composite_img.paste(delta_img, (paste_x, paste_y), delta_img)
                    composite_img.save(output_path)

                except FileNotFoundError:
                    print(f"    ! 警告：找不到差分圖檔案 {delta_image_name}，跳過此組合。")
                except Exception as e:
                    print(f"    ! 錯誤：處理 {output_filename} 時發生錯誤: {e}")

    except Exception as e:
        print(f"處理檔案 {csv_path} 時發生未預期的錯誤: {e}")

# --- 3. 程式主體：尋找並遍歷所有 CSV (維持不變) ---
def main():
    """
    主執行函式，負責尋找所有 CSV 檔案，並逐一處理。
    """
    csv_files = ['visual.csv']
    if not os.path.exists(csv_files[0]):
        print(f"在專案目錄中找不到 {csv_files[0]} 檔案，程式即將結束。")
        return

    print(f"總共找到 {len(csv_files)} 個 CSV 檔案: {', '.join(csv_files)}")
    
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"已建立輸出資料夾: {OUTPUT_DIR}")
        
    for file_path in csv_files:
        process_csv_file(file_path)
        
    print(f"\n--- ✅ 所有 CSV 檔案處理完成！ ---")

# --- 程式執行的進入點 ---
if __name__ == "__main__":
    main()
