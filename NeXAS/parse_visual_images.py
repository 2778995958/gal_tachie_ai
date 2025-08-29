import os
import pandas as pd
from PIL import Image
import glob

# --- 1. 設定區 ---
# 假設您的原始圖片都放在這個資料夾
SOURCE_IMAGES_DIR = 'images'
# 合成後的圖片會儲存到這個資料夾
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
        # 根據新的 'base_filename' 欄位進行分組
        grouped = df.groupby('base_filename')

        for base_name, group_df in grouped:
            # 假設角色代碼是檔名的前5個字元，這個邏輯保留
            character_code = base_name[:5]
            print(f"\n--- 正在處理基於底圖 '{base_name}' 的角色群組: {character_code} ---")

            # 建立每個角色的專屬輸出資料夾
            character_output_dir = os.path.join(OUTPUT_DIR, character_code)
            if not os.path.exists(character_output_dir):
                os.makedirs(character_output_dir)

            base_image_path = os.path.join(SOURCE_IMAGES_DIR, base_name)
            
            try:
                base_img = Image.open(base_image_path).convert("RGBA")
                print(f"  > 已載入底圖: {base_name}")

                # [保留功能] 檢查底圖是否已存在於輸出資料夾，若否，則複製一份過去
                output_base_path = os.path.join(character_output_dir, base_name)
                if not os.path.exists(output_base_path):
                    base_img.save(output_base_path)
                    print(f"  > 已複製底圖至輸出資料夾")
                else:
                    print(f"  [✓] 底圖已存在: {base_name}")

            except FileNotFoundError:
                print(f"  ! 錯誤：找不到底圖檔案 {base_image_path}，跳過此群組。")
                continue # 找不到底圖，直接跳到下一個群組

            # 遍歷這個群組中的每一行，進行合成
            for index, row in group_df.iterrows():
                # 檢查 'delta_filename' 是否為空 (Pandas 會讀取為 NaN)
                # 如果是空的，代表這行只是底圖宣告，直接跳過合成步驟
                if pd.isna(row['delta_filename']):
                    continue

                # 使用 'delta_filename' 作為輸出檔名
                output_filename = row['delta_filename']
                output_path = os.path.join(character_output_dir, output_filename)

                # [保留功能] 在合成前，檢查輸出檔案是否已存在，若存在則跳過
                if os.path.exists(output_path):
                    print(f"    [✓] 已存在，跳過: {output_filename}")
                    continue

                # 如果程式能執行到這裡，代表檔案不存在，需要合成
                print(f"    合成中: {output_filename} ...")
                
                try:
                    # 取得要貼上的圖片路徑和座標
                    delta_image_name = row['delta_filename']
                    delta_image_path = os.path.join(SOURCE_IMAGES_DIR, delta_image_name)
                    paste_x, paste_y = row['offset_x'], row['offset_y']
                    
                    # 讀取要貼上的圖片
                    delta_img = Image.open(delta_image_path).convert("RGBA")
                    
                    # 複製一份底圖來進行操作，避免影響到原始底圖
                    composite_img = base_img.copy()

                    # 進行透明貼圖
                    # 第三個參數傳入 delta_img 本身，PIL 會使用它的 Alpha 通道作為遮罩
                    composite_img.paste(delta_img, (paste_x, paste_y), delta_img)
                    
                    # 儲存合成後的圖片
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
    # 這裡我們直接指定處理 visual.csv
    csv_files = ['visual.csv']
    if not os.path.exists(csv_files[0]):
        print(f"在專案目錄中找不到 {csv_files[0]} 檔案，程式即將結束。")
        return

    print(f"總共找到 {len(csv_files)} 個 CSV 檔案: {', '.join(csv_files)}")
    
    # 檢查並建立輸出主資料夾
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"已建立輸出資料夾: {OUTPUT_DIR}")
        
    for file_path in csv_files:
        process_csv_file(file_path)
        
    print(f"\n--- ✅ 所有 CSV 檔案處理完成！ ---")

# --- 程式執行的進入點 ---
if __name__ == "__main__":
    main()