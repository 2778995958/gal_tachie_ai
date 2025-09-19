# process_pipeline.py (v11.0 - 批次模式支援位置百搭)

import os
import sys
from collections import defaultdict
from PIL import Image
from itertools import islice
import concurrent.futures

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, *args, **kwargs):
        return iterable

# ... (LAYOUTS, SUPPORTED_FORMATS, FLAGS 等定義與 v10.0 相同)
LAYOUTS = {
    '1x2': [1, 1], '2x1': [2], '1x3': [1, 1, 1], '3x1': [3], '2x2': [2, 2], '1x4': [1, 1, 1, 1],
    '1x5': [1, 1, 1, 1, 1], '3x2': [3, 3], '2x3': [2, 2, 2], '2x4': [2, 2, 2, 2], '3x3': [3, 3, 3],
}
SUPPORTED_FORMATS = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp')
WILDCARD_FLAGS = ['--a', '--w', '--wildcard', '--all']
BATCH_FLAGS = ['-b', '--batch']

# ==============================================================================
# 詳細使用說明函式 (已更新)
# ==============================================================================
def print_detailed_usage():
    script_name = os.path.basename(sys.argv[0])
    print("=" * 80)
    print(f" 終極圖片處理管線 v11.0 - 詳細使用說明")
    print("=" * 80)
    print("\n【模式一：手動模式】")
    # ... (手動模式說明不變)
    print(f"  用法: python {script_name} <layout> <output> <sources...> [flags...]")
    print("\n【模式二：批次模式】")
    print("  自動掃描並處理當前目錄下所有符合命名規則的專案。")
    print(f"  用法: python {script_name} -b [-a <pos>] [--crop] [--animated] [--format <ext>]")
    print("  命名規則: '專案名_佈局指令' (例如: myProject_3x2)。")
    print("  -a <pos>  : (批次模式專用) 指定百搭圖的位置。")
    print("              <pos> 是一個用逗號分隔的數字列表 (例如: 3,4,5)。")
    # ... (其餘說明與 v10.0 類似，此處省略)
    print("\n【通用旗標 (Flags)】")
    print("  -b, --batch   : 啟用批次處理模式。")
    print("  --a... <dir>  : 將路徑標記為『百搭圖』資料夾 (僅限手動模式)。")
    print("  --animated    : 啟用『動態圖合併模式』。")
    print("  --format <ext>: 強制指定輸出檔案的副檔名 (例如: gif)。")
    print("  --crop        : 在處理完成後，自動裁剪成品的透明邊界。")
    print("=" * 80)

# ==============================================================================
# 核心函式庫 (與v10.0相同)
# ==============================================================================
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

# ... (merge_image_set 和 crop_and_overwrite 函式與 v10.0 完全相同，此處省略)
def merge_image_set(image_paths, output_path, layout_structure, is_animated=False):
    # (此函式與 v8.0 完全相同)
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
    # (此函式與 v8.0 完全相同)
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
# 核心處理引擎 (與v10.0相同)
# ==============================================================================
def create_job_list(recipe, layout, output_dir, file_format):
    # (此函式與 v10.0 完全相同)
    layout_structure = LAYOUTS[layout]
    expected_n = sum(layout_structure)
    if len(recipe) != expected_n:
        print(f"錯誤: 佈局 '{layout}' 需要 {expected_n} 個來源，但配方提供了 {len(recipe)} 個。")
        return None
    wildcard_sources = {item['dir']: find_first_image(item['dir']) for item in recipe if item['type'] == 'wildcard'}
    primary_dir_info = next((item for item in recipe if item['type'] == 'normal'), None)
    if not primary_dir_info:
        print("錯誤: 配方中必須至少包含一個普通資料夾。")
        return None
    print(f"主要驅動資料夾: '{primary_dir_info['dir']}'")
    jobs = []
    primary_images = [p for p in sorted(os.listdir(primary_dir_info['dir'])) if p.lower().endswith(SUPPORTED_FORMATS)]
    for primary_image_name in primary_images:
        base_name, _ = os.path.splitext(primary_image_name)
        output_filename = f"{base_name}.{file_format}" if file_format else primary_image_name
        output_path = os.path.join(output_dir, output_filename)
        job_image_paths = [None] * expected_n
        is_job_valid = True
        for i, item in enumerate(recipe):
            if item['type'] == 'wildcard':
                job_image_paths[i] = wildcard_sources.get(item['dir'])
            elif item['type'] == 'normal':
                path = os.path.join(item['dir'], primary_image_name) if item['dir'] == primary_dir_info['dir'] else find_image_by_name(item['dir'], primary_image_name)
                if not path or not os.path.exists(path):
                    is_job_valid = False
                    break
                job_image_paths[i] = path
        if is_job_valid and all(job_image_paths):
            jobs.append({'inputs': job_image_paths, 'output': output_path, 'layout': layout_structure})
    return jobs

