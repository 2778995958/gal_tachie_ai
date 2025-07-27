import os
import sys
from PIL import Image
import itertools
import csv

def ensure_dir(dir_path):
    """確保資料夾存在，若不存在則建立。"""
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

# ==================================================================
# ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼ 核心修改 ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
# 此函式被修改為永遠回傳 (0, 0) 作為座標
# ==================================================================
def get_image_info(file_path):
    """獲取圖片的尺寸，並固定回傳 (0, 0) 作為座標。"""
    try:
        with Image.open(file_path) as img:
            size = img.size
            # 無論圖片為何，都將其位置視為 (0, 0)
            return size, (0, 0)
    except FileNotFoundError:
        return None, None
    except Exception as e:
        print(f"警告：讀取圖片 '{file_path}' 尺寸時發生錯誤: {e}")
        return None, None

def get_files_safely(dir_name):
    """安全地獲取資料夾中的所有 .png 檔案路徑。"""
    if not os.path.isdir(dir_name):
        return []
    return [os.path.join(dir_name, f) for f in os.listdir(dir_name) if f.endswith('.png')]

def calculate_and_composite(parts_info, output_path):
    """
    基於所有部件的絕對座標計算總邊界，並在一個新建的畫布上合成圖片。
    """
    if not parts_info:
        return

    min_x, min_y, max_x, max_y = float('inf'), float('inf'), float('-inf'), float('-inf')

    for _part_path, size, pos in parts_info:
        part_x, part_y = pos
        part_width, part_height = size
        min_x = min(min_x, part_x)
        min_y = min(min_y, part_y)
        max_x = max(max_x, part_x + part_width)
        max_y = max(max_y, part_y + part_height)

    canvas_width = max_x - min_x
    canvas_height = max_y - min_y

    if canvas_width <= 0 or canvas_height <= 0:
        print(f"警告：計算出的畫布尺寸無效 ({canvas_width}x{canvas_height})，跳過合成 {output_path}")
        return

    final_image = Image.new('RGBA', (canvas_width, canvas_height), (0, 0, 0, 0))

    for part in parts_info:
        part_path, _size, pos = part
        paste_x = pos[0] - min_x
        paste_y = pos[1] - min_y
        try:
            temp_layer = Image.new('RGBA', final_image.size, (0, 0, 0, 0))
            with Image.open(part_path) as part_img:
                temp_layer.paste(part_img.convert("RGBA"), (paste_x, paste_y))
            final_image = Image.alpha_composite(final_image, temp_layer)
        except FileNotFoundError:
            print(f"警告：合成時找不到檔案 {part_path}")
            continue
            
    final_image.save(output_path)
    print(f"  -> 已生成: {output_path}")

def generate_and_save(base_compositions, optional_parts, target_dir):
    """
    將可選部件添加到基礎組合中，並處理排序、檢查和儲存。
    (已更新檔名生成規則)
    """
    if not base_compositions:
        return []
    
    if not optional_parts:
        compositions_to_process = base_compositions
    else:
        compositions_to_process = [base + [part] for base in base_compositions for part in optional_parts]

    final_compositions = []
    for comp in compositions_to_process:
        # 圖層排序邏輯保持不變
        layer_order = {'fuku': 0, 'hoho': 1, 'kao': 2, 'kuchi': 3, 'kami': 4, 'effect': 5}
        def get_layer_key(path):
            part_type = os.path.basename(os.path.dirname(path))
            return layer_order.get(part_type, 99)
        comp.sort(key=get_layer_key)

        parts_info = []
        output_name_parts = [] # 這個列表將根據新規則來填充
        valid_composition = True
        for part_path in comp:
            if not os.path.exists(part_path):
                print(f"警告：檔案不存在 '{part_path}'，此組合將被跳過。")
                valid_composition = False
                break
            
            size, pos = get_image_info(part_path)
            if not size or pos is None:
                print(f"警告：無法獲取 '{os.path.basename(part_path)}' 的尺寸。")
                print(f"      => 此組合 {[os.path.basename(p) for p in comp]} 將被跳過。\n")
                valid_composition = False
                break
            parts_info.append((part_path, size, pos))

            # ==================================================================
            # ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼ 核心修改 ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
            # 根據部件所在的資料夾決定檔名片段
            # ==================================================================
            part_type = os.path.basename(os.path.dirname(part_path))
            base_name = os.path.splitext(os.path.basename(part_path))[0]

            if part_type == 'fuku':
                # 如果是 fuku，使用完整檔名
                output_name_parts.append(base_name)
            else:
                # 對於所有其他類型，取最後一個底線後的部分
                if '_' in base_name:
                    # 從右邊分割一次，取最後一個元素
                    name_part = base_name.rsplit('_', 1)[-1]
                    output_name_parts.append(name_part)
                else:
                    # 如果沒有底線，為避免錯誤，直接使用完整檔名
                    output_name_parts.append(base_name)
            # ==================================================================
        
        if not valid_composition or not parts_info:
            continue

        # 使用新的 output_name_parts 列表來組合最終檔名
        output_filename = "_".join(output_name_parts) + ".png"
        output_path = os.path.join(target_dir, output_filename)

        if os.path.exists(output_path):
            print(f"  -> 已存在，跳過: {output_path}")
            final_compositions.append(comp)
            continue

        final_compositions.append(comp)
        print(f"\n處理組合: {[os.path.basename(p) for p in comp]}")
        print(f"  -> 生成檔名: {output_filename}") # 增加一行日誌，方便確認檔名是否正確
        calculate_and_composite(parts_info, output_path)
    
    return final_compositions

