import os
import shutil
from PIL import Image
import itertools

# --- 核心函式 (維持不變) ---

def ensure_dir(dir_path):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

def get_image_info(file_path):
    try:
        with Image.open(file_path) as img:
            size = img.size
            pos = (0, 0)
            if 'comment' in img.info:
                comment_string = img.info['comment']
                parts = comment_string.split(',')
                if len(parts) >= 3 and parts[0] == 'pos':
                    pos = (int(parts[1]), int(parts[2]))
            return size, pos
    except FileNotFoundError:
        print(f"警告：找不到檔案 {file_path}")
        return None, None
    except Exception as e:
        print(f"警告：讀取 '{file_path}' 的資訊時發生錯誤: {e}")
        return None, None

def get_files_safely(dir_name):
    if not os.path.isdir(dir_name):
        return []
    return [os.path.join(dir_name, f) for f in os.listdir(dir_name) if f.endswith('.png')]

def calculate_and_composite(parts_info, output_path):
    if not parts_info: return
    min_x, min_y, max_x, max_y = float('inf'), float('inf'), float('-inf'), float('-inf')
    for _, size, pos in parts_info:
        min_x = min(min_x, pos[0])
        min_y = min(min_y, pos[1])
        max_x = max(max_x, pos[0] + size[0])
        max_y = max(max_y, pos[1] + size[1])
    canvas_width, canvas_height = max_x - min_x, max_y - min_y
    final_image = Image.new('RGBA', (canvas_width, canvas_height), (0, 0, 0, 0))
    for part_path, _, pos in parts_info:
        paste_x, paste_y = pos[0] - min_x, pos[1] - min_y
        try:
            temp_layer = Image.new('RGBA', final_image.size, (0, 0, 0, 0))
            with Image.open(part_path) as part_img:
                temp_layer.paste(part_img.convert("RGBA"), (paste_x, paste_y))
            final_image = Image.alpha_composite(final_image, temp_layer)
        except FileNotFoundError:
            continue
    final_image.save(output_path)
    print(f"  -> 已生成: {output_path}")

# --- ★★★ 全新重構的核心處理函式 ★★★ ---
def process_directory(source_path):
    print(f"\n=================================================")
    print(f"=== 正在處理專案: {source_path}")
    print(f"=================================================\n")

    # 1. 定義所有路徑
    OUTPUT_ROOT = os.path.join(source_path, "output")
    KAO_KUCHI_DIR = os.path.join(OUTPUT_ROOT, "kao_kuchi")
    KAO_KUCHI_HOHO_DIR = os.path.join(OUTPUT_ROOT, "kao_kuchi_hoho")
    KAO_KUCHI_EFFECT_DIR = os.path.join(OUTPUT_ROOT, "kao_kuchi_effect")
    KAO_KUCHI_HOHO_EFFECT_DIR = os.path.join(OUTPUT_ROOT, "kao_kuchi_hoho_effect")
    
    for d in [OUTPUT_ROOT, KAO_KUCHI_DIR, KAO_KUCHI_HOHO_DIR, KAO_KUCHI_EFFECT_DIR, KAO_KUCHI_HOHO_EFFECT_DIR]:
        ensure_dir(d)

    # 獲取所有部件檔案
    fuku_files = get_files_safely(os.path.join(source_path, "fuku"))
    kao_files = get_files_safely(os.path.join(source_path, "kao"))
    kami_files = get_files_safely(os.path.join(source_path, "kami"))
    kuchi_files = get_files_safely(os.path.join(source_path, "kuchi"))
    hoho_files = get_files_safely(os.path.join(source_path, "hoho"))
    effect_files = get_files_safely(os.path.join(source_path, "effect"))

    if not fuku_files or not kao_files:
        print(f"錯誤：在 '{source_path}' 中，'fuku' 或 'kao' 為空或不存在。")
        return

    # 2. 輔助函式：用於生成組合和儲存
    def generate_and_save(base_compositions, optional_parts, target_dir):
        # 接收一個「基礎組合的列表」，為其中每一個組合添加新的「可選部件」
        output_compositions = []
        if optional_parts:
            # 如果有可選部件，進行組合
            for base_comp in base_compositions:
                for part_path in optional_parts:
                    output_compositions.append(base_comp + [part_path])
        else:
            # 如果沒有可選部件，直接傳遞基礎組合
            output_compositions = base_compositions
        
        # 對所有產生的組合進行合成和儲存
        for comp in output_compositions:
            parts_info = []
            output_name_parts = []
            for part_path in comp:
                size, pos = get_image_info(part_path)
                if not size: continue
                parts_info.append((part_path, size, pos))
                output_name_parts.append(os.path.splitext(os.path.basename(part_path))[0])
            
            output_filename = "_".join(output_name_parts) + ".png"
            output_path = os.path.join(target_dir, output_filename)
            calculate_and_composite(parts_info, output_path)
            
        return output_compositions

    # 3. 階段性執行合成
    print("--- 第一階段: 處理 基礎+髮型 (-> output/) ---")
    base_comps = [[f, k] for f in fuku_files for k in kao_files]
    stage1_comps = generate_and_save(base_comps, kami_files, OUTPUT_ROOT)

    print("\n--- 第二階段: 處理 +嘴巴 (-> kao_kuchi/) ---")
    stage2_comps = generate_and_save(stage1_comps, kuchi_files, KAO_KUCHI_DIR)

    print("\n--- 第三階段: 處理 +臉頰 (-> kao_kuchi_hoho/) ---")
    stage3_comps = generate_and_save(stage2_comps, hoho_files, KAO_KUCHI_HOHO_DIR)

    if effect_files:
        print("\n--- 第四階段 (分支A): 為 'kao_kuchi' 添加效果 ---")
        generate_and_save(stage2_comps, effect_files, KAO_KUCHI_EFFECT_DIR)

        print("\n--- 第四階段 (分支B): 為 'kao_kuchi_hoho' 添加效果 ---")
        generate_and_save(stage3_comps, effect_files, KAO_KUCHI_HOHO_EFFECT_DIR)

    print(f"\n--- 專案 {source_path} 處理完畢！ ---")


# --- 啟動函式 (維持不變) ---
def find_and_process_directories(start_path='.'):
    print("開始掃描專案資料夾...")
    found_projects = 0
    for root, dirs, files in os.walk(start_path):
        if "fuku" in dirs and "kao" in dirs:
            if os.path.sep + 'output' + os.path.sep in root + os.path.sep:
                continue
            found_projects += 1
            process_directory(root)
    if found_projects == 0:
        print("未找到任何包含 'fuku' 和 'kao' 的專案資料夾。")
    else:
        print(f"\n--- 所有 {found_projects} 個專案都已處理完畢！ ---")

# --- 主程式入口 ---
if __name__ == '__main__':
    find_and_process_directories()
