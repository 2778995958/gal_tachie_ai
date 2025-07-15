import os
import shutil
from PIL import Image
import itertools
import re

# --- 輔助函式 ---

def parse_pos_file(filepath):
    """
    (再次加固) 無論 fgpos 在檔案何處，都能找到並解析它。
    """
    if not os.path.exists(filepath):
        print("資訊: 未在腳本目錄下找到 pos.txt。")
        return None
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # 1. 在整個檔案內容中，先定位到 fgpos={...} 的區塊
        fgpos_marker = 'fgpos={'
        try:
            fgpos_start_index = content.find(fgpos_marker)
            if fgpos_start_index == -1:
                print(f"警告: 在 pos.txt 中未找到 '{fgpos_marker}' 區塊。")
                return None
        except ValueError:
            print(f"警告: 在 pos.txt 中未找到 '{fgpos_marker}' 區塊。")
            return None

        # 2. 從 fgpos={ 的開頭，手動尋找與之匹配的結束括號 '}'
        brace_level = 1
        search_start_pos = fgpos_start_index + len(fgpos_marker)
        fgpos_end_index = -1
        for i in range(search_start_pos, len(content)):
            char = content[i]
            if char == '{':
                brace_level += 1
            elif char == '}':
                brace_level -= 1
            
            if brace_level == 0:
                fgpos_end_index = i
                break
        
        if fgpos_end_index == -1:
            print("警告: pos.txt 中的 'fgpos' 區塊結構不完整（找不到結束的 '}'）。")
            return None

        # 3. 只取出 fgpos 區塊內部的內容進行解析
        fgpos_content = content[search_start_pos:fgpos_end_index]

        # 4. 使用之前驗證過的、強大的解析器來解析 fgpos_content
        pos_data = {}
        cursor = 0
        block_start_regex = re.compile(r'([\w\d]+)\s*=\s*\{')

        while cursor < len(fgpos_content):
            match = block_start_regex.search(fgpos_content, cursor)
            if not match:
                break

            block_name = match.group(1)
            content_start_pos = match.end()
            
            brace_level_inner = 1
            content_end_pos_inner = -1
            for i in range(content_start_pos, len(fgpos_content)):
                char = fgpos_content[i]
                if char == '{':
                    brace_level_inner += 1
                elif char == '}':
                    brace_level_inner -= 1
                
                if brace_level_inner == 0:
                    content_end_pos_inner = i
                    break
            
            if content_end_pos_inner == -1:
                break 

            block_content = fgpos_content[content_start_pos:content_end_pos_inner].strip()
            
            if re.match(r'^\s*x\s*=', block_content):
                coord_match = re.search(r'x\s*=\s*(\d+)\s*,\s*y\s*=\s*(\d+)', block_content)
                if coord_match:
                    x, y = coord_match.groups()
                    pos_data[block_name] = {'x': int(x), 'y': int(y)}
            else:
                pos_data[block_name] = {}
                inner_items = re.finditer(r'([\w\d]+)\s*=\s*\{x\s*=\s*(\d+)\s*,\s*y\s*=\s*(\d+)\}', block_content)
                for item in inner_items:
                    item_name, x, y = item.groups()
                    pos_data[block_name][item_name] = {'x': int(x), 'y': int(y)}

            cursor = content_end_pos_inner + 1
        
        print("成功讀取並解析 pos.txt 中的 fgpos 區塊。")
        return pos_data
    except Exception as e:
        print(f"錯誤: 解析 pos.txt 時發生問題: {e}")
        return None


def get_image_position_from_png(file_path):
    """
    從 PNG 檔案的 tEXt 中繼資料區塊中讀取位置座標。
    """
    try:
        with Image.open(file_path) as img:
            if 'comment' in img.info:
                comment_string = img.info['comment']
                parts = comment_string.split(',')
                if len(parts) >= 3 and parts[0] == 'pos':
                    return int(parts[1]), int(parts[2])
    except Exception:
        pass
    return None, None

