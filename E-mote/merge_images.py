# process_pipeline.py (v12.2 - 旗標修正版)

import os
import sys
import re
from collections import defaultdict
from PIL import Image
from itertools import islice
import concurrent.futures

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, *args, **kwargs):
        return iterable

# --- 佈局與全域設定 (WILDCARD_FLAGS 已修正) ---
LAYOUTS = {
    '1x2': [1, 1], '2x1': [2], '1x3': [1, 1, 1], '3x1': [3], '2x2': [2, 2], '1x4': [1, 1, 1, 1],
    '1x5': [1, 1, 1, 1, 1], '3x2': [3, 3], '2x3': [2, 2, 2], '2x4': [2, 2, 2, 2], '3x3': [3, 3, 3],
}
SUPPORTED_FORMATS = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp')
# ----- 這裡是修正點 -----
WILDCARD_FLAGS = ['-a', '--a', '-w', '--w', '--wildcard', '--all']
# -------------------------
BATCH_FLAGS = ['-b', '--batch']

# ==============================================================================
# 詳細使用說明函式 (與 v12.1 相同)
# ==============================================================================
def print_detailed_usage():
    # ... (此函式不變)
    script_name = os.path.basename(sys.argv[0])
    print("=" * 80)
    print(f" 終極圖片處理管線 v12.2 - 詳細使用說明")
    print("=" * 80)
    print("\n【模式一：手動模式】")
    print(f"  用法: python {script_name} <layout> <output> <sources...> [flags...]")
    print("\n【模式二：批次模式】")
    print("  自動掃描並處理當前目錄下所有符合命名規則的專案。")
    print(f"  用法: python {script_name} -b [-a <pos>] [--crop] [--animated] [--format <ext>]")
    print("\n  >> 批次模式下的『智慧型百搭』功能 (-a <pos>) <<")
    print("  -a <pos>  : 指定百搭圖的位置列表 (例如: 3,4,5)。腳本會自動判斷類型：")
    print("    - 資料夾內僅 1 張圖:  視為【簡單百搭】，固定使用該圖。")
    print("    - 資料夾內 >1 張圖: 視為【條件式百搭】，根據檔名數字進行範圍匹配。")
    print("\n  >> 條件式百搭的檔名規則 <<")
    print("    - 主要圖片 (例如: char_0044.png)  -> 腳本自動提取【最後】的數字 (44)。")
    print("    - 百搭圖片 (例如: mood_31.png)    -> 腳本自動提取【最前】的數字 (31)。")
    print("    - 腳本會選用百搭數字 <= 主要數字 的那張最接近的百搭圖。")
    print("\n【通用旗標 (Flags)】")
    print("  -b, --batch   : 啟用批次處理模式。")
    print("  -a... <dir>  : 將路徑標記為『百搭圖』資料夾 (僅限手動模式)。")
    print("  --animated    : 啟用『動態圖合併模式』。")
    print("  --format <ext>: 強制指定輸出檔案的副檔名 (例如: gif)。")
    print("  --crop        : 在處理完成後，自動裁剪成品的透明邊界。")
    print("=" * 80)

# ==============================================================================
# 核心函式庫 (與 v12.1 相同)
# ==============================================================================
def extract_number(text, first=False):
    numbers = re.findall(r'\d+', text)
    if not numbers:
        return -1
    return int(numbers[0] if first else numbers[-1])

# ... (find_first_image, find_image_by_name, chunk_list, merge_image_set, crop_and_overwrite 等函式都與 v12.1 相同，此處省略以保持簡潔)
def find_first_image(directory):
    if not os.path.isdir(directory): return None
    for filename in sorted(os.listdir(directory)):
        if filename.lower().endswith(SUPPORTED_FORMATS):
            return os.path.join(directory, filename)
    return None
def find_image_by_name(directory, name):
    if not os.path.isdir(directory): return None
    for filename in os.listdir(directory):
        if filename.lower() == name.lower():
            return os.path.join(directory, filename)
    return None
def chunk_list(data, sizes):
    it = iter(data)
    return [list(islice(it, size)) for size in sizes]
