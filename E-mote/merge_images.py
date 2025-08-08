# process_pipeline.py (v6.0 - 視覺化腳本組裝引擎)

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
        print("提示：可安裝 'tqdm' 函式庫以顯示進度條 (pip install tqdm)")
        return iterable

# --- 佈局定義 ---
LAYOUTS = {
    '2v': [1, 1], '2h': [2], '3v': [1, 1, 1], '3h': [3], '4h': [2, 2], '4v': [1, 1, 1, 1],
    '5v': [1, 1, 1, 1, 1], '6g': [3, 3], '6h': [2, 2, 2], '8g': [2, 2, 2, 2], '9g': [3, 3, 3],
}
SUPPORTED_FORMATS = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff')
WILDCARD_FLAGS = ['--a', '--w', '--wildcard', '--all']

# ==============================================================================
# 核心函式庫 (部分重構)
# ==============================================================================

def find_first_image(directory):
    """尋找資料夾中的第一張圖片"""
    if not os.path.isdir(directory): return None
    for filename in sorted(os.listdir(directory)):
        if filename.lower().endswith(SUPPORTED_FORMATS):
            return os.path.join(directory, filename)
    return None

def find_image_by_name(directory, name):
    """在資料夾中尋找特定名稱的圖片"""
    if not os.path.isdir(directory): return None
    for filename in os.listdir(directory):
        if filename.lower() == name.lower():
            return os.path.join(directory, filename)
    return None
    
def chunk_list(data, sizes):
    """將一個列表根據指定的尺寸分割成多個子列表"""
    it = iter(data)
    return [list(islice(it, size)) for size in sizes]

def merge_image_set(image_paths, output_path, layout_structure):
    # ... (此函式無需改變，從 v5.0 複製過來即可)
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
    except Exception as e:
        print(f"  - 合併失敗 ({os.path.basename(output_path)}): {e}")
        return None


def crop_and_overwrite(image_path):
    # ... (此函式無需改變，從 v5.0 複製過來即可)
    try:
        with Image.open(image_path) as img:
            if img.mode != 'RGBA': img = img.convert('RGBA')
            bbox = img.getbbox()
            if bbox and bbox != (0, 0, img.width, img.height):
                cropped = img.crop(bbox)
                cropped.save(image_path, format='PNG')
                return f"成功裁剪: {os.path.basename(image_path)}"
            else:
                return f"無需裁剪: {os.path.basename(image_path)}"
    except Exception as e:
        return f"裁剪失敗 {os.path.basename(image_path)}: {e}"

# ==============================================================================
# 全新：自訂參數解析與任務生成引擎
# ==============================================================================

def parse_arguments(argv):
    """手動解析 sys.argv 來建構指令配方"""
    if len(argv) < 4: return None
    
    args = {}
    args['layout'] = argv[1]
    args['output_dir'] = argv[2]
    args['crop'] = '--crop' in argv
    
    # 提取核心的圖片來源參數
    source_args = [arg for arg in argv[3:] if arg != '--crop']
    
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
    """根據配方生成所有合併任務"""
    recipe = args['recipe']
    layout = args['layout']
    
    if layout not in LAYOUTS:
        print(f"錯誤: 未知的佈局 '{layout}'")
        return None
        
    layout_structure = LAYOUTS[layout]
    expected_n = sum(layout_structure)

    if len(recipe) != expected_n:
        print(f"錯誤: 佈局 '{layout}' 需要 {expected_n} 個圖片來源，但你提供了 {len(recipe)} 個。")
        return None

    # 1. 預先載入所有百搭圖的路徑
    wildcard_sources = {}
    for item in recipe:
        if item['type'] == 'wildcard':
            path = find_first_image(item['dir'])
            if not path:
                print(f"警告: 在百搭資料夾 '{item['dir']}' 中找不到任何圖片。")
                return None
            wildcard_sources[item['dir']] = path
    
    # 2. 找到主要驅動資料夾（第一個 normal 型別）
    primary_dir_info = next((item for item in recipe if item['type'] == 'normal'), None)
    if not primary_dir_info:
        print("錯誤: 配方中必須至少包含一個普通圖片資料夾作為主要驅動。")
        return None
        
    print(f"主要驅動資料夾: '{primary_dir_info['dir']}'")

    # 3. 遍歷主要驅動資料夾中的圖片，生成任務
    jobs = []
    primary_images = [p for p in sorted(os.listdir(primary_dir_info['dir'])) if p.lower().endswith(SUPPORTED_FORMATS)]
    
    for primary_image_name in primary_images:
        job_image_paths = [None] * expected_n
        is_job_valid = True
        
        for i, item in enumerate(recipe):
            if item['type'] == 'wildcard':
                job_image_paths[i] = wildcard_sources[item['dir']]
            
            elif item['type'] == 'normal':
                if item['dir'] == primary_dir_info['dir']:
                    job_image_paths[i] = os.path.join(item['dir'], primary_image_name)
                else: # 其他 normal 資料夾，需要尋找同名檔案
                    path = find_image_by_name(item['dir'], primary_image_name)
                    if not path:
                        # print(f"  - 警告: 在 '{item['dir']}' 中找不到名為 '{primary_image_name}' 的對應圖片，跳過此組合。")
                        is_job_valid = False
                        break
                    job_image_paths[i] = path
        
        if is_job_valid and all(job_image_paths):
            output_path = os.path.join(args['output_dir'], primary_image_name)
            jobs.append({'inputs': job_image_paths, 'output': output_path, 'layout': layout_structure})

    return jobs

# ==============================================================================
# 主流程控制
# ==============================================================================

def main():
    args = parse_arguments(sys.argv)
    if not args:
        # ... (此處可以印出詳細的使用說明)
        print("指令格式錯誤。範例: python process_pipeline.py <layout> <output> <sources...> [--crop]")
        return
        
    print("--- 步驟 1: 解析指令配方並生成任務列表 ---")
    os.makedirs(args['output_dir'], exist_ok=True)
    jobs = create_job_list(args)
    
    if not jobs:
        print("未能生成任何有效的合併任務，流程結束。")
        return
        
    print(f"成功生成 {len(jobs)} 個合併任務。")
    
    print("\n--- 步驟 2: 執行圖片合併 ---")
    successful_files = []
    for job in tqdm(jobs, desc="合併進度"):
        result_path = merge_image_set(job['inputs'], job['output'], job['layout'])
        if result_path:
            successful_files.append(result_path)
            
    if not successful_files:
        print("\n--- 合併階段未產生任何檔案，流程結束。 ---")
        return

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