def get_coordinates(file_path, pos_map):
    """
    在給定的座標表 (pos_map) 中查找座標。
    """
    coords = get_image_position_from_png(file_path)
    if coords[0] is not None:
        return coords

    if pos_map:
        filename_key = os.path.splitext(os.path.basename(file_path))[0]
        if filename_key in pos_map:
            return (pos_map[filename_key]['x'], pos_map[filename_key]['y'])

    return None, None

# --- 核心函式 ---

def ensure_dir(dir_path):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

def composite_images(base, part_img_path, fuku_coords, pos_map):
    """
    合成圖片。
    """
    if fuku_coords[0] is None: return None
    part_coords = get_coordinates(part_img_path, pos_map)
    part_x, part_y = (part_coords[0] or 0), (part_coords[1] or 0)
    dx = part_x - fuku_coords[0]
    dy = part_y - fuku_coords[1]
    print(f"         └ 貼上 {os.path.basename(part_img_path)} 到相對位置 ({dx}, {dy})")
    try:
        if isinstance(base, str):
            base_img = Image.open(base).convert("RGBA")
        elif isinstance(base, Image.Image):
            base_img = base
        else:
            return None
        with Image.open(part_img_path).convert("RGBA") as part_img:
            temp_layer = Image.new("RGBA", base_img.size)
            temp_layer.paste(part_img, (dx, dy))
            return Image.alpha_composite(base_img, temp_layer)
    except Exception as e:
        print(f"合成過程中發生錯誤: {e}")
        return None

def get_files_safely(dir_name):
    if not os.path.isdir(dir_name):
        return []
    return [f for f in os.listdir(dir_name) if f.endswith('.png')]


# --- 核心處理函式 ---