def execute_pipeline(jobs, is_animated, should_crop):
    # (此函式與 v10.0 完全相同)
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
# 模式切換與主流程控制 (run_batch_mode 已升級)
# ==============================================================================

def run_manual_mode(argv):
    # (此函式與 v10.0 完全相同)
    args = {} 
    if len(argv) < 4: print_detailed_usage(); return
    args['layout'] = argv[1]
    args['output_dir'] = argv[2]
    format_val = None
    temp_argv = list(argv)
    for i, arg in enumerate(temp_argv):
        if arg == '--format':
            if i + 1 < len(temp_argv):
                format_val = temp_argv[i+1]
                argv.remove(arg); argv.remove(format_val)
                break
    args['format'] = format_val
    args['animated'] = '--animated' in argv
    args['crop'] = '--crop' in argv
    source_args = [arg for arg in argv[3:] if arg not in ['--crop', '--animated']]
    recipe = []
    is_next_wildcard = False
    for arg in source_args:
        if arg in WILDCARD_FLAGS:
            is_next_wildcard = True; continue
        recipe.append({'type': 'wildcard' if is_next_wildcard else 'normal', 'dir': arg})
        is_next_wildcard = False
    print("--- 步驟 1: 解析手動指令配方 ---")
    os.makedirs(args['output_dir'], exist_ok=True)
    jobs = create_job_list(recipe, args['layout'], args['output_dir'], args['format'])
    execute_pipeline(jobs, args['animated'], args['crop'])

def run_batch_mode(argv):
    """批次模式執行流程 (支援 -a 位置百搭)"""
    print("--- 批次處理模式已啟動 ---")
    # 提取通用旗標
    is_animated = '--animated' in argv
    should_crop = '--crop' in argv
    file_format = None
    wildcard_positions_str = None
    
    # 手動解析旗標，因為批次模式不使用固定位置參數
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == '--format':
            if i + 1 < len(argv):
                file_format = argv[i+1]
                i += 1 # 跳過值
        elif arg in ['-a', '--w', '--wildcard', '--all']: # 我們的目標
            if i + 1 < len(argv):
                wildcard_positions_str = argv[i+1]
                i += 1
        i += 1

    wildcard_indices = set()
    if wildcard_positions_str:
        try:
            # 將 1,2,3 轉換為 0-based 索引 {0, 1, 2}
            wildcard_indices = {int(p) - 1 for p in wildcard_positions_str.split(',')}
            print(f"已啟用位置百搭，指定位置: {wildcard_positions_str}")
        except ValueError:
            print(f"錯誤: 百搭位置列表 '{wildcard_positions_str}' 格式錯誤，應為用逗號分隔的數字。")
            return

    # 掃描當前目錄尋找專案資料夾
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
                print(f"警告: 專案 '{project_dir}' 中未找到任何來源子資料夾，已跳過。")
                continue
                
            # --- 根據 wildcard_indices 動態生成配方 ---
            recipe = []
            for i, source_dir in enumerate(source_dirs):
                if i in wildcard_indices:
                    recipe.append({'type': 'wildcard', 'dir': source_dir})
                    print(f"  - 位置 {i+1} ('{os.path.basename(source_dir)}') 設定為 百搭模式")
                else:
                    recipe.append({'type': 'normal', 'dir': source_dir})
            
            print("--- 步驟 1: 生成任務列表 ---")
            jobs = create_job_list(recipe, layout, output_dir, file_format)
            execute_pipeline(jobs, is_animated, should_crop)

    if projects_found == 0:
        print("未在當前目錄下找到任何符合 '專案名_佈局' 格式的資料夾。")

def main():
    """根據參數決定執行手動模式或批次模式"""
    if any(arg in BATCH_FLAGS for arg in sys.argv):
        run_batch_mode(sys.argv)
    elif len(sys.argv) > 1:
        run_manual_mode(sys.argv)
    else:
        print_detailed_usage()

if __name__ == '__main__':
    main()