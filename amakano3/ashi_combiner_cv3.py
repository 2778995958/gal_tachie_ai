import sys
import os
import json
from PIL import Image
from collections import Counter

# (find_best_x_offset_by_left_edge 和 apply_template 函式與 v23 版本完全相同，為求簡潔此處省略)
# (完整的程式碼在下方提供)
ALPHA_THRESHOLD = 10
def find_best_x_offset_by_left_edge(torso_img, legs_img, crop_height=1):
    # ... (與 v23 相同)
    print(f"  -> 將在 y={torso_img.height - crop_height - 1} 的真實接合線上進行輪廓對齊...")
    def get_leftmost_opaque_pixel_x(image_row):
        if 'A' not in image_row.getbands(): return 0
        alpha_pixels = image_row.getchannel('A').load()
        width = image_row.width
        for x in range(width):
            if alpha_pixels[x, 0] > ALPHA_THRESHOLD: return x
        return -1
    seam_y_index = torso_img.height - crop_height - 1
    if seam_y_index < 0: return 0
    torso_seam_row = torso_img.crop((0, seam_y_index, torso_img.width, seam_y_index + 1))
    legs_seam_row = legs_img.crop((0, 0, legs_img.width, 1))
    torso_left_x = get_leftmost_opaque_pixel_x(torso_seam_row)
    legs_left_x = get_leftmost_opaque_pixel_x(legs_seam_row)
    if torso_left_x == -1 or legs_left_x == -1: return 0
    final_offset = torso_left_x - legs_left_x
    print(f"  -> 輪廓起點: (上半身: {torso_left_x}, 腿部: {legs_left_x}) -> 計算偏移: {final_offset}")
    return final_offset

def apply_template(json_path, small_images_folder, crop_height):
    # ... (與 v23 相同)
    print("\n--- 進入「套用模式」---")
    try:
        with open(json_path, 'r', encoding='utf-8') as f: config = json.load(f)
        legs_template_path = config["apply_params"]["legs_template_file"]
        if not os.path.exists(legs_template_path): raise FileNotFoundError(f"找不到腿部範本 '{legs_template_path}'")
        legs_to_paste = Image.open(legs_template_path).convert('RGBA')
        print(f"成功讀取設定檔 '{json_path}'。")
        print(f"本次套用將對所有小圖底部裁切 {crop_height} 像素。")
        small_folder_name = os.path.basename(os.path.normpath(small_images_folder))
        output_folder = os.path.join("output", small_folder_name)
        if not os.path.exists(output_folder): os.makedirs(output_folder)
        for filename in os.listdir(small_images_folder):
            if not filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')): continue
            try:
                small_image_path = os.path.join(small_images_folder, filename)
                base_img_original = Image.open(small_image_path).convert('RGBA')
                print(f"處理中: {filename}")
                paste_offset_x = find_best_x_offset_by_left_edge(base_img_original, legs_to_paste, crop_height)
                base_img = base_img_original
                if base_img.height > crop_height:
                    base_img = base_img.crop((0, 0, base_img.width, base_img.height - crop_height))
                final_width = max(base_img.width, legs_to_paste.width + paste_offset_x)
                final_height = base_img.height + legs_to_paste.height
                final_image = Image.new('RGBA', (final_width, final_height), (0, 0, 0, 0))
                paste_base_x = max(0, -paste_offset_x)
                paste_legs_x = max(0, paste_offset_x)
                final_image.paste(legs_to_paste, (paste_legs_x, base_img.height), mask=legs_to_paste)
                final_image.paste(base_img, (paste_base_x, 0), mask=base_img)
                final_image = final_image.crop(final_image.getbbox()) if final_image.getbbox() else Image.new('RGBA', (1, 1), (0,0,0,0))
                output_filename = os.path.splitext(filename)[0] + '.png'
                output_path = os.path.join(output_folder, output_filename)
                final_image.save(output_path, compress_level=1)
            except Exception as e: print(f"  -> 處理檔案 {filename} 時出錯: {e}")
        print("\n✅ 批量套用處理完成！")
    except Exception as e: print(f"套用過程中發生錯誤: {e}")


