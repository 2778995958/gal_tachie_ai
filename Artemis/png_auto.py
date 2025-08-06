import os
import re
from collections import defaultdict
from PIL import Image
import numpy as np

# ==============================================================================
# --- 設定區 ---
# 你可以在這裡修改所有參數
# ==============================================================================

# 1. 輸入和輸出的根資料夾名稱
INPUT_ROOT = "fg"
OUTPUT_ROOT = "output"

# 2. 臉紅效果使用的「確切」編號
#    例如，a0081.png, b0081.png 會被視為臉紅
BLUSH_SUFFIX_NUMBER = 81

# 3. 配件使用的「起始」編號
#    例如，設為 82，則 a0082, a0083... 等都會被視為配件
ACCESSORY_SUFFIX_START = 82

# 4. 角色內部的資料夾處理優先級順序
#    程式會從左到右，依序處理這些資料夾
PROCESSING_ORDER = ["z2", "z1", "no", "bc", "fa"] 

# ==============================================================================
# --- 核心程式區 ---
# (通常不需要修改以下內容)
# ==============================================================================

def ensure_dir(dir_path):
    """確保資料夾存在，如果不存在則建立"""
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

def get_image_position(file_path):
    """從 PNG 檔案的 tEXt 中繼資料區塊中讀取位置座標。"""
    try:
        with Image.open(file_path) as img:
            if 'comment' in img.info:
                comment_string = img.info['comment']
                parts = comment_string.split(',')
                if len(parts) >= 3 and parts[0] == 'pos':
                    x = int(parts[1])
                    y = int(parts[2])
                    if x == 0 and y == 0:
                        return None, None
                    return x, y
    except FileNotFoundError:
        print(f"警告：找不到檔案 {os.path.basename(file_path)}")
        return None, None
    except Exception as e:
        print(f"警告：讀取 '{os.path.basename(file_path)}' 的座標時發生錯誤: {e}")
        return None, None
    return None, None

def composite_images(base_image, overlay_path, base_coords):
    """使用 NumPy 將一個圖片疊加到另一個圖片上，進行高效 Alpha 合成。"""
    overlay_coords = get_image_position(overlay_path)
    if not base_coords or not overlay_coords:
        return base_image

    dx = overlay_coords[0] - base_coords[0]
    dy = overlay_coords[1] - base_coords[1]

    try:
        with Image.open(overlay_path).convert("RGBA") as overlay_img:
            overlay_canvas = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
            overlay_canvas.paste(overlay_img, (dx, dy))

            base_arr = np.array(base_image) / 255.0
            overlay_arr = np.array(overlay_canvas) / 255.0

            rgb_fg = overlay_arr[:, :, :3]
            alpha_fg = overlay_arr[:, :, 3:]
            rgb_bg = base_arr[:, :, :3]
            alpha_bg = base_arr[:, :, 3:]

            alpha_out = alpha_fg + alpha_bg * (1 - alpha_fg)
            rgb_out = np.divide(
                rgb_fg * alpha_fg + rgb_bg * alpha_bg * (1 - alpha_fg),
                alpha_out,
                out=np.zeros_like(rgb_fg),
                where=alpha_out != 0
            )

            output_arr = np.concatenate((rgb_out, alpha_out), axis=2)
            output_img = Image.fromarray((output_arr * 255).astype('uint8'))
            return output_img
    except FileNotFoundError:
        print(f"錯誤：合成時找不到檔案 {overlay_path}")
        return base_image
    except Exception as e:
        print(f"NumPy 合成過程中發生未知錯誤: {e}")
        import traceback
        traceback.print_exc()
        return base_image

