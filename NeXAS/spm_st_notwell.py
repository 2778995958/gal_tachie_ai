# final_assembler.py (v24.0 - The Precision Engine Edition)
# 最終版：引入了基於 NumPy 的高精度 Alpha Blending 引擎，以徹底解決合圖後的灰線問題。

import struct
import os
import sys
import glob
import re
from dataclasses import dataclass
from typing import List, Dict
from io import BytesIO
try:
    from PIL import Image
except ImportError:
    print("錯誤：Pillow 函式庫未安裝。請執行 'pip install Pillow'")
    sys.exit(1)
try:
    import numpy as np
except ImportError:
    print("錯誤：NumPy 函式庫未安裝。請執行 'pip install numpy'")
    sys.exit(1)

# --- 1. 檔名解析器 (與 v23 相同) ---
def parse_filenames_from_spm(file_path: str) -> List[str]:
    with open(file_path, 'rb') as f:
        file_content = f.read()
    filenames = []
    try:
        scan_chunk = file_content[-2048:]
        decoded_text = scan_chunk.decode('sjis', 'ignore')
        pattern = r'st[a-zA-Z0-9]+\.png'
        found_names = re.findall(pattern, decoded_text, re.IGNORECASE)
        if not found_names:
            raise ValueError("正規表示式掃描器在檔案末尾找不到任何符合模式的檔名。")
        ordered_filenames = list(dict.fromkeys(found_names))
        filenames = ordered_filenames
    except Exception as e:
        print(f"  [警告] 解析檔名列表時出錯: {e}。")
    return filenames

# --- ★★★ 2. 全新高精度合成引擎 ★★★ ---
def composite_numpy(base_img: Image.Image, overlay_img: Image.Image, position=(0, 0)) -> Image.Image:
    """
    使用基於 NumPy 的標準 Alpha Blending 公式進行高精度圖像合成。
    """
    # 將 PIL 圖像轉換為 NumPy 陣列，並將像素值轉為 0.0-1.0 的浮點數
    base_np = np.array(base_img, dtype=np.float64) / 255.0
    overlay_np = np.array(overlay_img, dtype=np.float64) / 255.0

    base_h, base_w = base_np.shape[:2]
    overlay_h, overlay_w = overlay_np.shape[:2]
    
    # 建立一個與底圖同大的透明圖層，用來放置前景
    fg_layer = np.zeros_like(base_np)

    # 計算貼上範圍，確保不超出邊界
    x, y = position
    x1, y1 = max(x, 0), max(y, 0)
    x2, y2 = min(x + overlay_w, base_w), min(y + overlay_h, base_h)
    
    overlay_x1, overlay_y1 = x1 - x, y1 - y
    overlay_x2, overlay_y2 = x2 - x, y2 - y

    # 如果有重疊區域，則將前景圖的對應部分複製到透明圖層上
    if x1 < x2 and y1 < y2:
        fg_layer[y1:y2, x1:x2] = overlay_np[overlay_y1:overlay_y2, overlay_x1:overlay_x2]

    # 從 NumPy 陣列中分離出 RGB 和 Alpha 通道
    bg_rgb, bg_a = base_np[:,:,:3], base_np[:,:,3:4]
    fg_rgb, fg_a = fg_layer[:,:,:3], fg_layer[:,:,3:4]

    # 標準 Alpha Blending 公式
    out_a = fg_a + bg_a * (1.0 - fg_a)
    
    out_rgb = np.zeros_like(bg_rgb)
    # 建立一個遮罩，只在 Alpha > 0 的地方進行除法，避免除以零的錯誤
    mask = out_a > 1e-6
    numerator = fg_rgb * fg_a + bg_rgb * bg_a * (1.0 - fg_a)
    np.divide(numerator, out_a, where=mask, out=out_rgb)

    # 合併計算後的 RGBA 通道，並轉回 8-bit 整數 (0-255)
    final_np_float = np.concatenate([out_rgb, out_a], axis=2)
    final_np_uint8 = (final_np_float * 255).round().astype(np.uint8)

    return Image.fromarray(final_np_uint8, 'RGBA')