def merge_image_set(image_paths, output_path, layout_structure, is_animated=False):
    if is_animated:
        opened_images = []
        try:
            opened_images = [Image.open(p) for p in image_paths]
            frame_counts = [getattr(img, 'n_frames', 1) for img in opened_images]
            min_frames = min(frame_counts)
            output_frames = []
            for frame_index in range(min_frames):
                current_input_frames = [img.seek(frame_index) or img.convert("RGBA") for img in opened_images]
                image_rows = chunk_list(current_input_frames, layout_structure)
                max_canvas_width, total_canvas_height = 0, 0
                row_dimensions = []
                for row in image_rows:
                    row_width = sum(img.width for img in row)
                    row_height = max(img.height for img in row)
                    row_dimensions.append({'width': row_width, 'height': row_height})
                    max_canvas_width = max(max_canvas_width, row_width)
                    total_canvas_height += row_height
                canvas = Image.new('RGBA', (max_canvas_width, total_canvas_height), (0, 0, 0, 0))
                current_y = 0
                for i, row in enumerate(image_rows):
                    row_dims = row_dimensions[i]
                    current_x = (max_canvas_width - row_dims['width']) // 2
                    for img_frame in row:
                        paste_y = current_y + (row_dims['height'] - img_frame.height) // 2
                        canvas.paste(img_frame, (current_x, paste_y), img_frame)
                        current_x += img_frame.width
                    current_y += row_dims['height']
                output_frames.append(canvas)
            if output_frames:
                duration = opened_images[0].info.get('duration', 100)
                output_frames[0].save(output_path, save_all=True, append_images=output_frames[1:], duration=duration, loop=0, disposal=2)
                return output_path
            return None
        except Exception as e: return None
        finally:
            for img in opened_images: img.close()
    else:
        try:
            images = [Image.open(p).convert("RGBA") for p in image_paths]
            image_rows = chunk_list(images, layout_structure)
            row_dimensions = []
            max_canvas_width, total_canvas_height = 0, 0
            for row in image_rows:
                row_width = sum(img.width for img in row)
                row_height = max(img.height for img in row)
                row_dimensions.append({'width': row_width, 'height': row_height})
                max_canvas_width = max(max_canvas_width, row_width)
                total_canvas_height += row_height
            canvas = Image.new('RGBA', (max_canvas_width, total_canvas_height), (0, 0, 0, 0))
            current_y = 0
            for i, row in enumerate(image_rows):
                row_dims = row_dimensions[i]
                current_x = (max_canvas_width - row_dims['width']) // 2
                for img in row:
                    paste_y = current_y + (row_dims['height'] - img.height) // 2
                    canvas.paste(img, (current_x, paste_y), img)
                    current_x += img.width
                current_y += row_dims['height']
            canvas.save(output_path)
            for img in images: img.close()
            return output_path
        except Exception as e: return None
def crop_and_overwrite(image_path):
    try:
        with Image.open(image_path) as img:
            if img.mode != 'RGBA': img = img.convert('RGBA')
            bbox = img.getbbox()
            if bbox and bbox != (0, 0, img.width, img.height):
                is_animated = getattr(img, 'is_animated', False)
                if is_animated:
                    frames = []
                    for i in range(img.n_frames):
                        img.seek(i)
                        frames.append(img.crop(bbox))
                    frames[0].save(image_path, save_all=True, append_images=frames[1:], loop=0, duration=img.info.get('duration', 100), disposal=2)
                else:
                    cropped = img.crop(bbox)
                    cropped.save(image_path, format='PNG')
                return f"成功裁剪: {os.path.basename(image_path)}"
            else:
                return f"無需裁剪: {os.path.basename(image_path)}"
    except Exception as e: return None


# ==============================================================================
# 核心處理引擎 (與 v12.1 相同，我們不再需要偵錯訊息)
# ==============================================================================
def create_job_list(recipe, layout, output_dir, file_format):
    # ... (此函式不變)
    layout_structure = LAYOUTS[layout]
    expected_n = sum(layout_structure)
    if len(recipe) != expected_n:
        print(f"錯誤: 佈局 '{layout}' 需要 {expected_n} 個來源，但配方提供了 {len(recipe)} 個。")
        return None
    wildcard_sources = {}
    for item in recipe:
        if item['type'].startswith('wildcard'):
            if item['type'] == 'wildcard_simple':
                wildcard_sources[item['dir']] = find_first_image(item['dir'])
            elif item['type'] == 'wildcard_conditional':
                conditional_list = []
                for fname in sorted(os.listdir(item['dir'])):
                    if fname.lower().endswith(SUPPORTED_FORMATS):
                        start_index = extract_number(fname, first=True)
                        if start_index != -1:
                            conditional_list.append((start_index, os.path.join(item['dir'], fname)))
                wildcard_sources[item['dir']] = sorted(conditional_list)
    primary_dir_info = next((item for item in recipe if item['type'] == 'normal'), None)
    if not primary_dir_info: print("錯誤: 配方中必須至少包含一個普通資料夾。"); return None
    print(f"主要驅動資料夾: '{primary_dir_info['dir']}'")
    jobs = []
    primary_images = [p for p in sorted(os.listdir(primary_dir_info['dir'])) if p.lower().endswith(SUPPORTED_FORMATS)]
    for primary_image_name in primary_images:
        base_name, _ = os.path.splitext(primary_image_name)
        output_filename = f"{base_name}.{file_format}" if file_format else primary_image_name
        output_path = os.path.join(output_dir, output_filename)
        job_image_paths = [None] * expected_n
        is_job_valid = True
        primary_index = extract_number(base_name)
        if primary_index == -1: continue
        for i, item in enumerate(recipe):
            if item['type'] == 'wildcard_simple':
                job_image_paths[i] = wildcard_sources[item['dir']]
            elif item['type'] == 'wildcard_conditional':
                correct_wildcard = None
                for start_index, path in wildcard_sources[item['dir']]:
                    if primary_index >= start_index:
                        correct_wildcard = path
                    else:
                        break
                if correct_wildcard: job_image_paths[i] = correct_wildcard
                else: is_job_valid = False; break
            elif item['type'] == 'normal':
                path = os.path.join(item['dir'], primary_image_name) if item['dir'] == primary_dir_info['dir'] else find_image_by_name(item['dir'], primary_image_name)
                if not path or not os.path.exists(path): is_job_valid = False; break
                job_image_paths[i] = path
        if is_job_valid and all(job_image_paths):
            jobs.append({'inputs': job_image_paths, 'output': output_path, 'layout': layout_structure})
    return jobs