def process_directory(current_dir, processed_combinations):
    """
    處理單一資料夾内的圖片合成工作，並使用更可靠的追蹤器來跳過重複組合。
    （此為包含完整合成邏輯的最終版本）
    """
    print(f"\n--- 正在處理資料夾：{current_dir} ---")

    # 提取當前資料夾的名稱作為「版本號」 (例如 "z1", "bc")
    current_version = os.path.basename(current_dir)

    # 檔案分類
    groups = defaultdict(lambda: defaultdict(list))
    body_pattern = re.compile(r"^(.+)([a-z])(\d{4,})\.png$")
    face_pattern = re.compile(r"^([a-z])(\d{4,})\.png$")
    files_in_dir = [f for f in os.listdir(current_dir) if f.endswith('.png')]

    for filename in files_in_dir:
        body_match = body_pattern.match(filename)
        if body_match:
            groups[body_match.group(2)]['body'].append(filename)
            continue
        face_match = face_pattern.match(filename)
        if face_match:
            group_key, number_str = face_match.groups()
            number = int(number_str)
            if number == BLUSH_SUFFIX_NUMBER:
                groups[group_key]['blush'] = filename
            elif number >= ACCESSORY_SUFFIX_START:
                groups[group_key]['accessories'].append(filename)
            else:
                groups[group_key]['face'].append(filename)

    # 執行合成邏輯
    for group_key, parts in groups.items():
        if not parts['body'] or not parts['face']:
            continue
        print(f"  > 正在處理群組 '{group_key}'...")
        blush_path = os.path.join(current_dir, parts['blush']) if 'blush' in parts else None
        accessory_paths = [os.path.join(current_dir, f) for f in parts['accessories']]
        
        for body_filename in parts['body']:
            body_basename = os.path.splitext(body_filename)[0]
            # 從檔名中移除版本號來建立「身體概念名稱」
            body_concept_key = body_basename.replace(current_version, '', 1)

            body_path = os.path.join(current_dir, body_filename)
            body_coords = get_image_position(body_path)
            if not body_coords:
                print(f"    - 警告：身體圖片 {body_filename} 無有效座標，跳過。")
                continue

            for face_filename in parts['face']:
                face_concept_key = os.path.splitext(face_filename)[0]

                # 核心判斷邏輯：如果此組合已處理過，則跳過
                if face_concept_key in processed_combinations[body_concept_key]:
                    print(f"    - 跳過組合：({body_filename}, {face_filename}) 因為概念上已生成過。")
                    continue

                print(f"    - 生成新組合：({body_filename}, {face_filename})")
                
                output_dir = os.path.join(OUTPUT_ROOT, os.path.relpath(current_dir, INPUT_ROOT))
                ensure_dir(output_dir)

                try:
                    with Image.open(body_path).convert("RGBA") as body_img:
                        # --- 第一層：身體 + 表情 ---
                        base_composite = composite_images(body_img, os.path.join(current_dir, face_filename), body_coords)
                        
                        # 決定輸出檔名並儲存
                        output_filename_base = f"{body_basename}_{face_concept_key}.png"
                        output_path_base = os.path.join(output_dir, output_filename_base)
                        if not os.path.exists(output_path_base):
                            base_composite.save(output_path_base)

                        # 成功生成後，立刻更新追蹤器
                        processed_combinations[body_concept_key].add(face_concept_key)

                        # 為新生成的圖片準備後續處理（配件、臉紅）
                        images_to_process = [(output_filename_base, base_composite)]
                        
                        # --- 第二層：在(身體+表情)的基礎上，疊加配件 ---
                        composites_with_accessories = []
                        if accessory_paths:
                            for acc_path in accessory_paths:
                                acc_composite = composite_images(base_composite, acc_path, body_coords)
                                acc_filename = f"{os.path.splitext(output_filename_base)[0]}_{os.path.splitext(os.path.basename(acc_path))[0]}.png"
                                
                                acc_output_path = os.path.join(output_dir, acc_filename)
                                if not os.path.exists(acc_output_path):
                                    acc_composite.save(acc_output_path)
                                
                                # 將帶配件的版本也加入待處理清單，以便後續疊加臉紅
                                composites_with_accessories.append( (acc_filename, acc_composite) )
                        
                        images_to_process.extend(composites_with_accessories)

                        # --- 第三層：為所有已生成的結果（包含有/無配件）疊加臉紅 ---
                        if blush_path:
                            for original_filename, image_to_blush in images_to_process:
                                blush_composite = composite_images(image_to_blush, blush_path, body_coords)
                                blush_filename = f"{os.path.splitext(original_filename)[0]}_{os.path.splitext(os.path.basename(blush_path))[0]}.png"
                                blush_output_path = os.path.join(output_dir, blush_filename)
                                
                                if not os.path.exists(blush_output_path):
                                    blush_composite.save(blush_output_path)

                except Exception as e:
                    print(f"      - 錯誤：處理 {body_filename} 和 {face_filename} 時發生嚴重錯誤: {e}")

def main():
    """
    主函式，以角色為單位，並按指定優先級順序執行處理。
    """
    if not os.path.isdir(INPUT_ROOT):
        print(f"錯誤：找不到輸入資料夾 '{INPUT_ROOT}'。請檢查頂部的設定是否正確。")
        return

    # 1. 取得所有角色的資料夾 (例如 "fg" 下的 "aya", "bobe", ...)
    try:
        character_dirs = [d for d in os.listdir(INPUT_ROOT) if os.path.isdir(os.path.join(INPUT_ROOT, d))]
    except FileNotFoundError:
        print(f"錯誤：找不到輸入資料夾 '{INPUT_ROOT}'。")
        return

    # 2. 逐一處理每個角色
    for character_name in character_dirs:
        print(f"\n=========================================")
        print(f"=== 開始處理角色：{character_name}")
        print(f"=========================================")
        
        character_path = os.path.join(INPUT_ROOT, character_name)
        
        # 為每個新角色建立一個獨立的「已處理組合」追蹤器
        processed_combinations = defaultdict(set)

        # 3. 根據設定的優先級順序，處理該角色的子資料夾
        for folder_name in PROCESSING_ORDER:
            current_dir = os.path.join(character_path, folder_name)
            
            if os.path.isdir(current_dir):
                # 傳入追蹤器，讓 process_directory 可以讀取和更新它
                process_directory(current_dir, processed_combinations)
            else:
                print(f"\n--- 資訊：在角色 {character_name} 中找不到資料夾 '{folder_name}'，跳過。 ---")


    print("\n--- 所有角色處理完畢！ ---")

if __name__ == '__main__':
    main()