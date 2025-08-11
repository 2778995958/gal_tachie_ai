import os
import re
from collections import defaultdict
from PIL import Image
import numpy as np
import concurrent.futures
import time
import tqdm

# ==============================================================================
# --- 設定區 ---
# 你可以在這裡修改所有參數
# ==============================================================================

MAX_WORKERS = os.cpu_count()
INPUT_ROOT = "fg"
OUTPUT_ROOT = "output"

# 1. 【新設定】表情使用的編號「範圍」
#    只有在此範圍內的檔案會被視為表情。
FACE_SUFFIX_START = 1
FACE_SUFFIX_END = 80

# 2. 特別配件設定 (支援多種)
SPECIAL_ACCESSORIES = {
    "mio": [90, 91],
    "sui": [91],
    "yok": [99]
}

# 3. 臉紅效果使用的編號「範圍」
BLUSH_SUFFIX_START = 81
BLUSH_SUFFIX_END = 82

# 4. (一般)配件使用的「起始」編號
ACCESSORY_SUFFIX_START = 99

# 5. 角色內部的資料夾處理優先級順序
PROCESSING_ORDER = ["z2", "z1", "no", "bc", "fa"]

# ==============================================================================
# --- 核心程式區 ---
# ==============================================================================

def ensure_dir(dir_path):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

def get_image_position(file_path):
    try:
        with Image.open(file_path) as img:
            if 'comment' in img.info:
                comment_string = img.info['comment']
                parts = comment_string.split(',')
                if len(parts) >= 3 and parts[0] == 'pos':
                    return int(parts[1]), int(parts[2])
    except Exception:
        return None, None
    return None, None

def composite_images(base_image, overlay_path, base_coords):
    overlay_coords = get_image_position(overlay_path)
    if not base_coords or not overlay_coords:
        return base_image

    try:
        with Image.open(overlay_path).convert("RGBA") as overlay_img:
            overlay_canvas = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
            overlay_canvas.paste(overlay_img, (dx := overlay_coords[0] - base_coords[0], dy := overlay_coords[1] - base_coords[1]))

            base_arr = np.array(base_image) / 255.0
            overlay_arr = np.array(overlay_canvas) / 255.0
            
            alpha_fg = overlay_arr[:, :, 3:]
            if np.all(alpha_fg == 0): return base_image

            alpha_bg = base_arr[:, :, 3:]
            alpha_out = alpha_fg + alpha_bg * (1 - alpha_fg)
            
            rgb_fg = overlay_arr[:, :, :3]
            rgb_bg = base_arr[:, :, :3]
            
            rgb_out = np.divide(
                rgb_fg * alpha_fg + rgb_bg * alpha_bg * (1 - alpha_fg),
                alpha_out, out=np.zeros_like(rgb_fg), where=alpha_out != 0
            )
            
            output_arr = np.concatenate((rgb_out, alpha_out), axis=2)
            return Image.fromarray((output_arr * 255).astype('uint8'))
    except Exception:
        return base_image

def process_single_combination(args):
    body_path, face_path, body_coords, final_blush_path, special_accessory_paths, regular_accessory_paths, output_dir = args
    
    body_basename = os.path.splitext(os.path.basename(body_path))[0]
    face_concept_key = os.path.splitext(os.path.basename(face_path))[0]
    special_acc_tags = [os.path.splitext(os.path.basename(p))[0] for p in special_accessory_paths]
    special_acc_suffix = f"_{'_'.join(special_acc_tags)}" if special_acc_tags else ""
    
    base_filename_no_blush = f"{body_basename}_{face_concept_key}{special_acc_suffix}.png"
    base_filepath_no_blush = os.path.join(output_dir, base_filename_no_blush)
    
    base_filepath_with_blush = None
    if final_blush_path:
        blush_tag = f"_{os.path.splitext(os.path.basename(final_blush_path))[0]}"
        base_filename_with_blush = f"{body_basename}_{face_concept_key}{blush_tag}{special_acc_suffix}.png"
        base_filepath_with_blush = os.path.join(output_dir, base_filename_with_blush)

    tasks = {}
    if not os.path.exists(base_filepath_no_blush):
        tasks['base_no_blush'] = base_filepath_no_blush
    for r_acc_path in regular_accessory_paths:
        r_acc_tag = f"_{os.path.splitext(os.path.basename(r_acc_path))[0]}"
        acc_filepath = os.path.join(output_dir, f"{os.path.splitext(base_filename_no_blush)[0]}{r_acc_tag}.png")
        if not os.path.exists(acc_filepath):
            tasks[f'acc_no_blush_{r_acc_tag}'] = (acc_filepath, r_acc_path)

    if base_filepath_with_blush:
        if not os.path.exists(base_filepath_with_blush):
            tasks['base_with_blush'] = base_filepath_with_blush
        for r_acc_path in regular_accessory_paths:
            r_acc_tag = f"_{os.path.splitext(os.path.basename(r_acc_path))[0]}"
            acc_filepath = os.path.join(output_dir, f"{os.path.splitext(base_filename_with_blush)[0]}{r_acc_tag}.png")
            if not os.path.exists(acc_filepath):
                tasks[f'acc_with_blush_{r_acc_tag}'] = (acc_filepath, r_acc_path)

    if not tasks:
        return True

    try:
        base_no_blush_img, base_with_blush_img = None, None

        if any(k.startswith('base_no_blush') or k.startswith('acc_no_blush') for k in tasks):
            with Image.open(body_path).convert("RGBA") as body_img:
                base_no_blush_img = composite_images(body_img, face_path, body_coords)
                for sp_acc_path in special_accessory_paths:
                    base_no_blush_img = composite_images(base_no_blush_img, sp_acc_path, body_coords)
        
        if any(k.startswith('base_with_blush') or k.startswith('acc_with_blush') for k in tasks):
            with Image.open(body_path).convert("RGBA") as body_img:
                temp_blush_base = composite_images(body_img, final_blush_path, body_coords)
                base_with_blush_img = composite_images(temp_blush_base, face_path, body_coords)
                for sp_acc_path in special_accessory_paths:
                    base_with_blush_img = composite_images(base_with_blush_img, sp_acc_path, body_coords)
        
        if 'base_no_blush' in tasks and base_no_blush_img:
            base_no_blush_img.save(tasks['base_no_blush'])
        
        if 'base_with_blush' in tasks and base_with_blush_img:
            base_with_blush_img.save(tasks['base_with_blush'])

        for key, value in tasks.items():
            if key.startswith('acc_no_blush') and base_no_blush_img:
                acc_filepath, r_acc_path = value
                final_img = composite_images(base_no_blush_img, r_acc_path, body_coords)
                final_img.save(acc_filepath)
            elif key.startswith('acc_with_blush') and base_with_blush_img:
                acc_filepath, r_acc_path = value
                final_img = composite_images(base_with_blush_img, r_acc_path, body_coords)
                final_img.save(acc_filepath)
        return True

    except Exception as e:
        print(f"處理失敗: {os.path.basename(body_path)} + {os.path.basename(face_path)} -> {e}")
        return False

