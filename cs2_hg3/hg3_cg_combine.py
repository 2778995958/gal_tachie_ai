import pandas as pd
import numpy as np
from PIL import Image
import os
import re
import glob
import shutil

# --- 步驟 1: 專業級合成函式 (未變更) ---
def composite_high_quality(background_img, foreground_img, position):
    """
    採用專業級「預乘/還原 Alpha」工作流程，執行高精度圖片合成。
    """
    base_np = np.array(background_img, dtype=np.float64) / 255.0
    part_np = np.array(foreground_img, dtype=np.float64) / 255.0
    fg_layer = np.zeros_like(base_np)
    
    dx, dy = position
    part_h, part_w = part_np.shape[:2]
    base_h, base_w = base_np.shape[:2]

    x1_canvas, y1_canvas = max(dx, 0), max(dy, 0)
    x2_canvas, y2_canvas = min(dx + part_w, base_w), min(dy + part_h, base_h)
    
    x1_part, y1_part = x1_canvas - dx, y1_canvas - dy
    x2_part, y2_part = x2_canvas - dx, y2_canvas - dy
    
    if x1_canvas < x2_canvas and y1_canvas < y2_canvas:
        fg_layer[y1_canvas:y2_canvas, x1_canvas:x2_canvas] = part_np[y1_part:y2_part, x1_part:x2_part]

    bg_a = base_np[:, :, 3:4]
    fg_a = fg_layer[:, :, 3:4]
    
    bg_rgb_prem = base_np[:, :, :3] * bg_a
    fg_rgb_prem = fg_layer[:, :, :3] * fg_a

    out_rgb_prem = fg_rgb_prem + bg_rgb_prem * (1.0 - fg_a)
    out_a = fg_a + bg_a * (1.0 - fg_a)

    out_rgb = np.zeros_like(out_rgb_prem)
    mask = out_a > 1e-6
    np.divide(out_rgb_prem, out_a, where=mask, out=out_rgb)

    final_np_float = np.concatenate([out_rgb, out_a], axis=2)
    final_np_uint8 = (np.clip(final_np_float, 0.0, 1.0) * 255).round().astype(np.uint8)

    return Image.fromarray(final_np_uint8, 'RGBA')

# --- 步驟 2: 建立資料夾和路徑 (未變更) ---
PNG_DIR = 'png'
OUTPUT_DIR = 'output'
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- 步驟 3: 智慧型路徑選擇函式 ---
def get_priority_paths(part_name):
    """
    檢查是否存在 _l 版本的檔案，如果存在則優先回傳其路徑。
    返回一個元組: (要使用的PNG路徑, 要使用的HG3座標檔名)
    """
    large_png_path = os.path.join(PNG_DIR, f"{part_name}_l.png")
    if os.path.exists(large_png_path):
        return (large_png_path, f"{part_name}_l.hg3")
    
    standard_png_path = os.path.join(PNG_DIR, f"{part_name}.png")
    return (standard_png_path, f"{part_name}.hg3")

# --- 步驟 4: **完全修正**的檔名解析函式 ---
def get_parts_from_string(frame_string):
    """
    穩健地解析各種類型的字串，並根據規則進行補零。
    """
    cleaned_string = str(frame_string).replace('"', '')
    parts = cleaned_string.split(',')

    if len(parts) == 1:
        return [parts[0]]

    built_parts = []
    base_prefix = parts[0]
    
    for i, part_suffix in enumerate(parts[1:]):
        padding = "0" * i
        built_parts.append(f"{base_prefix}_{padding}{part_suffix}")
        
    return built_parts

# --- 主要流程 ---
try:
    print("正在讀取 hg3_coordinates.txt...")
    coords_df = pd.read_csv('hg3_coordinates.txt', sep='\t')
    coords_df.set_index('FileName', inplace=True)
    # **修正：將索引全部轉為小寫，以忽略大小寫**
    coords_df.index = coords_df.index.str.lower()
    print("座標資料讀取成功。")
except FileNotFoundError as e:
    print(f"致命錯誤：找不到座標檔 - {e.filename}。程式無法繼續。")
    exit()

