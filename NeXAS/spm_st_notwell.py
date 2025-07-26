# final_assembler.py (v23.0 - The Regex Hunter Edition)
# 最終版：採用強大的正規表示式來掃描並提取檔名，以應對不同SPM檔案的格式差異。

import struct
import os
import sys
import glob
import re # 導入正規表示式模組
from dataclasses import dataclass
from typing import List, Dict
from io import BytesIO
try:
    from PIL import Image
except ImportError:
    print("錯誤：Pillow 函式庫未安裝。請執行 'pip install Pillow'")
    sys.exit(1)

# --- 1. 檔名解析器 (全新升級) ---
def parse_filenames_from_spm(file_path: str) -> List[str]:
    """
    使用正規表示式直接從檔案末尾的二進位數據中提取檔名列表。
    """
    with open(file_path, 'rb') as f:
        file_content = f.read()

    filenames = []
    try:
        # 取檔案最後的 2KB 進行掃描，這個範圍足夠安全
        scan_chunk = file_content[-2048:]
        
        # 將二進位數據解碼為字串，忽略任何解碼錯誤
        decoded_text = scan_chunk.decode('sjis', 'ignore')
        
        # 【核心變更】使用正規表示式查找所有符合 "stXXXX.png" 模式的字串
        # 這個模式能夠靈活匹配 stany11.png, stksm31a.png, stats11leg.png 等所有變體
        pattern = r'st[a-zA-Z0-9]+\.png'
        
        found_names = re.findall(pattern, decoded_text, re.IGNORECASE)
        
        if not found_names:
            raise ValueError("正規表示式掃描器在檔案末尾找不到任何符合模式的檔名。")
            
        # 使用 dict.fromkeys 來移除重複的檔名，同時保持原始順序
        ordered_filenames = list(dict.fromkeys(found_names))
        filenames = ordered_filenames

    except Exception as e:
        print(f"  [警告] 解析檔名列表時出錯: {e}。")

    return filenames

# --- 2. 規則合成器 (與 v22 相同) ---
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
            if not leg_image_path:
                print(f"    [警告] 找到了腿部定義 '{leg_piece_name}' 但找不到對應檔案。")
            else:
                print(f"    > 檢測到擴展部件: '{leg_piece_name}'，正在擴展畫布...")
                leg_img = Image.open(os.path.join(images_dir, leg_image_path)).convert('RGBA')
                
                new_width = max(base_img.width, leg_img.width)
                new_height = base_img.height + leg_img.height
                canvas = Image.new('RGBA', (new_width, new_height), (0,0,0,0))
                
                canvas.paste(base_img, (0,0), base_img)
                canvas.paste(leg_img, (0, base_img.height), leg_img)
                print(f"    > 新畫布尺寸: {new_width}x{new_height}")

        output_path_base = os.path.join(output_dir, f"{base_spm_name}_base.png")
        canvas.save(output_path_base, 'PNG')
        print(f"    => 成功儲存基礎版本至: {output_path_base}")

        for overlay_name in overlays:
            overlay_path = file_lookup.get(overlay_name.lower())
            if not overlay_path:
                print(f"    [警告] 找不到配件檔案: '{overlay_name}'")
                continue

            print(f"    > 正在疊加配件: '{overlay_name}'...")
            with Image.open(os.path.join(images_dir, overlay_path)) as overlay_img:
                overlay_img = overlay_img.convert('RGBA')
                temp_canvas = canvas.copy()
                temp_canvas.paste(overlay_img, (0,0), overlay_img)
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
    print("--- SPM 最終合成腳本 (v23.0 - 正則獵手版) ---")

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