def execute_pipeline(jobs, is_animated, should_crop):
    # ... (此函式不變)
    if not jobs:
        print("未能生成任何有效的合併任務。")
        return
    print(f"成功生成 {len(jobs)} 個合併任務。")
    print("\n--- 步驟 2: 執行圖片合併 ---")
    successful_files = [p for job in tqdm(jobs, desc="合併進度") if (p := merge_image_set(job['inputs'], job['output'], job['layout'], is_animated=is_animated))]
    if not successful_files:
        print("\n--- 合併階段未產生任何檔案。 ---")
        return
    print(f"\n--- 合併階段完成，共生成 {len(successful_files)} 個檔案。 ---")
    if should_crop:
        print("\n--- 步驟 3: 執行多進程裁剪 ---")
        with concurrent.futures.ProcessPoolExecutor() as executor:
            list(tqdm(executor.map(crop_and_overwrite, successful_files), total=len(successful_files), desc="裁剪進度"))
        print("\n--- 裁剪階段完成 ---")

# ==============================================================================
# 模式切換與主流程控制 (與 v12.1 相同)
# ==============================================================================
def run_manual_mode(argv):
    # ... (此函式不變)
    print("手動模式需要更詳細的指令，請參考說明。")
    print_detailed_usage()

def run_batch_mode(argv):
    # ... (此函式不變)
    print("--- 批次處理模式已啟動 ---")
    is_animated = '--animated' in argv
    should_crop = '--crop' in argv
    file_format = next((argv[i+1] for i, arg in enumerate(argv) if arg == '--format' and i + 1 < len(argv)), None)
    wildcard_positions_str = next((argv[i+1] for i, arg in enumerate(argv) if arg in WILDCARD_FLAGS and i + 1 < len(argv)), None)
    wildcard_indices = set()
    if wildcard_positions_str:
        try:
            wildcard_indices = {int(p) - 1 for p in wildcard_positions_str.split(',')}
            print(f"已啟用位置百搭，指定位置: {wildcard_positions_str}")
        except ValueError:
            print(f"錯誤: 百搭位置列表 '{wildcard_positions_str}' 格式錯誤。"); return
    projects_found = 0
    for dir_name in sorted(os.listdir('.')):
        if not os.path.isdir(dir_name) or dir_name == 'output': continue
        if '_' not in dir_name: continue
        name_part, _, layout = dir_name.rpartition('_')
        if layout in LAYOUTS:
            projects_found += 1
            print(f"\n{'='*20} 正在處理專案: {dir_name} {'='*20}")
            project_dir = dir_name
            output_dir = os.path.join('output', project_dir)
            os.makedirs(output_dir, exist_ok=True)
            source_dirs = sorted([os.path.join(project_dir, d) for d in os.listdir(project_dir) if os.path.isdir(os.path.join(project_dir, d))])
            if not source_dirs:
                print(f"警告: 專案 '{project_dir}' 中未找到任何來源子資料夾。"); continue
            recipe = []
            for i, source_dir in enumerate(source_dirs):
                if i in wildcard_indices:
                    num_images = len([f for f in os.listdir(source_dir) if f.lower().endswith(SUPPORTED_FORMATS)])
                    if num_images > 1:
                        recipe.append({'type': 'wildcard_conditional', 'dir': source_dir})
                        print(f"  - 位置 {i+1} ('{os.path.basename(source_dir)}') -> 偵測到 >1 張圖，設為【條件式百搭】")
                    else:
                        recipe.append({'type': 'wildcard_simple', 'dir': source_dir})
                        print(f"  - 位置 {i+1} ('{os.path.basename(source_dir)}') -> 偵測到 <=1 張圖，設為【簡單百搭】")
                else:
                    recipe.append({'type': 'normal', 'dir': source_dir})
            print("\n--- 步驟 1: 生成任務列表 ---")
            jobs = create_job_list(recipe, layout, output_dir, file_format)
            execute_pipeline(jobs, is_animated, should_crop)
    if projects_found == 0:
        print("未在當前目錄下找到任何符合 '專案名_佈局' 格式的資料夾。")

def main():
    if any(arg in BATCH_FLAGS for arg in sys.argv):
        run_batch_mode(sys.argv)
    elif len(sys.argv) > 1:
        run_manual_mode(sys.argv)
    else:
        print_detailed_usage()

if __name__ == '__main__':
    main()