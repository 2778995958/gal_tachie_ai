import os
import pandas as pd
from PIL import Image
import glob

# --- 1. 設定區 ---
# 原始圖片素材所在的資料夾名稱
SOURCE_IMAGES_DIR = 'images'
# 最終合成圖片要輸出的資料夾名稱
OUTPUT_DIR = 'output_images'

# --- 2. 處理單一 CSV 檔案的函式 ---
def process_csv_file(csv_path):
    """
    此函式負責讀取一個 CSV 檔案，並根據其內容進行圖片合成。
    """
    print(f"\n{'='*25}")
    print(f"▶️  開始處理檔案: {os.path.basename(csv_path)}")
    print(f"{'='*25}")

    try:
        # 讀取 CSV，並將任何空格或 NaN 值轉換為空字串，方便後續判斷
        df = pd.read_csv(csv_path).fillna('')
        # 根據 'base' 欄位進行分組，這樣可以一次處理好同一張底圖的所有差分
        grouped = df.groupby('base')

        # 遍歷每一個底圖群組
        for base_name, group_df in grouped:
            # 從底圖名稱取出角色代碼 (例如 'CA01A')
            character_code = base_name[:5]
            print(f"\n--- 正在處理基於底圖 '{base_name}' 的角色群組: {character_code} ---")

            # 建立該角色的專屬輸出資料夾
            character_output_dir = os.path.join(OUTPUT_DIR, character_code)
            if not os.path.exists(character_output_dir):
                os.makedirs(character_output_dir)

            # 組合出完整的底圖檔案路徑
            base_image_name = base_name + '.png'
            base_image_path = os.path.join(SOURCE_IMAGES_DIR, base_image_name)
            
            try:
                # 打開底圖檔案
                base_img = Image.open(base_image_path).convert("RGBA")
            except FileNotFoundError:
                print(f"  ! 警告：找不到底圖檔案 {base_image_name}，將跳過這個群組的所有圖片。")
                continue # 如果找不到底圖，就跳過這個群組，處理下一個

            # 遍歷這個群組中的每一筆資料 (也就是每一張要輸出的圖片)
            for index, row in group_df.iterrows():
                # 最終輸出的檔案名稱來自 'tag' 欄位
                output_filename = str(row['tag']) + '.png'
                output_path = os.path.join(character_output_dir, output_filename)

                # 如果檔案已經存在，就跳過，節省時間
                if os.path.exists(output_path):
                    print(f"    - 已存在，跳過: {output_filename}")
                    continue

                # 【核心邏輯】
                # 檢查 'diff' 欄位是否為空。
                # 如果是空的，代表這筆資料就是基底圖本身，不需要合成。
                if row['diff'] == '':
                    print(f"    儲存基底圖: {output_filename} ...")
                    try:
                        # 直接將底圖複製並儲存成目標檔名
                        base_img.save(output_path)
                    except Exception as e:
                        print(f"    ! 錯誤：儲存基底圖 {output_filename} 時發生錯誤: {e}")
                    # 處理完畢，跳到下一筆資料
                    continue

                # 如果程式執行到這裡，代表 'diff' 欄位有值，需要進行圖片合成
                print(f"    合成中: {output_filename} ...")
                
                try:
                    # 根據 CSV 的 'diff', 'x', 'y' 欄位來合成圖片
                    diff_image_name = str(row['diff']) + '.png'
                    diff_image_path = os.path.join(SOURCE_IMAGES_DIR, diff_image_name)
                    paste_x, paste_y = int(row['x']), int(row['y'])
                    
                    # 打開差分圖
                    diff_img = Image.open(diff_image_path).convert("RGBA")
                    # 複製一份底圖來進行操作，避免影響到下一張圖的合成
                    composite_img = base_img.copy()
                    # 將差分圖疊加到底圖上
                    composite_img.paste(diff_img, (paste_x, paste_y), diff_img)
                    # 儲存合成後的圖片
                    composite_img.save(output_path)
                except FileNotFoundError:
                    print(f"    ! 警告：找不到差分圖檔案 {diff_image_name}，跳過此圖片。")
                except Exception as e:
                    print(f"    ! 錯誤：處理 {output_filename} 時發生錯誤: {e}")

    except Exception as e:
        print(f"處理檔案 {os.path.basename(csv_path)} 時發生未預期的錯誤: {e}")

# --- 3. 程式主體：尋找並遍歷所有 CSV ---
def main():
    """
    主執行函式，會自動尋找當前資料夾下的所有 .csv 檔案，並逐一進行處理。
    """
    # 尋找所有檔名結尾是 .csv 的檔案
    csv_files = glob.glob('*.csv')
    if not csv_files:
        print("在專案目錄中找不到任何 .csv 檔案，程式結束。")
        return
        
    print(f"找到了 {len(csv_files)} 個 CSV 檔案，準備開始處理...")
    for csv_file in csv_files:
        process_csv_file(csv_file)
    
    print(f"\n{'='*25}")
    print("✅  所有 CSV 檔案處理完畢！")
    print(f"{'='*25}")

# --- 4. 執行程式 ---
# 確保這段程式碼只有在直接執行此 .py 檔案時才會被觸發
if __name__ == "__main__":
    main()