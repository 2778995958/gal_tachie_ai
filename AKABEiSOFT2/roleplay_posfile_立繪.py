import os
import glob
import re
from PIL import Image

# --- 1. 設定區 ---
# 圖片和 .pos 檔案的來源資料夾
SOURCE_IMAGES_DIR = 'images'
# 最終合成圖片的輸出資料夾
OUTPUT_DIR = 'output'


# --- 2. 處理單一 .pos 檔案的函式 ---
def process_pos_file(pos_path):
    """
    此函式負責處理單一一個 .pos 檔案的圖片合成邏輯。
    """
    print(f"\n--- 正在處理檔案: {os.path.basename(pos_path)} ---")

    # 根據 .pos 檔名，決定最終輸出的檔名
    output_filename = os.path.basename(pos_path).replace('.pos', '.png')
    output_filepath = os.path.join(OUTPUT_DIR, output_filename)

    # 【檢查功能】如果最終的合成圖已存在，則直接跳過
    if os.path.exists(output_filepath):
        print(f"  [✓] 已存在，跳過: {output_filename}")
        return # 結束這個函式的執行

    # --- 讀取並解析 .pos 檔案 ---
    try:
        with open(pos_path, 'r', encoding='utf-16') as f:
            content = f.read()

        # 使用正規表示式來安全地抓取 "檔名"、數字1、數字2
        # "([^"]+)"   -> 抓取雙引號中的檔名
        # \s*,\s* -> 匹配逗號以及前後的空白
        # (\d+)       -> 抓取一個或多個數字
        match = re.search(r'"([^"]+)"\s*,\s*(\d+)\s*,\s*(\d+)', content)

        if not match:
            print(f"  ! 錯誤：無法解析檔案格式 {pos_path}")
            return

        # 從解析結果中取得資訊
        base_name = match.group(1) # st01aaa00
        paste_y = int(match.group(2)) # 658
        paste_x = int(match.group(3)) # 603
        
        base_image_filename = base_name + '.png' # st01aaa00.png
        # 要被貼上的差分圖，就是輸出檔名對應的圖
        diff_image_filename = output_filename 

        print(f"  > 解析成功: 底圖='{base_image_filename}', 差分圖='{diff_image_filename}', 座標=(x:{paste_x}, y:{paste_y})")

    except FileNotFoundError:
        print(f"  ! 錯誤：找不到 .pos 檔案 {pos_path}")
        return
    except Exception as e:
        print(f"  ! 錯誤：讀取或解析 .pos 檔案時發生問題: {e}")
        return

    # --- 執行圖片合成 ---
    try:
        # 定義所有圖片的完整路徑
        base_image_path = os.path.join(SOURCE_IMAGES_DIR, base_image_filename)
        diff_image_path = os.path.join(SOURCE_IMAGES_DIR, diff_image_filename)
        output_base_path = os.path.join(OUTPUT_DIR, base_image_filename)

        # 1. 處理底圖：檢查底圖是否已在輸出資料夾，若無則複製過去
        if os.path.exists(output_base_path):
            print(f"  [✓] 底圖已存在於輸出資料夾: {base_image_filename}")
        else:
            # 嘗試打開來源底圖並儲存到輸出區
            base_img_source = Image.open(base_image_path)
            base_img_source.save(output_base_path)
            print(f"  > 已複製底圖至: {output_base_path}")

        # 2. 執行合成
        print(f"  合成中: {output_filename} ...")
        base_img = Image.open(base_image_path).convert("RGBA")
        diff_img = Image.open(diff_image_path).convert("RGBA")

        # 建立一個底圖的複本來進行貼圖，避免污染原始底圖物件
        composite_img = base_img.copy()
        
        # 執行貼上操作，注意 paste 函式的座標順序是 (x, y)
        composite_img.paste(diff_img, (paste_x, paste_y), diff_img)
        
        # 儲存最終的合成圖片
        composite_img.save(output_filepath)
        print(f"  ✨ 合成完畢，已儲存至: {output_filepath}")

    except FileNotFoundError as e:
        print(f"  ! 錯誤：找不到圖片檔案，請檢查 '{e.filename}' 是否存在於 '{SOURCE_IMAGES_DIR}' 資料夾中。")
    except Exception as e:
        print(f"  ! 錯誤：在圖片合成過程中發生問題: {e}")


# --- 3. 程式主體：尋找並遍歷所有 .pos ---
def main():
    """
    主執行函式，負責尋找所有 .pos 檔案，並逐一處理。
    """
    # 建立輸出資料夾 (如果不存在)
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"已建立輸出資料夾: {OUTPUT_DIR}")

    # 尋找 'images' 資料夾中所有的 .pos 檔案
    search_path = os.path.join(SOURCE_IMAGES_DIR, '*.pos')
    pos_files = glob.glob(search_path)

    if not pos_files:
        print(f"在 '{SOURCE_IMAGES_DIR}' 資料夾中找不到任何 .pos 檔案，程式即將結束。")
        return

    print(f"\n總共找到 {len(pos_files)} 個 .pos 檔案。開始處理...")
    
    for file_path in pos_files:
        process_pos_file(file_path)
        
    print(f"\n--- ✅ 所有 .pos 檔案處理完成！ ---")

# --- 程式執行的進入點 ---
if __name__ == "__main__":
    main()