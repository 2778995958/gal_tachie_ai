import os
import pandas as pd
from PIL import Image
import glob

# --- 1. 設定區 ---
SOURCE_IMAGES_DIR = 'event'
OUTPUT_DIR = 'output_event'

# --- 2. 處理單一 CSV 檔案的函式 ---
def process_csv_file(csv_path):
    """
    此函式負責處理單一一個 CSV 檔案的圖片合成邏輯。
    """
    print(f"\n{'='*25}")
    print(f"▶️  開始處理檔案: {csv_path}")
    print(f"{'='*25}")

    try:
        # [優化] 使用 utf-8-sig 防止不可見的 BOM 字元干擾欄位名稱
        df = pd.read_csv(csv_path, encoding='utf-8-sig')
        
        # [優化] 清理欄位名稱前後可能多出來的空白
        df.columns = df.columns.str.strip()

        grouped = df.groupby('base')

        for base_name, group_df in grouped:
            base_name = str(base_name)
            
            # [修正 1] 改用底線分割來取得角色代號。例如 'EA01_01L' -> 取 'EA01'
            character_code = base_name.split('_')[0]
            print(f"\n--- 正在處理基於底圖 '{base_name}' 的角色群組: {character_code} ---")

            character_output_dir = os.path.join(OUTPUT_DIR, character_code)
            if not os.path.exists(character_output_dir):
                os.makedirs(character_output_dir)

            base_image_name = base_name + '.png'
            base_image_path = os.path.join(SOURCE_IMAGES_DIR, base_image_name)
            
            try:
                base_img = Image.open(base_image_path).convert("RGBA")
                print(f"  > 已載入底圖: {base_image_name}")

                output_base_path = os.path.join(character_output_dir, base_image_name)
                if os.path.exists(output_base_path):
                    print(f"  [✓] 底圖已存在: {base_image_name}")
                else:
                    base_img.save(output_base_path)
                    print(f"  > 已複製底圖至輸出資料夾")

            except FileNotFoundError:
                print(f"  ! 錯誤：找不到底圖檔案 {base_image_path}，跳過此群組。")
                continue

            for index, row in group_df.iterrows():
                # [優化] 增加 pd.isna 檢查，避免 diff 是空值時發生錯誤
                if str(row['tag']) == base_name or pd.isna(row['diff']):
                    continue

                output_filename = str(row['tag']) + '.png'
                output_path = os.path.join(character_output_dir, output_filename)

                if os.path.exists(output_path):
                    print(f"    [✓] 已存在，跳過: {output_filename}")
                    continue

                print(f"    合成中: {output_filename} ...")
                
                try:
                    diff_image_name = str(row['diff']) + '.png'
                    diff_image_path = os.path.join(SOURCE_IMAGES_DIR, diff_image_name)
                    
                    # [修正 2] 強制將座標轉換為標準整數 int()
                    paste_x, paste_y = int(row['x']), int(row['y'])
                    
                    diff_img = Image.open(diff_image_path).convert("RGBA")
                    composite_img = base_img.copy()
                    
                    # 將差分圖貼到底圖上
                    composite_img.paste(diff_img, (paste_x, paste_y), diff_img)
                    composite_img.save(output_path)
                except FileNotFoundError:
                    print(f"    ! 警告：找不到差分圖檔案 {diff_image_name}，跳過此組合。")
                except Exception as e:
                    print(f"    ! 錯誤：處理 {output_filename} 時發生錯誤: {e}")

    except Exception as e:
        print(f"處理檔案 {csv_path} 時發生未預期的錯誤: {e}")

# --- 3. 程式主體：尋找並遍歷所有 CSV ---
def main():
    csv_files = glob.glob('*.csv')
    if not csv_files:
        print("在專案目錄中找不到任何 .csv 檔案，程式即將結束。")
        return
    print(f"總共找到 {len(csv_files)} 個 CSV 檔案: {', '.join(csv_files)}")
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"已建立輸出資料夾: {OUTPUT_DIR}")
    for file_path in csv_files:
        process_csv_file(file_path)
    print(f"\n--- ✅ 所有 CSV 檔案處理完成！ ---")

if __name__ == "__main__":
    main()