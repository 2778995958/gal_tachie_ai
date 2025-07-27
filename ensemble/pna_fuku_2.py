import os
import sys
from PIL import Image
import itertools
import csv

def ensure_dir(dir_path):
    """確保資料夾存在，若不存在則建立。"""
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

def get_image_info(file_path, pos_lookup_map):
    """獲取圖片的尺寸和位置座標。"""
    base_filename = os.path.basename(file_path)
    size = None
    try:
        with Image.open(file_path) as img:
            size = img.size
    except FileNotFoundError:
        return None, None
    except Exception as e:
        print(f"警告：讀取圖片 '{file_path}' 尺寸時發生錯誤: {e}")
        return None, None
    if base_filename in pos_lookup_map:
        pos = pos_lookup_map[base_filename]
        return size, pos
    else:
        return size, None

def get_files_safely(dir_name):
    """安全地獲取資料夾中的所有 .png 檔案路徑。"""
    if not os.path.isdir(dir_name):
        return []
    return [os.path.join(dir_name, f) for f in os.listdir(dir_name) if f.endswith('.png')]

def calculate_and_composite(parts_info, output_path):
    """以第一個部件為基準點，計算相對位置並合成圖片。"""
    if not parts_info:
        return
    _base_part_path, _base_size, base_pos = parts_info[0]
    origin_x, origin_y = base_pos
    min_x, min_y, max_x, max_y = float('inf'), float('inf'), float('-inf'), float('-inf')
    relative_parts = []
    for part_path, size, pos in parts_info:
        relative_pos = (pos[0] - origin_x, pos[1] - origin_y)
        relative_parts.append({'path': part_path, 'size': size, 'rel_pos': relative_pos})
        min_x = min(min_x, relative_pos[0])
        min_y = min(min_y, relative_pos[1])
        max_x = max(max_x, relative_pos[0] + size[0])
        max_y = max(max_y, relative_pos[1] + size[1])
    canvas_width, canvas_height = max_x - min_x, max_y - min_y
    if canvas_width <= 0 or canvas_height <= 0:
        print(f"警告：計算出的畫布尺寸無效 ({canvas_width}x{canvas_height})，跳過合成 {output_path}")
        return
    final_image = Image.new('RGBA', (canvas_width, canvas_height), (0, 0, 0, 0))
    for part in relative_parts:
        paste_x, paste_y = part['rel_pos'][0] - min_x, part['rel_pos'][1] - min_y
        try:
            temp_layer = Image.new('RGBA', final_image.size, (0, 0, 0, 0))
            with Image.open(part['path']) as part_img:
                temp_layer.paste(part_img.convert("RGBA"), (paste_x, paste_y))
            final_image = Image.alpha_composite(final_image, temp_layer)
        except FileNotFoundError:
            print(f"警告：合成時找不到檔案 {part['path']}")
            continue
    final_image.save(output_path)
    print(f"  -> 已生成: {output_path}")

def generate_and_save(base_compositions, optional_parts, target_dir, pos_lookup):
    """
    將可選部件添加到基礎組合中，並處理排序、檢查和儲存。
    """
    if not base_compositions:
         return []
    
    if not optional_parts:
        compositions_to_process = base_compositions
    else:
        compositions_to_process = [base + [part] for base in base_compositions for part in optional_parts]

    final_compositions = []
    for comp in compositions_to_process:
        layer_order = {'fuku': 0, 'hoho': 1, 'kao': 2, 'kuchi': 3, 'kami': 4, 'effect': 5}
        def get_layer_key(path):
            part_type = os.path.basename(os.path.dirname(path))
            return layer_order.get(part_type, 99)
        comp.sort(key=get_layer_key)

        parts_info = []
        output_name_parts = []
        valid_composition = True
        for part_path in comp:
            if not os.path.exists(part_path):
                print(f"警告：檔案不存在 '{part_path}'，此組合將被跳過。")
                valid_composition = False
                break
            size, pos = get_image_info(part_path, pos_lookup)
            if not size or not pos:
                print(f"警告：無法獲取 '{os.path.basename(part_path)}' 的尺寸或座標。")
                print(f"      => 請確認該檔案存在，且其檔名已在 master_coordinates.txt 中正確定義。")
                print(f"      => 此組合 {[os.path.basename(p) for p in comp]} 將被跳過。\n")
                valid_composition = False
                break
            parts_info.append((part_path, size, pos))
            output_name_parts.append(os.path.splitext(os.path.basename(part_path))[0])
        
        if not valid_composition or not parts_info:
            continue

        output_filename = "_".join(output_name_parts) + ".png"
        output_path = os.path.join(target_dir, output_filename)

        if os.path.exists(output_path):
            print(f"  -> 已存在，跳過: {output_path}")
            final_compositions.append(comp)
            continue

        final_compositions.append(comp)
        print(f"\n處理組合: {[os.path.basename(p) for p in comp]}")
        calculate_and_composite(parts_info, output_path)
    
    return final_compositions

