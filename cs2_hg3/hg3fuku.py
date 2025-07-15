import os
import csv
import re # 引入 re 模組來輔助字串分解
from PIL import Image
import numpy as np

# --- 基礎設定 ---
IMAGES_BASE_DIR = "images"
OUTPUT_DIR = "output"
COORDS_FILENAME = "hg3_coordinates.txt"

# 部件的資料夾名稱
FUKU_DIR_NAME = "fuku"
KAO_DIR_NAME = "kao"
KAMI_DIR_NAME = "kami"
KUCHI_DIR_NAME = "kuchi"
HOHO_DIR_NAME = "hoho"
EFFECT_DIR_NAME = "effect"

# --- 核心輔助函式 ---

def ensure_dir(dir_path):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

def _read_lines_with_fallback(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            return f.readlines()
    except UnicodeDecodeError:
        try:
            with open(file_path, 'r', encoding='shift_jis') as f:
                return f.readlines()
        except Exception as e:
            print(f"錯誤：使用 Shift-JIS 也無法讀取 {file_path}: {e}")
            return None
    except Exception as e:
        print(f"錯誤：讀取 {file_path} 時發生未知錯誤: {e}")
        return None

def load_hg3_coordinates(file_path):
    print(f"[*] 正在讀取全域座標檔案: {file_path}")
    if not os.path.exists(file_path):
        print(f"錯誤：找不到座標檔案 {file_path}")
        return None
    lines = _read_lines_with_fallback(file_path)
    if lines is None: return None
    coords = {}
    reader = csv.DictReader(lines, delimiter='\t')
    for row in reader:
        filename = row.get('FileName', '').strip()
        if not filename: continue
        key = os.path.splitext(filename)[0].lower()
        for col in ['FragmentWidth', 'FragmentHeight', 'OffsetX', 'OffsetY', 'CanvasWidth', 'CanvasHeight']:
            value = row.get(col, '0').strip()
            row[col] = int(value) if value else 0
        coords[key] = row
    print(f" > 座標讀取完成，共找到 {len(coords)} 筆座標定義。")
    return coords

def get_image_info(file_path, coords_data):
    key = os.path.splitext(os.path.basename(file_path))[0].lower()
    info = coords_data.get(key)
    if not info:
        print(f"警告：在 {COORDS_FILENAME} 中找不到鍵 '{key}' 的座標資訊。")
    return info

def get_png_files_from_dir(dir_path):
    if not os.path.isdir(dir_path): return []
    return sorted([os.path.join(dir_path, f) for f in os.listdir(dir_path) if f.endswith('.png')])

def get_all_png_files(dir_path):
    if not os.path.isdir(dir_path): return []
    all_files = []
    for item in os.listdir(dir_path):
        item_path = os.path.join(dir_path, item)
        if os.path.isdir(item_path):
            all_files.extend(get_all_png_files(item_path))
        elif item.endswith('.png'):
            all_files.append(item_path)
    return sorted(all_files)

def composite_numpy(base_np, part_img, part_pos):
    """使用 NumPy 進行高效的 Alpha 合成。"""
    try:
        part_np = np.array(part_img, dtype=np.uint8)
        part_h, part_w, _ = part_np.shape
        base_h, base_w, _ = base_np.shape
        x, y = part_pos
        x1, y1 = max(x, 0), max(y, 0)
        x2, y2 = min(x + part_w, base_w), min(y + part_h, base_h)
        part_x1, part_y1 = x1 - x, y1 - y
        part_x2, part_y2 = x2 - x, y2 - y
        if x1 >= x2 or y1 >= y2:
            return base_np
        base_region = base_np[y1:y2, x1:x2]
        part_region = part_np[part_y1:part_y2, part_x1:part_x2]
        part_alpha = (part_region[:, :, 3] / 255.0)[:, :, np.newaxis]
        blended_rgb = (part_region[:, :, :3] * part_alpha + base_region[:, :, :3] * (1 - part_alpha)).astype(np.uint8)
        new_alpha = (part_region[:, :, 3] + base_region[:, :, 3] * (1 - part_alpha.squeeze())).astype(np.uint8)
        base_np[y1:y2, x1:x2, :3] = blended_rgb
        base_np[y1:y2, x1:x2, 3] = new_alpha
        return base_np
    except Exception as e:
        print(f"      └ 錯誤: NumPy 合成失敗: {e}")
        return base_np

def get_short_name(file_path):
    name = os.path.splitext(os.path.basename(file_path))[0]
    return name.rsplit('_', 1)[-1] if '_' in name else name

# --- 【已修正】自訂排序函式 ---
def natural_sort_key(s):
    """
    產生一個可用於自然排序的鍵。
    規則：
    1. 優先按檔名分解後的部分數量排序（部分越少越靠前）。
    2. 部分數量相同時，再按 a-z -> 0-9 的規則排序。
    """
    s = os.path.splitext(os.path.basename(s))[0]
    parts = re.split('([0-9]+)', s)
    key_list = []
    for part in parts:
        if part.isdigit():
            # (1, 數字)
            key_list.append((1, int(part)))
        elif part:
            # (0, 文字)
            key_list.append((0, part))
    
    # 返回一個元組，第一個元素是分解部分的長度，第二個是分解列表本身
    # Python 在排序元組時，會先比較第一個元素
    return (len(key_list), key_list)


def process_character(char_dir_path, coords_data):
    char_name = os.path.basename(char_dir_path)
    print(f"\n{'='*25} 開始處理角色: {char_name} {'='*25}")

    output_root = os.path.join(OUTPUT_DIR, char_name)
    ensure_dir(output_root)

    part_paths = {name: os.path.join(char_dir_path, name) for name in [FUKU_DIR_NAME, HOHO_DIR_NAME, KAO_DIR_NAME, KAMI_DIR_NAME, KUCHI_DIR_NAME, EFFECT_DIR_NAME]}

    fuku_files = get_all_png_files(part_paths[FUKU_DIR_NAME])
    kao_files = get_png_files_from_dir(part_paths[KAO_DIR_NAME])
    kami_files = get_png_files_from_dir(part_paths[KAMI_DIR_NAME])
    kuchi_files = get_png_files_from_dir(part_paths[KUCHI_DIR_NAME])
    hoho_files = get_png_files_from_dir(part_paths[HOHO_DIR_NAME])
    effect_files = get_png_files_from_dir(part_paths[EFFECT_DIR_NAME])

    print(f"--- [{char_name}] 零件掃描結果 ---")
    print(f" > Fuku: {len(fuku_files)} | Kami: {len(kami_files)} | Kao: {len(kao_files)}")
    print(f" > Kuchi: {len(kuchi_files)} | Hoho: {len(hoho_files)} | Effect: {len(effect_files)}")

    if not fuku_files or not kao_files:
        print(f"錯誤: 角色 '{char_name}' 的 'fuku' 或 'kao' 資料夾為空或不存在，跳過此角色。")
        return

    fuku_groups = []
    fuku_dir = part_paths.get(FUKU_DIR_NAME)
    if os.path.isdir(fuku_dir):
        subdirs = [d for d in os.listdir(fuku_dir) if os.path.isdir(os.path.join(fuku_dir, d))]
        if subdirs:
            for subdir_name in sorted(subdirs):
                files = get_png_files_from_dir(os.path.join(fuku_dir, subdir_name))
                if files: fuku_groups.append((subdir_name, files))
        else:
            for f_path in get_png_files_from_dir(fuku_dir):
                group_name = os.path.splitext(os.path.basename(f_path))[0]
                fuku_groups.append((group_name, [f_path]))

    print(f"--- [{char_name}] 檢測到 {len(fuku_groups)} 種 Fuku 基礎群組 ---")

    for fuku_base_name, fuku_group_files in fuku_groups:
        print(f"\n--- [{char_name}] 開始處理 Fuku 群組: {fuku_base_name} ---")
        
        # 使用修正後的排序邏輯
        fuku_group_files.sort(key=natural_sort_key)
        print(" > Fuku 圖層排序結果:")
        for f in fuku_group_files:
            print(f"   - {os.path.basename(f)}")

        base_fuku_info = get_image_info(fuku_group_files[0], coords_data)
        if not base_fuku_info:
            print(f"錯誤: 找不到基礎服裝 '{fuku_group_files[0]}' 的座標資訊，跳過此群組。")
            continue

        canvas_size = (base_fuku_info['CanvasWidth'], base_fuku_info['CanvasHeight'])
        print(f" > 此群組基準畫布大小為: {canvas_size}")

        base_np = np.zeros((canvas_size[1], canvas_size[0], 4), dtype=np.uint8)
        for path in fuku_group_files:
            info = get_image_info(path, coords_data)
            if not info: continue
            with Image.open(path) as p_img:
                base_np = composite_numpy(base_np, p_img.convert("RGBA"), (info['OffsetX'], info['OffsetY']))
        fuku_base_img = Image.fromarray(base_np)

        body_bases = {}
        if kami_files:
            for kami_path in kami_files:
                info_k = get_image_info(kami_path, coords_data)
                if not info_k: continue
                with Image.open(kami_path) as p_img:
                    body_np = composite_numpy(np.array(fuku_base_img), p_img.convert("RGBA"), (info_k['OffsetX'], info_k['OffsetY']))
                body_name = f"{char_name}_{fuku_base_name}_{get_short_name(kami_path)}"
                body_bases[body_name] = Image.fromarray(body_np)
        else:
            body_name = f"{char_name}_{fuku_base_name}"
            body_bases[body_name] = fuku_base_img

        print(f"\n--- [{fuku_base_name}] 流程 A.1: 建立標準臉 (fuku_face) ---")
        fuku_face_dir = os.path.join(output_root, "fuku_face"); ensure_dir(fuku_face_dir)
        face_images = {}
        for body_name, body_img in body_bases.items():
            for kao_path in kao_files:
                base_np_a = np.array(body_img)
                info = get_image_info(kao_path, coords_data)
                if not info: continue
                with Image.open(kao_path) as p_img:
                    base_np_a = composite_numpy(base_np_a, p_img.convert("RGBA"), (info['OffsetX'], info['OffsetY']))
                name_parts = [body_name, get_short_name(kao_path)]
                if kuchi_files:
                    for kuchi_path in kuchi_files:
                        info_k = get_image_info(kuchi_path, coords_data)
                        if not info_k: continue
                        with Image.open(kuchi_path) as p_img:
                            final_np = composite_numpy(base_np_a.copy(), p_img.convert("RGBA"), (info_k['OffsetX'], info_k['OffsetY']))
                        final_img = Image.fromarray(final_np)
                        final_name = "_".join(name_parts + [get_short_name(kuchi_path)]) + ".png"
                        output_path = os.path.join(fuku_face_dir, final_name)
                        if not os.path.exists(output_path):
                            final_img.save(output_path)
                        face_images[final_name] = final_img
                else:
                    final_img = Image.fromarray(base_np_a)
                    final_name = "_".join(name_parts) + ".png"
                    output_path = os.path.join(fuku_face_dir, final_name)
                    if not os.path.exists(output_path):
                        final_img.save(output_path)
                    face_images[final_name] = final_img
        print(f" > 已處理 {len(face_images)} 張標準臉。")
        
        if effect_files:
            print(f"--- [{fuku_base_name}] 流程 A.2: 疊加特效 (fuku_face_effect) ---")
            fuku_face_effect_dir = os.path.join(output_root, "fuku_face_effect"); ensure_dir(fuku_face_effect_dir)
            count = 0
            for face_name, face_img in face_images.items():
                for effect_path in effect_files:
                    info_e = get_image_info(effect_path, coords_data)
                    if not info_e: continue
                    final_name = f"{os.path.splitext(face_name)[0]}_{get_short_name(effect_path)}.png"
                    output_path = os.path.join(fuku_face_effect_dir, final_name)
                    if not os.path.exists(output_path):
                        with Image.open(effect_path) as p_img:
                            final_np = composite_numpy(np.array(face_img), p_img.convert("RGBA"), (info_e['OffsetX'], info_e['OffsetY']))
                        Image.fromarray(final_np).save(output_path)
                        count += 1
            print(f" > 新增生成 {count} 張標準臉特效。")

        if hoho_files:
            print(f"\n--- [{fuku_base_name}] 流程 B.1: 建立臉紅妝 (fuku_face_hoho) ---")
            fuku_face_hoho_dir = os.path.join(output_root, "fuku_face_hoho"); ensure_dir(fuku_face_hoho_dir)
            hoho_face_images = {}
            for body_name, body_img in body_bases.items():
                for hoho_path in hoho_files:
                    info_h = get_image_info(hoho_path, coords_data)
                    if not info_h: continue
                    with Image.open(hoho_path) as p_img:
                        base_np_b = composite_numpy(np.array(body_img), p_img.convert("RGBA"), (info_h['OffsetX'], info_h['OffsetY']))
                    for kao_path in kao_files:
                        info_k = get_image_info(kao_path, coords_data)
                        if not info_k: continue
                        with Image.open(kao_path) as p_img:
                            kao_np = composite_numpy(base_np_b.copy(), p_img.convert("RGBA"), (info_k['OffsetX'], info_k['OffsetY']))
                        name_parts = [body_name, get_short_name(hoho_path), get_short_name(kao_path)]
                        if kuchi_files:
                            for kuchi_path in kuchi_files:
                                info_ku = get_image_info(kuchi_path, coords_data)
                                if not info_ku: continue
                                with Image.open(kuchi_path) as p_img:
                                    final_np = composite_numpy(kao_np.copy(), p_img.convert("RGBA"), (info_ku['OffsetX'], info_ku['OffsetY']))
                                final_img = Image.fromarray(final_np)
                                final_name = "_".join(name_parts + [get_short_name(kuchi_path)]) + ".png"
                                output_path = os.path.join(fuku_face_hoho_dir, final_name)
                                if not os.path.exists(output_path):
                                    final_img.save(output_path)
                                hoho_face_images[final_name] = final_img
                        else:
                            final_img = Image.fromarray(kao_np)
                            final_name = "_".join(name_parts) + ".png"
                            output_path = os.path.join(fuku_face_hoho_dir, final_name)
                            if not os.path.exists(output_path):
                                final_img.save(output_path)
                            hoho_face_images[final_name] = final_img
            print(f" > 已處理 {len(hoho_face_images)} 張臉紅妝。")
            
            if effect_files and hoho_face_images:
                print(f"--- [{fuku_base_name}] 流程 B.2: 疊加臉紅妝特效 (fuku_face_hoho_effect) ---")
                fuku_face_hoho_effect_dir = os.path.join(output_root, "fuku_face_hoho_effect"); ensure_dir(fuku_face_hoho_effect_dir)
                count = 0
                for face_name, face_img in hoho_face_images.items():
                    for effect_path in effect_files:
                        info_e = get_image_info(effect_path, coords_data)
                        if not info_e: continue
                        final_name = f"{os.path.splitext(face_name)[0]}_{get_short_name(effect_path)}.png"
                        output_path = os.path.join(fuku_face_hoho_effect_dir, final_name)
                        if not os.path.exists(output_path):
                            with Image.open(effect_path) as p_img:
                                final_np = composite_numpy(np.array(face_img), p_img.convert("RGBA"), (info_e['OffsetX'], info_e['OffsetY']))
                            Image.fromarray(final_np).save(output_path)
                            count += 1
                print(f" > 新增生成 {count} 張臉紅妝特效。")
            elif effect_files:
                print(f"--- [{fuku_base_name}] 流程 B.2: 因沒有任何 '臉紅妝' 圖片生成，已跳過疊加特效。")


def main():
    script_dir = os.getcwd()
    print(f"[*] 開始掃描，工作目錄為: {script_dir}")

    if not os.path.exists(COORDS_FILENAME):
        print(f"[!] 錯誤: 在工作目錄中找不到座標檔案 '{COORDS_FILENAME}'。")
        return
    if not os.path.isdir(IMAGES_BASE_DIR):
        print(f"[!] 錯誤: 在工作目錄中找不到圖片資料夾 '{IMAGES_BASE_DIR}'。")
        return

    coords_data = load_hg3_coordinates(COORDS_FILENAME)
    if not coords_data:
        return

    try:
        char_dirs = [os.path.join(IMAGES_BASE_DIR, d) for d in os.listdir(IMAGES_BASE_DIR) if os.path.isdir(os.path.join(IMAGES_BASE_DIR, d))]
    except FileNotFoundError:
        print(f"[!] 錯誤: 圖片資料夾 '{IMAGES_BASE_DIR}' 不存在。")
        return

    if not char_dirs:
        print(f"[!] 警告: 在 '{IMAGES_BASE_DIR}' 中沒有找到任何角色資料夾。")
        return

    print(f"[*] 偵測到 {len(char_dirs)} 個角色: {[os.path.basename(d) for d in char_dirs]}")

    for char_path in char_dirs:
        process_character(char_path, coords_data)

    print(f"\n{'='*60}\n所有角色處理完畢！\n{'='*60}")

if __name__ == '__main__':
    main()