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

# --- 動態檢測資料處理函式 (已修正) ---
def prepare_data(csv_path):
    """
    讀取CSV並動態識別「手」與「配件」圖層。
    已修正為可處理任意數量的底線。
    """
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print(f"錯誤：找不到 CSV 檔案於 '{csv_path}'")
        return None

    character_data = defaultdict(lambda: {
        'body': None, 'blush': None, 'expressions': [], 'hands': [], 'accessories': []
    })
    
    # --- 修正：改用 rsplit 確保取得最後一個底線後的數字 ---
    get_id = lambda name: int(name.rsplit('_', 1)[-1])

    # --- 修正：改用 rsplit 確保取得最後一個底線前的所有部分 ---
    df['character_id'] = df['frame_index'].apply(lambda x: x.rsplit('_', 1)[0])

    for char_id, group in df.groupby('character_id'):
        dynamic_layers = group[group['frame_index'].apply(get_id) >= 400]
        if dynamic_layers.empty:
            hand_prefix = '4'
        else:
            max_id = dynamic_layers['frame_index'].apply(get_id).max()
            hand_prefix = str(max_id)[0]
        
        accessory_prefixes = [str(i) for i in range(4, int(hand_prefix))]
        
        for _, row in group.iterrows():
            part_info = row.to_dict()
            # --- 修正：改用 rsplit 確保取得最後一個底線後的數字 ---
            part_code_str = row['frame_index'].rsplit('_', 1)[-1]

            if part_code_str.startswith(hand_prefix):
                character_data[char_id]['hands'].append(part_info)
            elif any(part_code_str.startswith(p) for p in accessory_prefixes):
                character_data[char_id]['accessories'].append(part_info)
            elif part_code_str.startswith(('2', '3')):
                character_data[char_id]['expressions'].append(part_info)
            elif part_code_str.startswith('1'):
                if not character_data[char_id]['blush'] or get_id(row['frame_index']) > get_id(character_data[char_id]['blush']['frame_index']):
                    character_data[char_id]['blush'] = part_info
            elif part_code_str == '0':
                character_data[char_id]['body'] = part_info

    return dict(character_data)

# --- 主合成函式 (已修正) ---
def combine_character_sprites(character_id, parts_info, image_folder, output_folder):
    """
    主合成函式，已修正檔名解析邏輯。
    """
    body = parts_info.get('body')
    blush = parts_info.get('blush')
    expressions = parts_info.get('expressions', [])
    hands = parts_info.get('hands', [])
    accessories = parts_info.get('accessories', [])

    if not body or not hands or not expressions:
        print(f"警告：角色 {character_id} 缺少必要部件 (身/手/表情)，無法產生組合。")
        return
    
    print(f"正在處理角色: {character_id} (動態檢測模式)...")
    base_x, base_y = body['offset_x'], body['offset_y']
    
    accessories_to_loop = accessories if accessories else [None]

    for hand in hands:
        for accessory in accessories_to_loop:
            for expression in expressions:
                # --- 修正：改用 rsplit 確保取得最後一個底線後的數字 ---
                hand_id = hand['frame_index'].rsplit('_', 1)[-1]
                exp_id = expression['frame_index'].rsplit('_', 1)[-1]
                accessory_id = accessory['frame_index'].rsplit('_', 1)[-1] if accessory else None

                fname_parts_base = [character_id, hand_id, exp_id]
                if accessory_id: fname_parts_base.append(accessory_id)
                output_filename_base = "_".join(fname_parts_base) + ".png"
                output_path_base = os.path.join(output_folder, output_filename_base)
                
                if blush:
                    # --- 修正：改用 rsplit 確保取得最後一個底線後的數字 ---
                    blush_id = blush['frame_index'].rsplit('_', 1)[-1]
                    fname_parts_blush = [character_id, hand_id, blush_id, exp_id]
                    if accessory_id: fname_parts_blush.append(accessory_id)
                    output_filename_blush = "_".join(fname_parts_blush) + ".png"
                    output_path_blush = os.path.join(output_folder, output_filename_blush)

                layers_no_blush = [body, hand, expression]
                if accessory: layers_no_blush.append(accessory)

                layers_with_blush = []
                if blush:
                    layers_with_blush = [body, hand, blush, expression]
                    if accessory: layers_with_blush.append(accessory)

                combined_layers = layers_no_blush + layers_with_blush
                unique_parts_map = {}
                for part in combined_layers:
                    if part:  # 確保部件不是 None
                        unique_parts_map[part['frame_index']] = part
                all_possible_parts = list(unique_parts_map.values())
                
                if not all_possible_parts: continue
                
                min_x = min(p['offset_x'] - base_x for p in all_possible_parts)
                min_y = min(p['offset_y'] - base_y for p in all_possible_parts)
                max_x = max((p['offset_x'] - base_x) + p['width'] for p in all_possible_parts)
                max_y = max((p['offset_y'] - base_y) + p['height'] for p in all_possible_parts)
                canvas_width, canvas_height = int(max_x - min_x), int(max_y - min_y)

                def process_and_save(path, layers):
                    if not layers: return
                    if os.path.exists(path):
                        return
                    
                    canvas = Image.new('RGBA', (canvas_width, canvas_height), (0, 0, 0, 0))
                    for part in layers:
                        try:
                            img = Image.open(os.path.join(image_folder, f"{part['frame_index']}.png")).convert("RGBA")
                            px = int((part['offset_x'] - base_x) - min_x)
                            py = int((part['offset_y'] - base_y) - min_y)
                            canvas = composite_high_quality(canvas, img, (px, py))
                        except FileNotFoundError:
                            print(f"  警告: 找不到圖檔 {part['frame_index']}.png")
                            if part['frame_index'] == body['frame_index']: return
                    
                    canvas.save(path)
                    print(f"  已儲存: {os.path.basename(path)}")

                process_and_save(output_path_base, layers_no_blush)
                if blush:
                    process_and_save(output_path_blush, layers_with_blush)

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