# ==================================================================
# ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼ 此函式流程已重構 ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
# ==================================================================
def process_directory(source_path, pos_lookup):
    """處理單一專案資料夾的所有合成任務，使用傳入的全域座標。"""
    print(f"\n=================================================")
    print(f"=== 正在處理專案: {source_path}")
    print(f"=================================================\n")

    OUTPUT_ROOT = os.path.join(source_path, "output")
    ensure_dir(OUTPUT_ROOT)

    # 預先建立所有輸出子資料夾
    sub_dirs = ["kao_kuchi", "kao_kuchi_hoho", "kao_kuchi_effect", "kao_kuchi_hoho_effect"]
    for sub in sub_dirs:
        ensure_dir(os.path.join(OUTPUT_ROOT, sub))

    # 獲取所有部件檔案
    fuku_files = get_files_safely(os.path.join(source_path, "fuku"))
    kao_files = get_files_safely(os.path.join(source_path, "kao"))
    kami_files = get_files_safely(os.path.join(source_path, "kami"))
    kuchi_files = get_files_safely(os.path.join(source_path, "kuchi"))
    hoho_files = get_files_safely(os.path.join(source_path, "hoho"))
    effect_files = get_files_safely(os.path.join(source_path, "effect"))

    if not fuku_files or not kao_files:
        print(f"錯誤：在 '{source_path}' 中找不到 'fuku' 或 'kao' 資料夾，或其中沒有 .png 檔案。跳過此專案。")
        return

    # --- 步驟 1: 在記憶體中建立最完整的「核心組合」 ---
    # 從 fuku + kao 開始
    print("--- 步驟 1: 建立核心組合 (fuku + kao -> + kami -> + kuchi) ---")
    core_comps = [[f, k] for f in fuku_files for k in kao_files]

    # 如果有 kami，添加到組合中
    if kami_files:
        print("  -> 發現 'kami'，正在添加到核心組合...")
        # 使用列表推導式來合併
        core_comps = [c + [k] for c in core_comps for k in kami_files]

    # 如果有 kuchi，添加到組合中
    if kuchi_files:
        print("  -> 發現 'kuchi'，正在添加到核心組合...")
        core_comps = [c + [ku] for c in core_comps for ku in kuchi_files]

    # --- 步驟 2: 將最終的核心組合儲存到 'kao_kuchi' 資料夾 ---
    print("\n--- 步驟 2: 儲存核心組合到 'kao_kuchi' 資料夾 ---")
    # 呼叫 generate_and_save，但 optional_parts 給予空列表 []
    # 這會告訴函式：不要再添加新部件了，直接處理並儲存我給你的 core_comps 列表
    saved_core_comps = generate_and_save(core_comps, [], os.path.join(OUTPUT_ROOT, "kao_kuchi"), pos_lookup)

    # --- 步驟 3: 基於核心組合，添加 'hoho' (臉頰) ---
    saved_hoho_comps = []
    if hoho_files:
        print("\n--- 步驟 3: 添加 'hoho' (臉頰) ---")
        # 以儲存好的核心組合為基礎，添加 hoho 部件
        saved_hoho_comps = generate_and_save(saved_core_comps, hoho_files, os.path.join(OUTPUT_ROOT, "kao_kuchi_hoho"), pos_lookup)

    # --- 步驟 4: 基於各階段結果，添加 'effect' (特效) ---
    if effect_files:
        # 為核心組合添加特效
        print("\n--- 步驟 4 (分支 A): 為核心組合添加 'effect' ---")
        generate_and_save(saved_core_comps, effect_files, os.path.join(OUTPUT_ROOT, "kao_kuchi_effect"), pos_lookup)
        
        # 如果存在 hoho 組合，也為它們添加特效
        if saved_hoho_comps:
            print("\n--- 步驟 4 (分支 B): 為 hoho 組合添加 'effect' ---")
            generate_and_save(saved_hoho_comps, effect_files, os.path.join(OUTPUT_ROOT, "kao_kuchi_hoho_effect"), pos_lookup)
            
    print(f"\n--- 專案 {source_path} 處理完畢！ ---")


def find_and_process_directories(start_path='.'):
    """從腳本同目錄載入全域座標檔，然後尋找並處理所有專案資料夾。"""
    print("--- 程式啟動 ---")
    
    try:
        script_dir = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
    except NameError:
        script_dir = os.getcwd()
        
    coords_txt_path = os.path.join(script_dir, 'master_coordinates.txt')
    pos_lookup = {}
    if os.path.exists(coords_txt_path):
        print(f"[資訊] 正在從全域路徑讀取座標檔: {coords_txt_path}")
        try:
            with open(coords_txt_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader)
                for i, row in enumerate(reader, 1):
                    if len(row) < 5: continue
                    filename = row[2].strip()
                    try:
                        x, y = int(row[3].strip()), int(row[4].strip())
                        pos_lookup[filename] = (x, y)
                    except ValueError:
                        print(f"[警告] 全域座標檔第 {i+1} 行的座標 '{row[3]},{row[4]}' 無法解析，已跳過。")
            print(f"[成功] 全域座標檔讀取完畢，共載入 {len(pos_lookup)} 筆設定。")
        except Exception as e:
            print(f"[嚴重錯誤] 讀取全域座標檔 {coords_txt_path} 時發生錯誤: {e}")
            return
    else:
        print(f"[嚴重錯誤] 找不到全域座標檔: {coords_txt_path}！")
        print("             請確認 master_coordinates.txt 與 Python 腳本在同一個資料夾下。程式即將終止。")
        return

    print("\n--- 開始掃描專案資料夾 ---")
    found_projects = 0
    for root, dirs, files in os.walk(os.path.normpath(start_path), topdown=True):
        if 'output' in dirs:
            dirs.remove('output')
        if "fuku" in dirs:
            found_projects += 1
            process_directory(root, pos_lookup)
            
    if found_projects == 0:
        print("\n未找到任何包含 'fuku' 資料夾的專案。")
    print(f"\n--- 所有 {found_projects} 個專案都已處理完畢！ ---")

if __name__ == '__main__':
    find_and_process_directories()
