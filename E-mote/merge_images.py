# process_pipeline.py (v8.0 - 新增輸出格式控制)

import os
import sys
from collections import defaultdict
from PIL import Image
from itertools import islice
import argparse
import concurrent.futures

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, *args, **kwargs):
        print("提示：可安裝 'tqdm' 函式庫以顯示進度條 (pip install tqdm)")
        return iterable

# ... (佈局定義、輔助函式等與 v7.0 完全相同，此處省略以節省篇幅)
LAYOUTS = {
    '2v': [1, 1], '2h': [2], '3v': [1, 1, 1], '3h': [3], '4h': [2, 2], '4v': [1, 1, 1, 1],
    '5v': [1, 1, 1, 1, 1], '6g': [3, 3], '6h': [2, 2, 2], '8g': [2, 2, 2, 2], '9g': [3, 3, 3],
}
SUPPORTED_FORMATS = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp')
WILDCARD_FLAGS = ['--a', '--w', '--wildcard', '--all']

def print_detailed_usage():
    """印出詳細的程式使用說明"""
    script_name = os.path.basename(sys.argv[0])
    
    print("=" * 80)
    print(f" 終極圖片處理管線 v9.0 - 詳細使用說明")
    print("=" * 80)
    print("這是一個強大的圖片合併工具，支援同名合併、百搭圖合併及動態圖處理。")

    print("\n【1. 基本用法】")
    print(f"  python {script_name} <layout> <output_dir> <sources...> [flags...]")

    print("\n【2. 必要參數】")
    print("  <layout>      : 指定合併的佈局。可用的佈局指令如下：")
    # 動態從 LAYOUTS 字典生成說明
    for key, value in LAYOUTS.items():
        print(f"    - {key:<10}: {str(value):<18} (共 {sum(value)} 張圖)")
        
    print("  <output_dir>  : 儲存最終成品的資料夾。")
    print("  <sources...>  : 一或多個來源圖片資料夾。其順序決定了在佈局中的位置。")

    print("\n【3. 可選旗標 (Flags)】")
    print("  --a, --w, --wildcard <dir>")
    print("                : 將下一個路徑 <dir> 標記為『百搭圖』資料夾。")
    print("                  腳本會選用該資料夾中的第一張圖片作為此位置的固定圖片。")
    print("\n  --animated")
    print("                : 啟用『動態圖合併模式』。腳本會逐偵合併，生成動態圖 (gif/webp)。")
    print("                  (同步規則：以最短偵數為準；播放速度以第一張圖為準)")
    print("\n  --format <ext>")
    print("                : 強制指定輸出檔案的副檔名 (例如: gif, webp, png)，不含點。")
    print("\n  --crop")
    print("                : 在所有處理完成後，自動裁剪成品的透明邊界。")

    print("\n【4. 使用範例】")
    print("-" * 20 + " 範例 A: 標準同名合併 " + "-" * 20)
    print("# 將 9 個資料夾中的同名圖片合併為 3x3 九宮格")
    print(f"  python {script_name} 9g ./output_grid ./dir1 ./dir2 ./dir3 ./dir4 ./dir5 ./dir6 ./dir7 ./dir8 ./dir9")
    
    print("\n" + "-" * 20 + " 範例 B: 位置指定的百搭圖合併 " + "-" * 20)
    print("# 佈局為6張圖，第1,2位置為普通圖，第3,4,5,6位置使用百搭圖")
    print(f"  python {script_name} 6h ./output_wildcard ./body ./face --a ./frame --a ./logo --a ./watermark --a ./effect")
    
    print("\n" + "-" * 20 + " 範例 C: 動態圖合併 + 格式轉換 " + "-" * 20)
    print("# 將一個動態 logo (百搭) 與一個靜態角色合併，輸出為 gif 格式並裁剪")
    print(f"  python {script_name} 2v ./output_gif --a ./anim_logo_folder ./static_char_folder --animated --format gif --crop")
    
    print("\n" + "=" * 80)

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
        except Exception as e:
            print(f"  - 動態合併失敗 ({os.path.basename(output_path)}): {e}")
            return None
        finally:
            for img in opened_images: img.close()
    else: # Static merge logic
        try:
            images = [Image.open(p).convert("RGBA") for p in image_paths]
            # ... (靜態合併邏輯與v7完全相同，此處省略)
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
        except Exception as e:
            print(f"  - 靜態合併失敗 ({os.path.basename(output_path)}): {e}")
            return None

def crop_and_overwrite(image_path):
    # ... (此函式無需改變)
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
    except Exception as e:
        return f"裁剪失敗 {os.path.basename(image_path)}: {e}"

# ==============================================================================
# 主要變更點
# ==============================================================================