def bake_template(large_image_path, small_images_folder, crop_height):
    """模式一：讀取 JSON 參數進行烘焙，如果 JSON 不存在則自動計算初始參數。"""
    print("\n--- 進入「烘焙模式」---")
    
    small_folder_name = os.path.basename(os.path.normpath(small_images_folder))
    json_path = f"{small_folder_name}.json"
    params = {}

    # --- << 關鍵修正：恢復「首次執行時自動計算」的邏輯 >> ---
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                params = json.load(f)["bake_params"]
            print(f"偵測到現有設定檔 '{json_path}'，將使用其中的參數進行烘焙。")
        except Exception:
            print(f"設定檔 '{json_path}' 格式錯誤，將重新自動計算。")
            params = {} # 讓後續的 not params 捕捉到
    
    if not params:
        print("未找到或無法讀取設定檔，將進行首次自動計算...")
        try:
            large_img_temp = Image.open(large_image_path)
            first_small_file = next((f for f in os.listdir(small_images_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))), None)
            if not first_small_file: raise FileNotFoundError("小圖資料夾中找不到任何圖片檔案。")
            
            base_img_temp = Image.open(os.path.join(small_images_folder, first_small_file))
            
            # 根據圖片寬度，自動計算出一個準確的初始縮放比例
            calculated_scale = base_img_temp.width / large_img_temp.width
            params = {
                "scale_factor": calculated_scale,
                "x_offset": 0,
                "y_offset": 0
            }
            print(f"已根據圖片寬度自動計算出基礎縮放比例: {calculated_scale:.4f}")
        except Exception as e:
            print(f"自動計算參數時發生錯誤: {e}"); return

    # --- 後續烘焙邏輯 ---
    try:
        large_img = Image.open(large_image_path).convert('RGBA')
        first_small_file = next((f for f in os.listdir(small_images_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))), None)
        base_img_original = Image.open(os.path.join(small_images_folder, first_small_file)).convert('RGBA')
        
        print(f"使用大圖 '{os.path.basename(large_image_path)}' 和預覽小圖 '{first_small_file}'。")
        print(f"當前使用參數: Scale={params['scale_factor']:.4f}, X-Offset={params['x_offset']}, Y-Offset={params['y_offset']}")

        bake_time_width = base_img_original.width
        base_img = base_img_original
        # 烘焙時使用指定的裁切高度
        if base_img.height > crop_height:
            base_img = base_img.crop((0, 0, base_img.width, base_img.height - crop_height))

        resized_large_img = large_img.resize((int(large_img.width * params['scale_factor']), int(large_img.height * params['scale_factor'])), Image.Resampling.LANCZOS)
        
        # ... (後續程式碼與 v23 相同) ...
        canvas_width = base_img.width + abs(params['x_offset'])
        canvas_height = base_img.height + resized_large_img.height + abs(params['y_offset'])
        paste_large_x, paste_large_y = (params['x_offset'] if params['x_offset'] >= 0 else 0, params['y_offset'] if params['y_offset'] >= 0 else 0)
        paste_base_x, paste_base_y = (abs(params['x_offset']) if params['x_offset'] < 0 else 0, abs(params['y_offset']) if params['y_offset'] < 0 else 0)
        background_layer = Image.new('RGBA', (canvas_width, canvas_height), (0, 0, 0, 0))
        background_layer.paste(resized_large_img, (paste_large_x, paste_large_y), mask=resized_large_img)
        foreground_layer = Image.new('RGBA', (canvas_width, canvas_height), (0, 0, 0, 0))
        foreground_layer.paste(base_img, (paste_base_x, paste_base_y), mask=base_img)
        final_canvas = Image.alpha_composite(background_layer, foreground_layer)
        preview_image = final_canvas.crop(final_canvas.getbbox()) if final_canvas.getbbox() else Image.new('RGBA', (1, 1), (0,0,0,0))
        legs_canvas = final_canvas.copy()
        hole = Image.new('RGBA', base_img.size, (0, 0, 0, 0))
        legs_canvas.paste(hole, (paste_base_x, paste_base_y))
        legs_template = legs_canvas.crop(legs_canvas.getbbox()) if legs_canvas.getbbox() else Image.new('RGBA', (1, 1), (0,0,0,0))
        preview_path = f"{small_folder_name}_preview.png"
        preview_image.save(preview_path, compress_level=1)
        print(f"\n✅ 已產生預覽圖: '{preview_path}'")
        legs_template_path = f"{small_folder_name}_legs.png"
        legs_template.save(legs_template_path, compress_level=1)
        print(f"✅ 已烘焙腿部範本: '{legs_template_path}'")
        json_config = {"bake_params": params, "apply_params": {"legs_template_file": legs_template_path, "bake_time_width": bake_time_width, "crop_height": crop_height}}
        with open(json_path, 'w', encoding='utf-8') as f: json.dump(json_config, f, indent=4, ensure_ascii=False)
        print(f"✅ 已更新設定檔: '{json_path}'")
        print("\n烘焙完成！如果不滿意，請修改 JSON 中的 bake_params 並重新執行烘焙。")
    except Exception as e:
        print(f"烘焙過程中發生錯誤: {e}")


if __name__ == "__main__":
    print("參數化批量合併工具 (v24 - 修正首次烘焙計算)")
    print("="*60)
    args = sys.argv
    # ... (命令列解析邏輯與 v22/v23 相同) ...
    if '--bake' in args:
        crop_height = 1
        if '--crop' in args:
            try:
                crop_index = args.index('--crop') + 1
                crop_height = int(args[crop_index])
            except (ValueError, IndexError):
                print("錯誤：--crop 參數使用不當"); sys.exit(1)
        try:
            path_args = [arg for arg in args[1:] if not arg.startswith('--')]
            if '--crop' in args: path_args.remove(str(crop_height))
            large_img_path = next(p for p in path_args if os.path.isfile(p))
            small_folder_path = next(p for p in path_args if os.path.isdir(p))
            bake_template(large_img_path, small_folder_path, crop_height)
        except (StopIteration, IndexError):
             print("烘焙模式錯誤：請提供一個大圖檔案和一個小圖資料夾。")
    elif '--apply' in args:
        crop_height = 1
        if '--crop' in args:
            try:
                crop_index = args.index('--crop') + 1
                crop_height = int(args[crop_index])
            except (ValueError, IndexError):
                print("錯誤：--crop 參數使用不當"); sys.exit(1)
        try:
            path_args = [arg for arg in args[1:] if not arg.startswith('--')]
            if '--crop' in args: path_args.remove(str(crop_height))
            json_path = next(p for p in path_args if p.lower().endswith('.json'))
            small_folder_path = next(p for p in path_args if os.path.isdir(p))
            apply_template(json_path, small_folder_path, crop_height)
        except (StopIteration, IndexError):
            print("套用模式錯誤：命令格式應為 --apply <設定檔.json> <小圖資料夾>")
    else:
        print("如何使用：...")
    input("\n按 Enter 鍵結束...")