# --- 3. 規則合成器 (已升級為使用新引擎) ---
def assemble_images_by_rules(spm_filename: str, filenames: List[str], images_dir: str, output_dir: str, file_lookup: Dict[str, str]):
    if not filenames:
        print("  > 檔名列表為空，跳過合成。")
        return

    base_spm_name = os.path.splitext(spm_filename)[0]
    print(f"  > 正在基於規則合成 '{base_spm_name}'...")

    base_image_name = filenames[0]
    overlays = sorted([name for name in filenames[1:] if "leg" not in name.lower()])
    leg_pieces = [name for name in filenames if "leg" in name.lower()]

    try:
        base_image_path = file_lookup.get(base_image_name.lower())
        if not base_image_path:
            print(f"    [錯誤] 找不到底圖檔案: '{base_image_name}'")
            return
        base_img = Image.open(os.path.join(images_dir, base_image_path)).convert('RGBA')
        
        canvas = base_img
        if leg_pieces:
            leg_piece_name = leg_pieces[0]
            leg_image_path = file_lookup.get(leg_piece_name.lower())
            if leg_image_path:
                print(f"    > 檢測到擴展部件: '{leg_piece_name}'，正在擴展畫布...")
                leg_img = Image.open(os.path.join(images_dir, leg_image_path)).convert('RGBA')
                
                new_width = max(base_img.width, leg_img.width)
                new_height = base_img.height + leg_img.height
                
                # 先建立一個擴展後的全透明畫布
                expanded_canvas = Image.new('RGBA', (new_width, new_height), (0,0,0,0))
                
                # 【升級】使用高精度方法貼上底圖和腿部
                expanded_canvas = composite_numpy(expanded_canvas, base_img, position=(0, 0))
                expanded_canvas = composite_numpy(expanded_canvas, leg_img, position=(0, base_img.height))
                canvas = expanded_canvas
                print(f"    > 新畫布尺寸: {new_width}x{new_height}")

        output_path_base = os.path.join(output_dir, f"{base_spm_name}_base.png")
        canvas.save(output_path_base, 'PNG')
        print(f"    => 成功儲存基礎版本至: {output_path_base}")

        for overlay_name in overlays:
            overlay_path = file_lookup.get(overlay_name.lower())
            if not overlay_path: continue

            print(f"    > 正在疊加配件: '{overlay_name}'...")
            with Image.open(os.path.join(images_dir, overlay_path)) as overlay_img:
                overlay_img = overlay_img.convert('RGBA')
                
                # 【升級】使用高精度方法疊加配件
                temp_canvas = composite_numpy(canvas, overlay_img, position=(0,0))
                
                overlay_suffix = os.path.splitext(overlay_name)[0].replace(base_spm_name, '')
                output_path_overlay = os.path.join(output_dir, f"{base_spm_name}{overlay_suffix}.png")
                temp_canvas.save(output_path_overlay, 'PNG')
                print(f"      => 成功儲存疊加版本至: {output_path_overlay}")

    except Exception as e:
        print(f"    [致命錯誤] 在合成過程中發生錯誤: {e}")
        import traceback
        traceback.print_exc()

# --- 主程式 (不變) ---
def main():
    IMAGES_FOLDER = 'images'; OUTPUT_FOLDER = 'output'
    print("--- SPM 最終合成腳本 (v24.0 - 精準引擎版) ---")

    if not os.path.isdir(IMAGES_FOLDER):
        print(f"錯誤：找不到圖片來源資料夾 '{IMAGES_FOLDER}'，請建立它。"); return
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    print(f"圖片來源: '{IMAGES_FOLDER}/'"); print(f"輸出目標: '{OUTPUT_FOLDER}/'")
    
    spm_files = glob.glob('*.spm')
    if not spm_files:
        print("在當前目錄下找不到任何 .spm 檔案。"); return
    
    print(f"\n找到了 {len(spm_files)} 個 .spm 檔案，準備開始批次處理...\n")
    
    try:
        file_lookup = {f.lower(): f for f in os.listdir(IMAGES_FOLDER)}
    except FileNotFoundError:
        print(f"錯誤: images 資料夾不存在，請建立它。")
        return

    for spm_path in spm_files:
        print(f"--- 正在處理檔案: {spm_path} ---")
        try:
            filenames = parse_filenames_from_spm(spm_path)
            if not filenames:
                 print("  > 未能從此 SPM 檔案中提取任何有效的檔名，跳過。")
                 continue
            assemble_images_by_rules(os.path.basename(spm_path), filenames, IMAGES_FOLDER, OUTPUT_FOLDER, file_lookup)
        except Exception as e:
            print(f"處理 {spm_path} 時發生嚴重錯誤: {e}\n")
    print("\n--- 所有任務處理完畢 ---")

if __name__ == "__main__":
    main()