all_csv_files = glob.glob('*.csv')
if not all_csv_files:
    print("錯誤：在當前目錄下找不到任何 .csv 檔案。")
    exit()

print(f"找到 {len(all_csv_files)} 個CSV檔案: {all_csv_files}")

# --- 步驟 5: **全新**的主迴圈，整合所有功能 ---
for csv_file in all_csv_files:
    print(f"\n{'='*20}\n正在處理檔案: {csv_file}\n{'='*20}")
    try:
        cg_df = pd.read_csv(csv_file)
    except Exception as e:
        print(f"  -> 讀取 {csv_file} 失敗，錯誤: {e}。跳過此檔案。")
        continue

    for index, row in cg_df.iterrows():
        try:
            entry_name = row['entry_name']
            subentry_index = row['subentry_index']
            frame_str = row['frame_names_cleaned']
        except KeyError as e:
            print(f"  -> {csv_file} 第 {index} 行缺少必要的欄位 {e}，已跳過。")
            continue
        
        output_filename = f"{entry_name}_{subentry_index}.png"
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        
        # **新功能：如果輸出檔案已存在，則跳過**
        if os.path.exists(output_path):
            print(f"\n正在處理第 {index} 行 -> 輸出檔案: {output_filename}")
            print(f"  -> 檔案已存在，跳過。")
            continue
            
        print(f"\n正在處理第 {index} 行 -> 輸出檔案: {output_filename}")

        try:
            all_parts = get_parts_from_string(frame_str)
            if not all_parts:
                print(f"  -> 警告：無法從 '{frame_str}' 解析出任何圖片，已跳過。")
                continue
            
            # **最佳化：單一圖片直接複製**
            if len(all_parts) == 1:
                part_name = all_parts[0]
                source_png_path, _ = get_priority_paths(part_name)
                
                if os.path.exists(source_png_path):
                    shutil.copy(source_png_path, output_path)
                    print(f"  -> 偵測到單一圖片，已直接複製 '{os.path.basename(source_png_path)}'。")
                    print(f"  -> ✅ 成功儲存至 {output_path}")
                else:
                    print(f"  -> ❌ 錯誤：找不到來源檔案 '{os.path.basename(source_png_path)}'。")
                continue

            # **合成流程**
            base_name = all_parts[0]
            _, base_hg3_key = get_priority_paths(base_name)
            
            print(f"  -> 偵測到複雜模式。使用 '{base_hg3_key}' (忽略大小寫) 作為基底。")
            base_coords = coords_df.loc[base_hg3_key.lower()]
            base_x = int(base_coords['OffsetX'])
            base_y = int(base_coords['OffsetY'])

            canvas_width = int(base_coords['CanvasWidth'])
            canvas_height = int(base_coords['CanvasHeight'])
            final_image = Image.new('RGBA', (canvas_width, canvas_height), (0, 0, 0, 0))
            print(f"  -> 建立畫布，尺寸: {canvas_width}x{canvas_height}")

            for part_name in all_parts:
                part_png_path, part_hg3_key = get_priority_paths(part_name)
                
                part_img = Image.open(part_png_path).convert('RGBA')
                part_coords = coords_df.loc[part_hg3_key.lower()]
                part_x = int(part_coords['OffsetX'])
                part_y = int(part_coords['OffsetY'])
                
                paste_x = part_x - base_x
                paste_y = part_y - base_y
                
                print(f"  -> 正在疊加 {os.path.basename(part_png_path)}，位置: ({paste_x}, {paste_y})")
                final_image = composite_high_quality(final_image, part_img, (paste_x, paste_y))

            final_image.save(output_path)
            print(f"  -> ✅ 成功儲存至 {output_path}")

        except (FileNotFoundError, KeyError) as e:
            if isinstance(e, FileNotFoundError):
                print(f"  -> ❌ 錯誤：找不到檔案 {e.filename}。跳過此行。")
            else: # KeyError
                 print(f"  -> ❌ 錯誤：在 hg3_coordinates.txt 中找不到座標索引 '{e}' (已忽略大小寫)。跳過此行。")
        except Exception as e:
            print(f"  -> ❌ 發生未知錯誤：{e}。跳過此行。")

print("\n所有CSV檔案處理完畢！")