def process_directory(source_path):
    """
    處理單一專案資料夾的所有合成任務。
    (已移除 pos_lookup 參數)
    """
    print(f"\n=================================================")
    print(f"=== 正在處理專案: {source_path}")
    print(f"=================================================\n")

    OUTPUT_ROOT = os.path.join(source_path, "output")
    ensure_dir(OUTPUT_ROOT)

    sub_dirs = ["kao_kuchi", "kao_kuchi_hoho", "kao_kuchi_effect", "kao_kuchi_hoho_effect"]
    for sub in sub_dirs:
        ensure_dir(os.path.join(OUTPUT_ROOT, sub))

    fuku_files = get_files_safely(os.path.join(source_path, "fuku"))
    kao_files = get_files_safely(os.path.join(source_path, "kao"))
    kami_files = get_files_safely(os.path.join(source_path, "kami"))
    kuchi_files = get_files_safely(os.path.join(source_path, "kuchi"))
    hoho_files = get_files_safely(os.path.join(source_path, "hoho"))
    effect_files = get_files_safely(os.path.join(source_path, "effect"))

    if not fuku_files or not kao_files:
        print(f"錯誤：在 '{source_path}' 中找不到 'fuku' 或 'kao' 資料夾，或其中沒有 .png 檔案。跳過此專案。")
        return

    print("--- 步驟 1: 建立核心組合 (fuku + kao -> + kami -> + kuchi) ---")
    core_comps = [[f, k] for f in fuku_files for k in kao_files]

    if kami_files:
        print("  -> 發現 'kami'，正在添加到核心組合...")
        core_comps = [c + [k] for c in core_comps for k in kami_files]

    if kuchi_files:
        print("  -> 發現 'kuchi'，正在添加到核心組合...")
        core_comps = [c + [ku] for c in core_comps for ku in kuchi_files]

    print("\n--- 步驟 2: 儲存核心組合到 'kao_kuchi' 資料夾 ---")
    saved_core_comps = generate_and_save(core_comps, [], os.path.join(OUTPUT_ROOT, "kao_kuchi"))

    saved_hoho_comps = []
    if hoho_files:
        print("\n--- 步驟 3: 添加 'hoho' (臉頰) ---")
        saved_hoho_comps = generate_and_save(saved_core_comps, hoho_files, os.path.join(OUTPUT_ROOT, "kao_kuchi_hoho"))

    if effect_files:
        print("\n--- 步驟 4 (分支 A): 為核心組合添加 'effect' ---")
        generate_and_save(saved_core_comps, effect_files, os.path.join(OUTPUT_ROOT, "kao_kuchi_effect"))
        
        if saved_hoho_comps:
            print("\n--- 步驟 4 (分支 B): 為 hoho 組合添加 'effect' ---")
            generate_and_save(saved_hoho_comps, effect_files, os.path.join(OUTPUT_ROOT, "kao_kuchi_hoho_effect"))
            
    print(f"\n--- 專案 {source_path} 處理完畢！ ---")

# ==================================================================
# ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼ 核心修改 ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
# 已完全移除讀取 master_coordinates.txt 的程式碼
# ==================================================================
def find_and_process_directories(start_path='.'):
    """尋找並處理所有專案資料夾。"""
    print("--- 程式啟動 ---")
    print("[資訊] 目前模式：所有圖片座標皆視為 (0, 0)。將不再讀取 master_coordinates.txt。")

    print("\n--- 開始掃描專案資料夾 ---")
    found_projects = 0
    # 使用 os.path.abspath 將相對路徑轉為絕對路徑，讓掃描更穩定
    search_path = os.path.abspath(start_path)
    for root, dirs, files in os.walk(search_path, topdown=True):
        if 'output' in dirs:
            dirs.remove('output') # 避免進入 output 資料夾掃描
        # 判斷是否為專案資料夾的標準是底下同時有 fuku 和 kao
        if "fuku" in dirs and "kao" in dirs:
            found_projects += 1
            # 直接處理該目錄，不再需要傳入 pos_lookup
            process_directory(root)
            # 處理完一個專案後，從 dirs 列表中移除它的子資料夾，避免重複深入
            dirs[:] = [d for d in dirs if d not in ["fuku", "kao", "kami", "kuchi", "hoho", "effect"]]

    if found_projects == 0:
        print(f"\n在路徑 '{search_path}' 下未找到任何包含 'fuku' 和 'kao' 子資料夾的專案。")
    print(f"\n--- 所有 {found_projects} 個專案都已處理完畢！ ---")

if __name__ == '__main__':
    find_and_process_directories()
