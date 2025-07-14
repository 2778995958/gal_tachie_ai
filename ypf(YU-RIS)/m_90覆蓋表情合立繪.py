import os
from PIL import Image

# --- 設定 ---
# 來源資料夾，腳本會從這裡開始掃描
SOURCE_FOLDER = 'm_066'
# 輸出資料夾，所有合成後的圖片會儲存在這裡
OUTPUT_FOLDER = 'output'

# 【最終正確規則】根據您的最新指正，更新身體圖片的檔名後綴
# 優先尋找 *0100.png，若無，則尋找 *0000.png
BODY_IMAGE_SUFFIXES = ['0000.png', '0100.png']

def compose_images_in_folder(folder_path):
    """
    處理單一資料夾中的圖片合成。
    1. 按照優先級尋找身體圖片 ('0100.png' -> '0000.png')。
    2. 找到所有表情圖片。
    3. 儲存身體圖片和合成圖（如果目標不存在）。
    """
    print(f"正在處理資料夾：{folder_path}")

    # --- 1. 按照優先級尋找身體圖片 ---
    body_image_path = None
    all_png_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.png')]

    for suffix in BODY_IMAGE_SUFFIXES:
        for filename in all_png_files:
            if filename.lower().endswith(suffix):
                body_image_path = os.path.join(folder_path, filename)
                print(f"  找到身體 (使用規則 *{suffix}): {filename}")
                break
        if body_image_path:
            break

    # --- 2. 檢查與分類 ---
    if not body_image_path:
        print(f"  [跳過] 在 {folder_path} 中找不到任何身體圖片 (規則: {BODY_IMAGE_SUFFIXES})。")
        return

    body_filename = os.path.basename(body_image_path)
    emotion_image_paths = [os.path.join(folder_path, f) for f in all_png_files if f != body_filename]
    
    if not emotion_image_paths:
        print(f"  [提示] 在 {folder_path} 中找不到任何表情圖片，但仍會處理身體圖片。")

    # --- 3. 準備輸出路徑 ---
    relative_path = os.path.relpath(folder_path, '.')
    output_dir = os.path.join(OUTPUT_FOLDER, relative_path)
    os.makedirs(output_dir, exist_ok=True)

    # --- 4. 處理並儲存身體圖片 ---
    with Image.open(body_image_path) as body_img:
        body_img = body_img.convert('RGBA')

        output_path_for_body = os.path.join(output_dir, body_filename)

        if os.path.exists(output_path_for_body):
            print(f"    [跳過] 身體檔案已存在: {output_path_for_body}")
        else:
            body_img.save(output_path_for_body, 'PNG')
            print(f"    -> 已儲存身體: {output_path_for_body}")

        # --- 5. 遍歷表情並合成 ---
        for emotion_path in emotion_image_paths:
            try:
                output_filename = os.path.basename(emotion_path)
                output_path = os.path.join(output_dir, output_filename)

                if os.path.exists(output_path):
                    print(f"    [跳過] 合成檔案已存在: {output_path}")
                    continue

                with Image.open(emotion_path) as emotion_img:
                    emotion_img = emotion_img.convert('RGBA')
                    
                    composed_img = body_img.copy()
                    composed_img.paste(emotion_img, (0, 0), mask=emotion_img)
                    composed_img.save(output_path, 'PNG')
                    print(f"    -> 已合成並儲存至: {output_path}")

            except Exception as e:
                print(f"    [錯誤] 處理 {emotion_path} 時發生錯誤: {e}")

def main():
    """
    主函式，遍歷所有來源資料夾並執行合成。
    """
    print("--- 開始批量合成表情 ---")
    
    if not os.path.isdir(SOURCE_FOLDER):
        print(f"[錯誤] 來源資料夾 '{SOURCE_FOLDER}' 不存在！請檢查設定。")
        return

    for dirpath, subdirs, _ in os.walk(SOURCE_FOLDER):
        if not subdirs:
            compose_images_in_folder(dirpath)

    print("--- 所有任務已完成 ---")

if __name__ == '__main__':
    main()