def process_directory(source_path, pos_data):
    """
    針對指定的來源路徑執行所有圖片合成步驟。
    """
    print(f"\n=================================================")
    print(f"=== 正在處理專案: {source_path}")
    print(f"=================================================\n")
    
    FUKU_DIR = os.path.join(source_path, "fuku")
    
    # 步驟一：鎖定座標容器 (檔名推導邏輯)
    current_pos_map = None
    fuku_files = get_files_safely(FUKU_DIR)
    if pos_data and fuku_files:
        for f_name in sorted(fuku_files): 
            f_basename = os.path.splitext(f_name)[0]
            
            match = re.match(r'(.+?)(\d+)$', f_basename)
            if not match:
                continue
                
            derived_key = match.group(1)
            
            if derived_key in pos_data and isinstance(pos_data[derived_key], dict) and 'x' not in pos_data[derived_key]:
                current_pos_map = pos_data[derived_key]
                print(f"資訊: 已根據檔名 '{f_name}' 推導並鎖定座標容器 '{derived_key}'。")
                break 
    
    if not current_pos_map:
        print(f"警告: 未能從 '{FUKU_DIR}' 的任何檔名中推導出有效的座標容器。")

    # 後續路徑設定
    KAO_DIR = os.path.join(source_path, "kao")
    KAMI_DIR = os.path.join(source_path, "kami")
    KUCHI_DIR = os.path.join(source_path, "kuchi")
    HOHO_DIR = os.path.join(source_path, "hoho")
    EFFECT_DIR = os.path.join(source_path, "effect")
    OUTPUT_ROOT = os.path.join(source_path, "output")
    TEMP_DIR = os.path.join(OUTPUT_ROOT, "temp")
    FINAL_BASE_DIR = OUTPUT_ROOT
    KAO_KUCHI_DIR = os.path.join(OUTPUT_ROOT, "kao_kuchi")
    KAO_KUCHI_EFFECT_DIR = os.path.join(OUTPUT_ROOT, "kao_kuchi_effect")
    KAO_KUCHI_HOHO_DIR = os.path.join(OUTPUT_ROOT, "kao_kuchi_hoho")
    KAO_KUCHI_HOHO_EFFECT_DIR = os.path.join(OUTPUT_ROOT, "kao_kuchi_hoho_effect")
    
    MAX_EFFECT_LAYERS = 3
    for d in [OUTPUT_ROOT, TEMP_DIR, FINAL_BASE_DIR, KAO_KUCHI_DIR]: ensure_dir(d)
    
    kao_files = get_files_safely(KAO_DIR)
    if not fuku_files or not kao_files:
        print(f"錯誤：在 '{source_path}' 中，'fuku' 或 'kao' 為空或不存在。")
        return

    kami_files = get_files_safely(KAMI_DIR)
    kuchi_files = get_files_safely(KUCHI_DIR)
    hoho_files = get_files_safely(HOHO_DIR)
    effect_files = get_files_safely(EFFECT_DIR)
    
    # 步驟二：統一查詢
    for fuku_file in fuku_files:
        fuku_base_name = os.path.splitext(fuku_file)[0]
        fuku_path = os.path.join(FUKU_DIR, fuku_file)
        
        fuku_coords = get_coordinates(fuku_path, current_pos_map)
        if fuku_coords[0] is None: fuku_coords = (0, 0)
            
        print(f"\n--- 正在處理基礎: {fuku_file} (基準座標: {fuku_coords}) ---")

        # ... (以下合成步驟的程式碼不變)
        print("  第一步: fuku + kao -> temp");
        for kao_file in kao_files:
            composed = composite_images(fuku_path, os.path.join(KAO_DIR, kao_file), fuku_coords, current_pos_map)
            if composed: composed.save(os.path.join(TEMP_DIR, f"{fuku_base_name}_{os.path.splitext(kao_file)[0]}.png"))
        
        print("  第二步: temp + kami -> output/")
        if kami_files:
            for temp_file in [f for f in os.listdir(TEMP_DIR) if f.startswith(fuku_base_name)]:
                for kami_file in kami_files:
                    composed = composite_images(os.path.join(TEMP_DIR, temp_file), os.path.join(KAMI_DIR, kami_file), fuku_coords, current_pos_map)
                    if composed: composed.save(os.path.join(FINAL_BASE_DIR, f"{os.path.splitext(temp_file)[0]}_{os.path.splitext(kami_file)[0]}.png"))
        else:
            print("  資訊: 'kami' 為空，已跳過。")
            for temp_file in [f for f in os.listdir(TEMP_DIR) if f.startswith(fuku_base_name)]:
                shutil.copy(os.path.join(TEMP_DIR, temp_file), os.path.join(FINAL_BASE_DIR, temp_file))

        print(f"  第三步: output/ + kuchi -> kao_kuchi")
        for base_file in [f for f in os.listdir(FINAL_BASE_DIR) if f.startswith(fuku_base_name)]:
            base_path = os.path.join(FINAL_BASE_DIR, base_file)
            if kuchi_files:
                for kuchi_file in kuchi_files:
                    composed = composite_images(base_path, os.path.join(KUCHI_DIR, kuchi_file), fuku_coords, current_pos_map)
                    if composed: composed.save(os.path.join(KAO_KUCHI_DIR, f"{os.path.splitext(base_file)[0]}_{os.path.splitext(kuchi_file)[0]}.png"))
            else: shutil.copy(base_path, os.path.join(KAO_KUCHI_DIR, base_file))

        if effect_files:
            ensure_dir(KAO_KUCHI_EFFECT_DIR)
            print("  第四步: kao_kuchi + [效果組合] -> kao_kuchi_effect")
            for base_file in [f for f in os.listdir(KAO_KUCHI_DIR) if f.startswith(fuku_base_name)]:
                base_path = os.path.join(KAO_KUCHI_DIR, base_file)
                for size in range(1, min(MAX_EFFECT_LAYERS, len(effect_files)) + 1):
                    for effect_combo in itertools.combinations(effect_files, size):
                        current_image = Image.open(base_path).convert("RGBA")
                        for effect_file in effect_combo:
                            result_image = composite_images(current_image, os.path.join(EFFECT_DIR, effect_file), fuku_coords, current_pos_map)
                            if result_image: current_image = result_image
                        combo_suffix = "_".join(sorted([os.path.splitext(f)[0] for f in effect_combo]))
                        current_image.save(os.path.join(KAO_KUCHI_EFFECT_DIR, f"{os.path.splitext(base_file)[0]}_{combo_suffix}.png"))
        else: print("  資訊: 'effect' 為空，已跳過。")
        
        if hoho_files:
            ensure_dir(KAO_KUCHI_HOHO_DIR)
            print("  第五步: kao_kuchi + hoho -> kao_kuchi_hoho")
            for base_file in [f for f in os.listdir(KAO_KUCHI_DIR) if f.startswith(fuku_base_name)]:
                for hoho_file in hoho_files:
                    composed = composite_images(os.path.join(KAO_KUCHI_DIR, base_file), os.path.join(HOHO_DIR, hoho_file), fuku_coords, current_pos_map)
                    if composed: composed.save(os.path.join(KAO_KUCHI_HOHO_DIR, f"{os.path.splitext(base_file)[0]}_{os.path.splitext(hoho_file)[0]}.png"))
        else: print("  資訊: 'hoho' 為空，已跳過。")
            
        if hoho_files and effect_files:
            ensure_dir(KAO_KUCHI_HOHO_EFFECT_DIR)
            print("  第六步: kao_kuchi_hoho + [效果組合] -> kao_kuchi_hoho_effect")
            for base_file in [f for f in os.listdir(KAO_KUCHI_HOHO_DIR) if f.startswith(fuku_base_name)]:
                base_path = os.path.join(KAO_KUCHI_HOHO_DIR, base_file)
                for size in range(1, min(MAX_EFFECT_LAYERS, len(effect_files)) + 1):
                    for effect_combo in itertools.combinations(effect_files, size):
                        current_image = Image.open(base_path).convert("RGBA")
                        for effect_file in effect_combo:
                            result_image = composite_images(current_image, os.path.join(EFFECT_DIR, effect_file), fuku_coords, current_pos_map)
                            if result_image: current_image = result_image
                        combo_suffix = "_".join(sorted([os.path.splitext(f)[0] for f in effect_combo]))
                        current_image.save(os.path.join(KAO_KUCHI_HOHO_EFFECT_DIR, f"{os.path.splitext(base_file)[0]}_{combo_suffix}.png"))
        else: print("  資訊: 'hoho' 或 'effect' 為空，已跳過第六步。")

    print(f"\n--- 專案 {source_path} 處理完畢！ ---")
    if os.path.exists(TEMP_DIR):
        try:
            shutil.rmtree(TEMP_DIR)
            print(f"已清理臨時資料夾: {TEMP_DIR}")
        except OSError as e:
            print(f"錯誤: 清理臨時資料夾失敗: {e}")

# --- 啟動函式 ---

def find_and_process_directories(start_path='.'):
    """掃描並處理所有符合條件的專案資料夾。"""
    print("開始掃描專案資料夾...")
    # 執行腳本時，pos.txt 應與 .py 檔案放在同一個目錄
    pos_data = parse_pos_file('pos.txt')
    found_projects = 0
    for root, dirs, files in os.walk(start_path):
        if "fuku" in dirs and "kao" in dirs:
            if os.path.sep + 'output' + os.path.sep in root + os.path.sep:
                continue
            found_projects += 1
            process_directory(root, pos_data)
    if found_projects == 0:
        print("未找到任何包含 'fuku' 和 'kao' 的專案資料夾。")
    else:
        print(f"\n--- 所有 {found_projects} 個專案都已處理完畢！ ---")

# --- 主程式入口 ---
if __name__ == '__main__':
    find_and_process_directories()
