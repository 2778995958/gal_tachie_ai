import os
from PIL import Image

# --- 設定 ---
# 來源資料夾，腳本會從這裡開始掃描
SOURCE_FOLDER = 'm_090'
# 輸出資料夾，所有合成後的圖片會儲存在這裡
OUTPUT_FOLDER = 'output'
# 用來識別「身體」圖片的檔名後綴
BODY_IMAGE_SUFFIX = '100.png'

def compose_images_in_folder(folder_path):
    """
    處理單一資料夾中的圖片合成。
    1. 找到身體圖片。
    2. 找到所有表情圖片。
    3. 將每張表情疊加到身體上，並儲存到輸出目錄。
    """
    print(f"正在處理資料夾：{folder_path}")

    # --- 1. 整理檔案列表，找出身體和表情 ---
    body_image_path = None
    emotion_image_paths = []
    
    # 遍歷資料夾內所有檔案
    for filename in os.listdir(folder_path):
        # 只處理 .png 檔案
        if filename.lower().endswith('.png'):
            full_path = os.path.join(folder_path, filename)
            if filename.lower().endswith(BODY_IMAGE_SUFFIX):
                # 檢查是否已找到身體圖片，防止一個資料夾有多個身體圖
                if body_image_path is None:
                    body_image_path = full_path
                else:
                    print(f"  [警告] 在 {folder_path} 中找到多個身體圖片，將只使用第一個。")
            else:
                emotion_image_paths.append(full_path)

    # --- 2. 檢查是否有必要的圖片 ---
    if not body_image_path:
        print(f"  [跳過] 在 {folder_path} 中找不到身體圖片 (結尾為 {BODY_IMAGE_SUFFIX} 的檔案)。")
        return

    if not emotion_image_paths:
        print(f"  [跳過] 在 {folder_path} 中找不到任何表情圖片。")
        return

    print(f"  找到身體: {os.path.basename(body_image_path)}")
    print(f"  找到 {len(emotion_image_paths)} 個表情。")

    # --- 3. 開始合成圖片 ---
    # 打開身體圖片，並確保是 RGBA 格式以支援透明度
    with Image.open(body_image_path) as body_img:
        body_img = body_img.convert('RGBA')

        # 遍歷所有表情圖片
        for emotion_path in emotion_image_paths:
            try:
                # 打開表情圖片
                with Image.open(emotion_path) as emotion_img:
                    emotion_img = emotion_img.convert('RGBA')

                    # 建立一個身體圖片的複本，以便在其上進行操作
                    composed_img = body_img.copy()

                    # 將表情貼到身體複本上
                    # 第二個參數 (0, 0) 代表貼上的座標
                    # 第三個參數 mask=emotion_img 是為了正確處理表情圖的透明部分
                    composed_img.paste(emotion_img, (0, 0), mask=emotion_img)

                    # --- 4. 準備輸出路徑並儲存 ---
                    # 建立對應的輸出資料夾結構
                    # 例如: m_090\a_yur\a_yur_0a -> output\m_090\a_yur\a_yur_0a
                    relative_path = os.path.relpath(folder_path, '.')
                    output_dir = os.path.join(OUTPUT_FOLDER, relative_path)
                    
                    # 如果輸出資料夾不存在，則建立它
                    os.makedirs(output_dir, exist_ok=True)
                    
                    # 定義輸出檔案的路徑和名稱
                    output_filename = os.path.basename(emotion_path)
                    output_path = os.path.join(output_dir, output_filename)
                    
                    # 儲存合成後的圖片
                    composed_img.save(output_path, 'PNG')
                    print(f"    -> 已合成並儲存至: {output_path}")

            except Exception as e:
                print(f"    [錯誤] 處理 {emotion_path} 時發生錯誤: {e}")

def main():
    """
    主函式，遍歷所有來源資料夾並執行合成。
    """
    print("--- 開始批量合成表情 ---")
    
    # 檢查來源資料夾是否存在
    if not os.path.isdir(SOURCE_FOLDER):
        print(f"[錯誤] 來源資料夾 '{SOURCE_FOLDER}' 不存在！請檢查設定。")
        return

    # 使用 os.walk 遞迴地遍歷所有子資料夾
    for dirpath, _, _ in os.walk(SOURCE_FOLDER):
        # 我們只處理最深層的資料夾，判斷標準是它裡面不再有子資料夾
        # listdir 會列出所有檔案和資料夾，我們篩選出資料夾
        subdirs = [d for d in os.listdir(dirpath) if os.path.isdir(os.path.join(dirpath, d))]
        if not subdirs:
             compose_images_in_folder(dirpath)

    print("--- 所有任務已完成 ---")

if __name__ == '__main__':
    main()