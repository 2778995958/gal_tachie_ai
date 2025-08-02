import csv
from PIL import Image
import os
import numpy as np

# --- 設定 ---
CSV_FILE = 'lsf_export_all.csv'  # 請換成你的 CSV 檔案名稱
IMAGE_DIR = 'images'             # 存放 PNG 圖片的資料夾
OUTPUT_DIR = 'output'            # 輸出合成圖片的資料夾

# --- 步驟 1: 整合您提供的專業合成邏輯 ---
# --- 高精度合成函式 (無需修改) ---
def composite_high_quality(background_img, foreground_img, position):
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


# --- 主程式 (已修正循環邏輯) ---
def combine_character_images():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"已建立輸出資料夾: {OUTPUT_DIR}")

    grouped_data = {}
    try:
        with open(CSV_FILE, mode='r', encoding='utf-8-sig') as infile:
            reader = csv.DictReader(infile)
            reader.fieldnames = [field.strip() for field in reader.fieldnames]
            for row in reader:
                group_name = row.get('Source_LSF_File')
                if not group_name: continue
                if group_name not in grouped_data:
                    grouped_data[group_name] = []
                grouped_data[group_name].append(row)
    except FileNotFoundError:
        print(f"錯誤：找不到 CSV 檔案 '{CSV_FILE}'。")
        return

    for group_name, group_rows in grouped_data.items():
        print(f"\n--- 正在處理組: {group_name} ---")
        try:
            clothes_parts = [row for row in group_rows if int(row.get('Game_Logic_Index', -1)) == 0]
            expression_parts = [row for row in group_rows if int(row.get('Game_Logic_Index', -1)) == 1]
            blush_part_list = [row for row in group_rows if int(row.get('Game_Logic_Index', -1)) == 99]
            blush_part = blush_part_list[0] if blush_part_list else None
        except (ValueError, TypeError):
            print(f"  警告：組 '{group_name}' 的 Game_Logic_Index 有誤，跳過。")
            continue

        if not clothes_parts: continue

        for clothes_row in clothes_parts:
            try:
                base_x = int(clothes_row['X_Offset'])
                base_y = int(clothes_row['Y_Offset'])
                clothes_filename = clothes_row['PNG_Filename'].strip()
                clothes_path = os.path.join(IMAGE_DIR, f"{clothes_filename}.png")
                clothes_img = Image.open(clothes_path).convert('RGBA')
            except (FileNotFoundError, ValueError, TypeError):
                print(f"  警告：讀取或處理衣服 {clothes_filename} 失敗，跳過此衣服。")
                continue

            # 情況一：如果該組沒有任何表情部件
            if not expression_parts:
                output_filename_base = clothes_filename
                output_path_standard = os.path.join(OUTPUT_DIR, f"{output_filename_base}.png")
                if os.path.exists(output_path_standard):
                    print(f"  檔案已存在，跳過: {output_path_standard}")
                else:
                    clothes_img.save(output_path_standard)
                    print(f"  已儲存: {output_path_standard}")
                # (處理臉紅的邏輯省略，因為和下面重複，可根據需要添加回來)

            # 情況二：有表情部件，進行完整的循環組合
            else:
                # 【關鍵修正】為每一件衣服，遍歷所有表情
                for expression_row in expression_parts:
                    base_composite = clothes_img.copy()
                    
                    exp_filename = expression_row['PNG_Filename'].strip()
                    exp_path = os.path.join(IMAGE_DIR, f"{exp_filename}.png")
                    try:
                        expression_img = Image.open(exp_path).convert('RGBA')
                        exp_x = int(expression_row['X_Offset']) - base_x
                        exp_y = int(expression_row['Y_Offset']) - base_y
                        
                        # 合成 表情 到 衣服上
                        base_composite = composite_high_quality(base_composite, expression_img, (exp_x, exp_y))
                        
                        # 組合檔名
                        exp_suffix = exp_filename.split('_')[-1]
                        output_filename_base = f"{clothes_filename}_{exp_suffix}"
                        output_path_standard = os.path.join(OUTPUT_DIR, f"{output_filename_base}.png")
                        
                        # 儲存標準版
                        if os.path.exists(output_path_standard):
                            print(f"  檔案已存在，跳過: {output_path_standard}")
                        else:
                            base_composite.save(output_path_standard)
                            print(f"  已儲存: {output_path_standard}")

                        # 處理並儲存臉紅版
                        if blush_part:
                            output_path_blush = os.path.join(OUTPUT_DIR, f"{output_filename_base}_blush.png")
                            if os.path.exists(output_path_blush):
                                print(f"  檔案已存在，跳過: {output_path_blush}")
                            else:
                                blush_filename = blush_part['PNG_Filename'].strip()
                                blush_path = os.path.join(IMAGE_DIR, f"{blush_filename}.png")
                                blush_img = Image.open(blush_path).convert('RGBA')
                                blush_x = int(blush_part['X_Offset']) - base_x
                                blush_y = int(blush_part['Y_Offset']) - base_y
                                blush_composite = composite_high_quality(base_composite, blush_img, (blush_x, blush_y))
                                blush_composite.save(output_path_blush)
                                print(f"  已儲存: {output_path_blush} (全流程高精度)")

                    except (FileNotFoundError, ValueError, TypeError) as e:
                        print(f"  警告：處理組合 {clothes_filename} + {exp_filename} 時失敗: {e}")
                        continue

if __name__ == '__main__':
    combine_character_images()
    print("\n--- 所有處理已完成！ ---")