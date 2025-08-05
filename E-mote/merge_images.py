# process_pipeline.py (終極整合版 v4.0)

import os
import sys
from collections import defaultdict
from PIL import Image
from itertools import islice
import argparse
import concurrent.futures
from functools import partial

# 建議安裝 tqdm 以顯示進度條 (pip install tqdm)
try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, *args, **kwargs):
        print("提示：可安裝 'tqdm' 函式庫以顯示進度條 (pip install tqdm)")
        return iterable

# --- 佈局定義 (來自 v3.0) ---
LAYOUTS = {
    '2v': [1, 1], '2h': [2], '3v': [1, 1, 1], '3h': [3], '4-2x2': [2, 2],
    '5v': [1, 1, 1, 1, 1], '5h': [5], '6g-3x2': [3, 3], '6g-2x3': [2, 2, 2],
    '8-diamond': [1, 2, 2, 2, 1], '8-gallery': [3, 2, 3], '8-header': [1, 3, 3, 1],
    '9g-3x3': [3, 3, 3],
}
SUPPORTED_FORMATS = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff')

# ==============================================================================
# 核心函式庫 (合併自兩個腳本)
# ==============================================================================

def find_and_group_images(input_dirs):
    """掃描並分組圖片 (來自 merge_images.py)"""
    image_groups = defaultdict(list)
    for directory in input_dirs:
        if not os.path.isdir(directory): continue
        for filename in sorted(os.listdir(directory)):
            if filename.lower().endswith(SUPPORTED_FORMATS):
                image_groups[filename].append(os.path.join(directory, filename))
    return image_groups

def chunk_list(data, sizes):
    """分割列表 (來自 merge_images.py)"""
    it = iter(data)
    return [list(islice(it, size)) for size in sizes]

def merge_image_set(image_paths, output_path, layout_structure):
    """
    執行單一組圖片的合併。成功則返回輸出路徑，失敗則返回 None。
    (改寫自 merge_images.py)
    """
    try:
        images = [Image.open(p).convert("RGBA") for p in image_paths]
        image_rows = chunk_list(images, layout_structure)
        
        row_dimensions = []
        max_canvas_width = 0
        total_canvas_height = 0
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
        print(f"  - 合併失敗: {e}")
        return None

def crop_and_overwrite(image_path):
    """
    裁剪單一圖片的透明邊界並直接覆蓋儲存。
    (改寫自 crop_alpha.py)
    """
    try:
        with Image.open(image_path) as img:
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            bbox = img.getbbox()
            if bbox and bbox != (0, 0, img.width, img.height):
                cropped = img.crop(bbox)
                # 直接覆蓋原檔案
                cropped.save(image_path, format='PNG')
                return f"成功裁剪: {os.path.basename(image_path)}"
            else:
                return f"無需裁剪: {os.path.basename(image_path)}"
    except Exception as e:
        return f"裁剪失敗 {os.path.basename(image_path)}: {e}"

# ==============================================================================
# 主流程控制
# ==============================================================================

def main():
    """主函式，負責解析參數並協調合併與裁剪流程。"""
    parser = argparse.ArgumentParser(
        description="終極圖片處理管線：合併多個資料夾中的同名圖片，並可選擇性地進行透明邊界裁剪。",
        formatter_class=argparse.RawTextHelpFormatter # 保持換行格式
    )
    parser.add_argument("layout", choices=LAYOUTS.keys(), help="要使用的佈局指令。")
    parser.add_argument("output_dir", help="儲存最終成品的資料夾。")
    parser.add_argument("input_dirs", nargs='+', help="一或多個包含來源圖片的資料夾路徑。")
    parser.add_argument("--crop", action="store_true", help="啟用此旗標，可在合併後自動裁剪所有成品的透明邊界。")

    args = parser.parse_args()

    # --- 階段一：合併 ---
    print("--- 階段一：開始合併圖片 ---")
    os.makedirs(args.output_dir, exist_ok=True)
    image_groups = find_and_group_images(args.input_dirs)
    
    if not image_groups:
        print("在指定的來源資料夾中未找到任何可處理的圖片。")
        return

    layout_structure = LAYOUTS[args.layout]
    expected_n = sum(layout_structure)
    
    successful_merges = [] # 用於記錄成功合併的檔案路徑，以供裁剪階段使用
    
    for filename, paths in image_groups.items():
        if len(paths) == expected_n:
            print(f"正在處理 '{filename}'...")
            output_path = os.path.join(args.output_dir, filename)
            result_path = merge_image_set(paths, output_path, layout_structure)
            if result_path:
                print(f"  - 合併成功: {result_path}")
                successful_merges.append(result_path)
        else:
            print(f"跳過 '{filename}' (需要 {expected_n} 張，找到 {len(paths)} 張)")

    if not successful_merges:
        print("\n--- 合併階段未產生任何檔案，流程結束。 ---")
        return
        
    print(f"\n--- 合併階段完成，共生成 {len(successful_merges)} 個檔案。 ---")

    # --- 階段二：裁剪 (如果使用者指定) ---
    if args.crop:
        print("\n--- 階段二：開始多進程裁剪 ---")
        # 使用 ProcessPoolExecutor 進行平行處理
        with concurrent.futures.ProcessPoolExecutor() as executor:
            # 將需要裁剪的檔案路徑列表交給多進程處理
            results = list(tqdm(executor.map(crop_and_overwrite, successful_merges), total=len(successful_merges), desc="裁剪進度"))
        
        # (可選) 印出裁剪結果
        # print("\n裁剪結果摘要:")
        # for res in results:
        #     print(f"  - {res}")
        print("\n--- 裁剪階段完成 ---")
    else:
        print("\n未指定 --crop 旗標，跳過裁剪步驟。")

    print("\n所有任務完成！")

# 多進程程式碼的保護機制
if __name__ == '__main__':
    main()