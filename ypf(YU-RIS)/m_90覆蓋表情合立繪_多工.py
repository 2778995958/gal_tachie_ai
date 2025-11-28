import os
import time
from PIL import Image
from concurrent.futures import ProcessPoolExecutor
from tqdm import tqdm  # 需安裝: pip install tqdm

# --- 設定 ---
SOURCE_FOLDER = 'm_066'
OUTPUT_FOLDER = 'output'
# 優先尋找 *0100.png，若無，則尋找 *0000.png
BODY_IMAGE_SUFFIXES = ['0000.png', '0100.png']

def process_single_task(task_info):
    """
    這是給每個 CPU 核心執行的單一任務函式。
    task_info 包含: (body_path, emotion_path, output_path, is_body_only)
    """
    body_path, emotion_path, output_path, is_body_only = task_info

    try:
        if os.path.exists(output_path):
            return  # 檔案已存在，跳過

        # 處理 1: 僅儲存身體圖片 (當作單純複製)
        if is_body_only:
            with Image.open(body_path) as body_img:
                body_img = body_img.convert('RGBA')
                body_img.save(output_path, 'PNG')
            return

        # 處理 2: 合成表情
        with Image.open(body_path) as body_img:
            body_img = body_img.convert('RGBA')
            
            with Image.open(emotion_path) as emotion_img:
                emotion_img = emotion_img.convert('RGBA')
                
                # 合成
                composed_img = body_img.copy()
                composed_img.paste(emotion_img, (0, 0), mask=emotion_img)
                composed_img.save(output_path, 'PNG')
                
    except Exception as e:
        print(f"\n[錯誤] 處理 {output_path} 時發生錯誤: {e}")

def scan_folders_and_create_tasks():
    """
    掃描資料夾，但不立刻處理，而是建立「任務清單」。
    """
    tasks = []
    
    if not os.path.isdir(SOURCE_FOLDER):
        print(f"[錯誤] 來源資料夾 '{SOURCE_FOLDER}' 不存在！")
        return []

    print("正在掃描資料夾結構並建立任務清單...")

    for dirpath, subdirs, _ in os.walk(SOURCE_FOLDER):
        if not subdirs: # 只處理最底層資料夾
            # --- 尋找 PNG 檔案 ---
            all_png_files = [f for f in os.listdir(dirpath) if f.lower().endswith('.png')]
            if not all_png_files:
                continue

            # --- 尋找身體圖片 (邏輯保持不變) ---
            body_image_path = None
            body_filename = None

            for suffix in BODY_IMAGE_SUFFIXES:
                for filename in all_png_files:
                    if filename.lower().endswith(suffix):
                        body_image_path = os.path.join(dirpath, filename)
                        body_filename = filename
                        break
                if body_image_path:
                    break
            
            if not body_image_path:
                continue # 找不到身體就跳過該資料夾

            # --- 準備輸出資料夾 ---
            relative_path = os.path.relpath(dirpath, '.')
            output_dir = os.path.join(OUTPUT_FOLDER, relative_path)
            os.makedirs(output_dir, exist_ok=True)

            # --- 建立任務 1: 儲存身體圖片本身 ---
            output_path_body = os.path.join(output_dir, body_filename)
            # 參數格式: (body_path, emotion_path, output_path, is_body_only)
            tasks.append((body_image_path, None, output_path_body, True))

            # --- 建立任務 2: 每個表情的合成任務 ---
            emotion_files = [f for f in all_png_files if f != body_filename]
            for emotion_file in emotion_files:
                emotion_path = os.path.join(dirpath, emotion_file)
                output_path_emotion = os.path.join(output_dir, emotion_file)
                
                tasks.append((body_image_path, emotion_path, output_path_emotion, False))

    return tasks

def main():
    print("--- 開始多工批量合成表情 ---")
    start_time = time.time()

    # 1. 先收集所有要做的工作
    all_tasks = scan_folders_and_create_tasks()
    total_tasks = len(all_tasks)
    
    if total_tasks == 0:
        print("沒有發現需要處理的圖片。")
        return

    print(f"總共發現 {total_tasks} 個處理任務，準備開始多核心運算...")

    # 2. 使用 ProcessPoolExecutor 進行平行處理
    # max_workers 預設為 None，會自動使用電腦所有可用的 CPU 核心
    with ProcessPoolExecutor() as executor:
        # 使用 tqdm 顯示進度條，將任務分發給 executor
        list(tqdm(executor.map(process_single_task, all_tasks), total=total_tasks, unit="img"))

    end_time = time.time()
    duration = end_time - start_time
    print(f"\n--- 所有任務已完成 ---")
    print(f"耗時: {duration:.2f} 秒")

if __name__ == '__main__':
    main()