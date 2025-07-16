import os
import shutil
from PIL import Image
import itertools

# --- 核心函式 (get_image_info 已修正) ---

def ensure_dir(dir_path):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

# ★★★ 已修正：對調 pos.txt 與 PNG 內部的讀取優先級 ★★★
def get_image_info(file_path, pos_lookup_map):
    """
    獲取圖片的尺寸和位置座標，遵循三層優先級：
    1. PNG 檔案內部的 'comment'
    2. pos.txt 的外部定義
    3. 預設 (0, 0)
    """
    base_filename = os.path.basename(file_path)
    size = None
    
    # 先獲取圖片尺寸
    try:
        with Image.open(file_path) as img:
            size = img.size
    except FileNotFoundError:
        print(f"警告：找不到檔案 {file_path}")
        return None, None
    except Exception as e:
        print(f"警告：讀取圖片 '{file_path}' 尺寸時發生錯誤: {e}")
        return None, None

    # 優先級 1: 檢查 PNG 內部註解
    try:
        with Image.open(file_path) as img:
            if 'comment' in img.info:
                comment_string = img.info['comment']
                parts = comment_string.split(',')
                if len(parts) >= 3 and parts[0] == 'pos':
                    pos = (int(parts[1]), int(parts[2]))
                    print(f"      - 座標來源 [PNG]: {base_filename} -> {pos}")
                    return size, pos # 找到即返回，不再執行後續檢查
    except Exception:
        pass
    
    # 優先級 2: 檢查從 pos.txt 載入的 lookup map
    if base_filename in pos_lookup_map:
        pos = pos_lookup_map[base_filename]
        print(f"      - 座標來源 [pos.txt]: {base_filename} -> {pos}")
        return size, pos

    # 優先級 3: 使用預設值
    pos = (0, 0)
    print(f"      - 座標來源 [預設]: {base_filename} -> {pos}")
    return size, pos

def get_files_safely(dir_name):
    if not os.path.isdir(dir_name):
        return []
    return [os.path.join(dir_name, f) for f in os.listdir(dir_name) if f.endswith('.png')]

# --- 核心合成函式 (維持不變) ---
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

# --- 核心處理函式 (維持不變) ---
def process_directory(source_path):
    print(f"\n=================================================")
    print(f"=== 正在處理專案: {source_path}")
    print(f"=================================================\n")

    pos_lookup = {}
    pos_txt_path = os.path.join(source_path, 'pos.txt')
    if os.path.exists(pos_txt_path):
        print(f"[資訊] 正在讀取座標檔: {pos_txt_path}")
        with open(pos_txt_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'): continue
                parts = line.split(',')
                if len(parts) == 3:
                    filename = parts[0].strip()
                    try:
                        x = int(parts[1].strip())
                        y = int(parts[2].strip())
                        pos_lookup[filename] = (x, y)
                    except ValueError:
                        print(f"[警告] {pos_txt_path} 中有無法解析的行: {line}")
        print(f"[資訊] 座標檔讀取完畢，載入 {len(pos_lookup)} 筆設定。")
    
    OUTPUT_ROOT = os.path.join(source_path, "output")
    all_dirs = [os.path.join(OUTPUT_ROOT, d) for d in ["", "kao_kuchi", "kao_kuchi_hoho", "kao_kuchi_effect", "kao_kuchi_hoho_effect"]]
    for d in all_dirs: ensure_dir(d)

    fuku_files = get_files_safely(os.path.join(source_path, "fuku"))
    kao_files = get_files_safely(os.path.join(source_path, "kao"))
    kami_files = get_files_safely(os.path.join(source_path, "kami"))
    kuchi_files = get_files_safely(os.path.join(source_path, "kuchi"))
    hoho_files = get_files_safely(os.path.join(source_path, "hoho"))
    effect_files = get_files_safely(os.path.join(source_path, "effect"))

    if not fuku_files or not kao_files:
        print(f"錯誤：在 '{source_path}' 中，'fuku' 或 'kao' 為空或不存在。")
        return

    def generate_and_save(base_compositions, optional_parts, target_dir):
        output_compositions = base_compositions if not optional_parts else [base + [part] for base in base_compositions for part in optional_parts]
        for comp in output_compositions:
            parts_info = []
            output_name_parts = []
            print(f"\n組合: {[os.path.basename(p) for p in comp]}")
            for part_path in comp:
                size, pos = get_image_info(part_path, pos_lookup)
                if not size: continue
                parts_info.append((part_path, size, pos))
                output_name_parts.append(os.path.splitext(os.path.basename(part_path))[0])
            
            output_filename = "_".join(output_name_parts) + ".png"
            output_path = os.path.join(target_dir, output_filename)
            calculate_and_composite(parts_info, output_path)
        return output_compositions

    print("\n--- 第一階段: 處理 基礎+髮型 (-> output/) ---")
    base_comps = [[f, k] for f in fuku_files for k in kao_files]
    stage1_comps = generate_and_save(base_comps, kami_files, os.path.join(OUTPUT_ROOT, ""))

    print("\n--- 第二階段: 處理 +嘴巴 (-> kao_kuchi/) ---")
    stage2_comps = generate_and_save(stage1_comps, kuchi_files, os.path.join(OUTPUT_ROOT, "kao_kuchi"))

    print("\n--- 第三階段: 處理 +臉頰 (-> kao_kuchi_hoho/) ---")
    stage3_comps = generate_and_save(stage2_comps, hoho_files, os.path.join(OUTPUT_ROOT, "kao_kuchi_hoho"))

    if effect_files:
        print("\n--- 第四階段 (分支A): 為 'kao_kuchi' 添加效果 ---")
        generate_and_save(stage2_comps, effect_files, os.path.join(OUTPUT_ROOT, "kao_kuchi_effect"))

        print("\n--- 第四階段 (分支B): 為 'kao_kuchi_hoho' 添加效果 ---")
        generate_and_save(stage3_comps, effect_files, os.path.join(OUTPUT_ROOT, "kao_kuchi_hoho_effect"))

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
