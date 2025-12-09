import os
from PIL import Image

# ================= 設定區域 =================
# 圖片來源資料夾
SOURCE_DIR = "images"

# 輸出資料夾
OUTPUT_DIR = "output"

# 清單檔案名稱
LIST_FILE = "cglist.txt"
# ===========================================

def find_image_path(filename, source_dir):
    """
    尋找檔案，自動嘗試 jpg, png, bmp 副檔名
    並移除檔名中的 '*' 符號以進行搜尋
    """
    # 移除 '*' 符號 (搜尋檔案時不需要 *)
    clean_name = filename.replace('*', '').strip()
    
    extensions = ['.png', '.jpg', '.jpeg', '.bmp', '.PNG', '.JPG', '.BMP']
    for ext in extensions:
        full_path = os.path.join(source_dir, clean_name + ext)
        if os.path.exists(full_path):
            return full_path
    return None

def process_images():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    if not os.path.exists(LIST_FILE):
        print(f"[錯誤] 找不到清單檔案: {LIST_FILE}")
        return

    print(f"正在讀取清單: {LIST_FILE}")
    
    try:
        with open(LIST_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        with open(LIST_FILE, 'r', encoding='cp932') as f:
            lines = f.readlines()

    for line in lines:
        line = line.strip()
        
        # 跳過空行、註解(#)和分類(:)
        if not line or line.startswith('#') or line.startswith(':'):
            continue

        parts = line.split(',')
        
        folder_name = parts[0].strip() # 取得系列名稱 (如 sevH01)
        image_tasks = parts[1:]
        
        target_folder = os.path.join(OUTPUT_DIR, folder_name)
        if not os.path.exists(target_folder):
            os.makedirs(target_folder)
            
        print(f"處理系列: {folder_name}")

        counter = 1

        for task in image_tasks:
            if not task:
                continue

            try:
                # 處理特殊符號：將 ? 視為 |，並準備用於檔名的字串
                task_process = task.replace('?', '|')
                
                # === 關鍵修改：檔名格式 ===
                # 移除 | 和 * 用於檔名顯示
                safe_task_name = task_process.replace('|', '_').replace('*', '')
                
                # 格式：資料夾名_編號_處理後的任務名.png
                # 例如：sevH17_001_bg99_01_evH17b.png
                save_filename = f"{folder_name}_{counter:03d}_{safe_task_name}.png"
                save_path = os.path.join(target_folder, save_filename)
                # ========================

                if '|' in task_process:
                    # === 合併模式 ===
                    layers = task_process.split('|')
                    base_name = layers[0]
                    
                    base_path = find_image_path(base_name, SOURCE_DIR)
                    if not base_path:
                        print(f"  [跳過] 找不到底圖: {base_name}")
                        continue
                    
                    canvas = Image.open(base_path).convert("RGBA")

                    for layer_name in layers[1:]:
                        layer_path = find_image_path(layer_name, SOURCE_DIR)
                        if layer_path:
                            overlay = Image.open(layer_path).convert("RGBA")
                            if overlay.size != canvas.size:
                                overlay = overlay.resize(canvas.size, Image.Resampling.LANCZOS)
                            canvas = Image.alpha_composite(canvas, overlay)
                        else:
                            print(f"  [警告] 找不到疊加圖: {layer_name}")

                    canvas.save(save_path)
                    print(f"  [{counter:03d}] 已產生: {save_filename}")

                else:
                    # === 單張模式 ===
                    img_path = find_image_path(task_process, SOURCE_DIR)
                    if img_path:
                        img = Image.open(img_path).convert("RGBA")
                        img.save(save_path)
                        print(f"  [{counter:03d}] 已產生: {save_filename}")
                    else:
                        print(f"  [錯誤] 找不到檔案: {task_process}")

                counter += 1

            except Exception as e:
                print(f"  處理 {task} 時發生錯誤: {e}")

    print("\n所有作業完成！")

if __name__ == "__main__":
    process_images()