def parse_arguments(argv):
    """手動解析 sys.argv，新增對 --format 的支援"""
    if len(argv) < 4: return None
    
    args = {}
    args['layout'] = argv[1]
    args['output_dir'] = argv[2]
    
    # 使用迴圈來尋找 --format 和它的值
    format_val = None
    temp_argv = list(argv) # 複製一份以安全操作
    for i, arg in enumerate(temp_argv):
        if arg == '--format':
            if i + 1 < len(temp_argv):
                format_val = temp_argv[i+1]
                # 從參數列表中移除 --format 和它的值，以免干擾後續處理
                argv.remove(arg)
                argv.remove(format_val)
                break
    args['format'] = format_val

    args['animated'] = '--animated' in argv
    args['crop'] = '--crop' in argv
    
    source_args = [arg for arg in argv[3:] if arg not in ['--crop', '--animated']]
    
    recipe = []
    is_next_wildcard = False
    for arg in source_args:
        if arg in WILDCARD_FLAGS:
            is_next_wildcard = True
            continue
        if is_next_wildcard:
            recipe.append({'type': 'wildcard', 'dir': arg})
            is_next_wildcard = False
        else:
            recipe.append({'type': 'normal', 'dir': arg})
    args['recipe'] = recipe
    return args

def create_job_list(args):
    """根據配方生成所有合併任務，並處理 --format"""
    recipe = args['recipe']
    # ... (前面的驗證邏輯不變，此處省略)
    layout = args['layout']
    if layout not in LAYOUTS:
        print(f"錯誤: 未知的佈局 '{layout}'"); return None
    layout_structure = LAYOUTS[layout]
    expected_n = sum(layout_structure)
    if len(recipe) != expected_n:
        print(f"錯誤: 佈局 '{layout}' 需要 {expected_n} 個圖片來源，但你提供了 {len(recipe)} 個。"); return None
    wildcard_sources = {}
    for item in recipe:
        if item['type'] == 'wildcard':
            path = find_first_image(item['dir'])
            if not path:
                print(f"警告: 在百搭資料夾 '{item['dir']}' 中找不到任何圖片。"); return None
            wildcard_sources[item['dir']] = path
    primary_dir_info = next((item for item in recipe if item['type'] == 'normal'), None)
    if not primary_dir_info:
        print("錯誤: 配方中必須至少包含一個普通圖片資料夾作為主要驅動。"); return None

    print(f"主要驅動資料夾: '{primary_dir_info['dir']}'")
    jobs = []
    primary_images = [p for p in sorted(os.listdir(primary_dir_info['dir'])) if p.lower().endswith(SUPPORTED_FORMATS)]
    
    for primary_image_name in primary_images:
        # --- 構造輸出檔名的邏輯變更點 ---
        if args['format']:
            # 如果指定了 --format，則替換副檔名
            base_name, _ = os.path.splitext(primary_image_name)
            output_filename = f"{base_name}.{args['format']}"
        else:
            # 否則，使用原始檔名
            output_filename = primary_image_name
        
        output_path = os.path.join(args['output_dir'], output_filename)
        # --- 變更結束 ---

        job_image_paths = [None] * expected_n
        is_job_valid = True
        for i, item in enumerate(recipe):
            if item['type'] == 'wildcard':
                job_image_paths[i] = wildcard_sources[item['dir']]
            elif item['type'] == 'normal':
                if item['dir'] == primary_dir_info['dir']:
                    job_image_paths[i] = os.path.join(item['dir'], primary_image_name)
                else:
                    path = find_image_by_name(item['dir'], primary_image_name)
                    if not path:
                        is_job_valid = False
                        break
                    job_image_paths[i] = path
        
        if is_job_valid and all(job_image_paths):
            jobs.append({'inputs': job_image_paths, 'output': output_path, 'layout': layout_structure})

    return jobs

def main():
    args = parse_arguments(sys.argv)
    
    # --- 這裡是要修改的地方 ---
    if not args:
        print_detailed_usage()  # 呼叫新的詳細說明函式
        return
    print("--- 步驟 1: 解析指令配方並生成任務列表 ---")
    os.makedirs(args['output_dir'], exist_ok=True)
    jobs = create_job_list(args)
    if not jobs:
        print("未能生成任何有效的合併任務，流程結束。"); return
    print(f"成功生成 {len(jobs)} 個合併任務。")
    print("\n--- 步驟 2: 執行圖片合併 ---")
    successful_files = []
    for job in tqdm(jobs, desc="合併進度"):
        result_path = merge_image_set(job['inputs'], job['output'], job['layout'], is_animated=args['animated'])
        if result_path: successful_files.append(result_path)
    if not successful_files:
        print("\n--- 合併階段未產生任何檔案，流程結束。 ---"); return
    print(f"\n--- 合併階段完成，共生成 {len(successful_files)} 個檔案。 ---")
    if args['crop']:
        print("\n--- 步驟 3: 執行多進程裁剪 ---")
        with concurrent.futures.ProcessPoolExecutor() as executor:
            list(tqdm(executor.map(crop_and_overwrite, successful_files), total=len(successful_files), desc="裁剪進度"))
        print("\n--- 裁剪階段完成 ---")
    else:
        print("\n未指定 --crop 旗標，跳過裁剪步驟。")
    print("\n所有任務完成！")


if __name__ == '__main__':
    main()