def prepare_jobs_from_directory(current_dir, character_name):
    print(f"--- 正在分析資料夾：{current_dir} ---")
    
    job_list = []
    groups = defaultdict(lambda: defaultdict(list))
    body_pattern = re.compile(r"^(.+)([a-z])(\d{4,})\.png$")
    face_pattern = re.compile(r"^([a-z])(\d{4,})\.png$")
    files_in_dir = [f for f in os.listdir(current_dir) if f.endswith('.png')]
    special_acc_nums = SPECIAL_ACCESSORIES.get(character_name, [])

    for filename in files_in_dir:
        body_match = body_pattern.match(filename)
        if body_match:
            groups[body_match.group(2)]['body'].append(filename)
            continue
        
        face_match = face_pattern.match(filename)
        if face_match:
            group_key, number_str = face_match.groups()
            number = int(number_str)
            
            # 【修改】修正後的檔案分類邏輯，更加嚴謹
            if special_acc_nums and number in special_acc_nums:
                groups[group_key]['special_accessories'].append(filename)
            elif BLUSH_SUFFIX_START <= number <= BLUSH_SUFFIX_END:
                groups[group_key]['blush'].append(filename)
            elif number >= ACCESSORY_SUFFIX_START:
                groups[group_key]['accessories'].append(filename)
            elif FACE_SUFFIX_START <= number <= FACE_SUFFIX_END:
                groups[group_key]['face'].append(filename)
            # 如果數字不屬於以上任何範圍，則會被忽略

    for group_key, parts in groups.items():
        if not parts['body'] or not parts['face']: continue
        
        final_blush_path = None
        if parts['blush']:
            best_blush_file = max(parts['blush'], key=lambda f: int(face_pattern.match(f).group(2)))
            final_blush_path = os.path.join(current_dir, best_blush_file)
        
        special_accessory_paths = [os.path.join(current_dir, f) for f in parts['special_accessories']]
        regular_accessory_paths = [os.path.join(current_dir, f) for f in parts['accessories']]

        for body_filename in parts['body']:
            body_path = os.path.join(current_dir, body_filename)
            body_coords = get_image_position(body_path)
            if not body_coords: continue

            for face_filename in parts['face']:
                face_path = os.path.join(current_dir, face_filename)
                output_dir = os.path.join(OUTPUT_ROOT, os.path.relpath(current_dir, INPUT_ROOT))
                ensure_dir(output_dir)
                
                job_args = (body_path, face_path, body_coords, final_blush_path, special_accessory_paths, regular_accessory_paths, output_dir)
                job_list.append(job_args)
    return job_list

def main():
    start_time = time.time()
    
    if not os.path.isdir(INPUT_ROOT):
        print(f"錯誤：找不到輸入資料夾 '{INPUT_ROOT}'。")
        return

    try:
        character_dirs = [d for d in os.listdir(INPUT_ROOT) if os.path.isdir(os.path.join(INPUT_ROOT, d))]
    except FileNotFoundError:
        print(f"錯誤：找不到輸入資料聞 '{INPUT_ROOT}'。")
        return

    all_jobs = []
    for character_name in character_dirs:
        print(f"\n=========================================")
        print(f"=== 開始分析角色：{character_name}")
        print(f"=========================================")
        character_path = os.path.join(INPUT_ROOT, character_name)
        for folder_name in PROCESSING_ORDER:
            current_dir = os.path.join(character_path, folder_name)
            if os.path.isdir(current_dir):
                jobs = prepare_jobs_from_directory(current_dir, character_name)
                all_jobs.extend(jobs)
    
    if not all_jobs:
        print("未找到任何需要處理的圖片組合。")
        return

    print(f"\n--- 分析完成，總共找到 {len(all_jobs)} 個基礎組合任務。開始使用 {MAX_WORKERS} 個處理程序進行合成 ---")

    with concurrent.futures.ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = list(tqdm.tqdm(executor.map(process_single_combination, all_jobs), total=len(all_jobs)))

    end_time = time.time()
    print("\n--- 所有任務處理完畢！ ---")
    print(f"總耗時：{end_time - start_time:.2f} 秒")

if __name__ == '__main__':
    main()