import pandas as pd
from PIL import Image
import os
from collections import defaultdict
import numpy as np

# --- 高精度合成函式 (維持不變) ---
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

# --- 資料處理函式 (維持不變) ---
def prepare_data(csv_path):
    """
    讀取並處理 'coordinates.csv' 檔案
    """
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print(f"錯誤：找不到 CSV 檔案於 '{csv_path}'")
        return None

    character_data = defaultdict(lambda: {
        'body': None, 'blush': None, 'expressions': [], 'hands': []
    })
    df['character_id'] = df['frame_index'].apply(lambda x: x.split('_')[0])

    for char_id, group in df.groupby('character_id'):
        blush_files = group[group['frame_index'].str.contains(r'_1\d{2,}$')]
        if not blush_files.empty:
            character_data[char_id]['blush'] = blush_files.sort_values('frame_index').iloc[-1].to_dict()

        for _, row in group.iterrows():
            part_code = row['frame_index'].split('_')[1]
            if part_code == '0':
                character_data[char_id]['body'] = row.to_dict()
            elif part_code.startswith(('2', '3')):
                character_data[char_id]['expressions'].append(row.to_dict())
            elif part_code.startswith('4'):
                character_data[char_id]['hands'].append(row.to_dict())
    
    return dict(character_data)

# --- 主合成函式 (已更新) ---
def combine_character_sprites(character_id, parts_info, image_folder, output_folder):
    """
    主合成函式，已加入對身體部件的強制檢查。
    """
    body = parts_info.get('body')
    blush = parts_info.get('blush')
    expressions = parts_info.get('expressions', [])
    hands = parts_info.get('hands', [])

    if not body:
        print(f"警告：角色 {character_id} 在CSV中找不到身體部件 (_0) 的資料，已跳過整個角色。")
        return
    if not hands or not expressions:
        print(f"警告：角色 {character_id} 缺少手或表情部件的CSV資料，無法產生組合。")
        return

    print(f"正在處理角色: {character_id} (使用高精度模式)...")
    base_x, base_y = body['offset_x'], body['offset_y']

    for hand in hands:
        for expression in expressions:
            hand_id = hand['frame_index'].split('_')[1]
            exp_id = expression['frame_index'].split('_')[1]
            
            output_filename_base = f"{character_id}_{hand_id}_{exp_id}"
            output_path_standard = os.path.join(output_folder, f"{output_filename_base}.png")
            
            if os.path.exists(output_path_standard):
                print(f"  跳過：檔案 {output_filename_base}.png 已存在。")
                continue

            # --- 計算動態畫布大小 ---
            parts_to_combine = [body, hand, expression]
            if blush: parts_to_combine.append(blush)

            min_x = min(p['offset_x'] - base_x for p in parts_to_combine)
            min_y = min(p['offset_y'] - base_y for p in parts_to_combine)
            max_x = max((p['offset_x'] - base_x) + p['width'] for p in parts_to_combine)
            max_y = max((p['offset_y'] - base_y) + p['height'] for p in parts_to_combine)
            
            canvas_width = int(max_x - min_x)
            canvas_height = int(max_y - min_y)

            # --- 關鍵修正：優先處理身體部件，若失敗則跳過整個組合 ---
            # 1. 建立透明畫布
            current_composite = Image.new('RGBA', (canvas_width, canvas_height), (0, 0, 0, 0))
            
            # 2. 嘗試載入並合成身體
            try:
                body_img = Image.open(os.path.join(image_folder, f"{body['frame_index']}.png")).convert("RGBA")
                paste_x = int((body['offset_x'] - base_x) - min_x)
                paste_y = int((body['offset_y'] - base_y) - min_y)
                current_composite = composite_high_quality(current_composite, body_img, (paste_x, paste_y))
            except FileNotFoundError:
                # 如果找不到身體圖檔，則此組合無效，直接跳到下一個組合
                print(f"  錯誤：找不到基礎身體圖檔 {body['frame_index']}.png，組合 {output_filename_base} 已取消。")
                continue # 使用 continue 跳到 for-loop 的下一次迭代

            # 3. 只有在身體成功後，才繼續合成手和表情
            for part in [hand, expression]:
                try:
                    part_img = Image.open(os.path.join(image_folder, f"{part['frame_index']}.png")).convert("RGBA")
                    paste_x = int((part['offset_x'] - base_x) - min_x)
                    paste_y = int((part['offset_y'] - base_y) - min_y)
                    current_composite = composite_high_quality(current_composite, part_img, (paste_x, paste_y))
                except FileNotFoundError:
                    # 找不到手或表情是可選的，只警告不中斷
                    print(f"  警告：找不到圖片檔案 {part['frame_index']}.png，已在本次合成中跳過此部件。")
                    continue
            
            # 4. 儲存結果
            current_composite.save(output_path_standard)
            print(f"  已儲存: {output_filename_base}.png")

            # 5. 合成臉紅並儲存
            if blush:
                try:
                    blush_img = Image.open(os.path.join(image_folder, f"{blush['frame_index']}.png")).convert("RGBA")
                    paste_x = int((blush['offset_x'] - base_x) - min_x)
                    paste_y = int((blush['offset_y'] - base_y) - min_y)
                    blush_composite = composite_high_quality(current_composite, blush_img, (paste_x, paste_y))
                    
                    output_path_blush = os.path.join(output_folder, f"{output_filename_base}_blush.png")
                    blush_composite.save(output_path_blush)
                except FileNotFoundError:
                    print(f"  警告：找不到臉紅檔案 {blush['frame_index']}.png。")

    print(f"角色 {character_id} 已處理完畢。")


# --- 主程式進入點 (維持不變) ---
if __name__ == "__main__":
    CSV_FILE_PATH = 'coordinates.csv'
    IMAGE_SOURCE_FOLDER = 'images' 
    OUTPUT_FOLDER = 'output'

    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)
    
    all_characters_data = prepare_data(CSV_FILE_PATH)

    if all_characters_data:
        for char_id, parts in all_characters_data.items():
            combine_character_sprites(char_id, parts, IMAGE_SOURCE_FOLDER, OUTPUT_FOLDER)
        print("\n--- 所有處理已完成！(全流程高精度) ---")
    else:
        print("沒有讀取到任何資料，程式已結束。")