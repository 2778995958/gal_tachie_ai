import os
import shutil
from PIL import Image
import itertools # ★★★ 引入新工具 ★★★

# --- 基礎設定 (維持不變) ---

# 輸入資料夾名稱
FUKU_DIR = "fuku"
KAO_DIR = "kao"
KAMI_DIR = "kami"
KUCHI_DIR = "kuchi"
HOHO_DIR = "hoho"
EFFECT_DIR = "effect"

# 輸出資料夾名稱
OUTPUT_ROOT = "output"
TEMP_DIR = os.path.join(OUTPUT_ROOT, "temp")
FINAL_BASE_DIR = OUTPUT_ROOT
KAO_KUCHI_DIR = os.path.join(OUTPUT_ROOT, "kao_kuchi")
KAO_KUCHI_EFFECT_DIR = os.path.join(OUTPUT_ROOT, "kao_kuchi_effect")
KAO_KUCHI_HOHO_DIR = os.path.join(OUTPUT_ROOT, "kao_kuchi_hoho")
KAO_KUCHI_HOHO_EFFECT_DIR = os.path.join(OUTPUT_ROOT, "kao_kuchi_hoho_effect")

MAX_EFFECT_LAYERS = 1
# 是否要額外生成一個「完全沒有效果」的乾淨版本？
# True = 是, False = 否
GENERATE_NO_EFFECT_VERSION = False

# --- 核心函式 (維持不變) ---

def ensure_dir(dir_path):
    """確保資料夾存在，如果不存在則建立"""
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

def get_image_position(file_path):
    """
    從 PNG 檔案的 tEXt 中繼資料區塊中讀取位置座標。
    這是一個更穩健、更可靠的新版本。
    """
    try:
        # 使用 with Image.open() 可以確保檔案被正確關閉
        with Image.open(file_path) as img:
            # Pillow 會將 tEXt 區塊的資訊儲存在 .info 這個字典中。
            # 'tEXtcomment pos,212,-31...' 的關鍵字 (key) 是 'comment'。
            if 'comment' in img.info:
                # 取得 comment 的內容字串，例如 "pos,212,-31,920,2604"
                comment_string = img.info['comment']
                
                # 分割字串來取得座標
                parts = comment_string.split(',')
                
                # 確保格式是我們預期的 "pos,x,y,..."
                if len(parts) >= 3 and parts[0] == 'pos':
                    x = int(parts[1])
                    y = int(parts[2])
                    # 成功找到座標，返回它們
                    return x, y
                    
    except FileNotFoundError:
        # 這個錯誤最好單獨處理，讓使用者知道是檔案不見了
        print(f"警告：找不到檔案 {os.path.basename(file_path)}")
        return None, None
    except Exception as e:
        # 捕捉其他可能的錯誤，例如圖片格式損毀、權限問題等
        print(f"警告：讀取 '{os.path.basename(file_path)}' 的座標時發生錯誤: {e}")
        return None, None
            
    # 如果程式執行到這裡，代表圖片中沒有 'comment' 資訊或格式不符
    return None, None

# (ensure_dir, get_image_position, get_files_safely, main, main_full 等函式保持不變)

def composite_images(base, part_img_path, fuku_coords):
    """
    合成圖片。base 可以是路徑或已開啟的 PIL Image 物件。
    這個版本強化了對 base 參數的類型檢查，以修復 AttributeError。
    """
    # 座標處理邏輯 (不變)
    if fuku_coords[0] is None:
        return None
    
    part_coords = get_image_position(part_img_path)
    if part_coords[0] is None:
        print(f"\n    └ 資訊: 部件 {os.path.basename(part_img_path)} 無座標，使用 (0,0)。")
        part_x, part_y = 0, 0
    else:
        part_x, part_y = part_coords
        
    dx = part_x - fuku_coords[0]
    dy = part_y - fuku_coords[1]
    
    print(f"      └ 貼上 {os.path.basename(part_img_path)} 到相對位置 ({dx}, {dy})")

    try:
        # --- ★★★ 關鍵修正區域 ★★★ ---
        # 這裡我們判斷傳入的 base 是「檔案路徑」還是「已經在記憶體中的圖片物件」
        if isinstance(base, str):
            # 如果是字串 (str)，代表它是一個檔案路徑，我們需要用 Image.open() 打開它
            base_img = Image.open(base).convert("RGBA")
        elif isinstance(base, Image.Image):
            # 如果它已經是圖片物件 (Image.Image)，我們就直接使用它，不再打開
            base_img = base
        else:
            # 如果傳入了未知的類型，印出錯誤並返回
            print(f"錯誤：composite_images 收到了未知的 base 類型: {type(base)}")
            return None

        # part_img_path 永遠都應該是檔案路徑，所以我們總是打開它
        part_img = Image.open(part_img_path).convert("RGBA")
        
        # 建立臨時圖層並合成 (不變)
        temp_layer = Image.new("RGBA", base_img.size)
        temp_layer.paste(part_img, (dx, dy))
        return Image.alpha_composite(base_img, temp_layer)

    except FileNotFoundError:
        print(f"錯誤：合成時找不到檔案 {part_img_path}")
        return None
    except Exception as e:
        print(f"合成過程中發生未知錯誤: {e}")
        return None

def get_files_safely(dir_name):
    """
    安全地獲取資料夾中的 .png 檔案清單。
    如果資料夾不存在，返回一個空列表。
    """
    if not os.path.isdir(dir_name):
        print(f"資訊：找不到可選資料夾 '{dir_name}'，將跳過此部件。")
        return []
    return [f for f in os.listdir(dir_name) if f.endswith('.png')]

def main_full():
    """主函式，執行所有合成步驟 (已更新：修正效果合成問題並使用最大層數設定)"""
    
    base_dirs = [OUTPUT_ROOT, TEMP_DIR, FINAL_BASE_DIR, KAO_KUCHI_DIR]
    for d in base_dirs: ensure_dir(d)
    try:
        fuku_files = get_files_safely(FUKU_DIR); kao_files = get_files_safely(KAO_DIR)
        if not fuku_files or not kao_files: print(f"錯誤：基礎資料夾 '{FUKU_DIR}' 或 '{KAO_DIR}' 為空。"); return
    except Exception as e: print(f"讀取基礎資料夾時出錯: {e}"); return
    kami_files = get_files_safely(KAMI_DIR); kuchi_files = get_files_safely(KUCHI_DIR); hoho_files = get_files_safely(HOHO_DIR); effect_files = get_files_safely(EFFECT_DIR)
    
    for fuku_file in fuku_files:
        fuku_base_name = os.path.splitext(fuku_file)[0]
        fuku_path = os.path.join(FUKU_DIR, fuku_file)
        fuku_coords = get_image_position(fuku_path)
        if fuku_coords[0] is None: print(f"資訊: Fuku {fuku_file} 無座標，預設為 (0, 0)。"); fuku_coords = (0, 0)
        print(f"\n--- 正在處理基礎: {fuku_file} ---")

        # Step 1
        print("  第一步: fuku + kao -> temp");
        for kao_file in kao_files:
            composed = composite_images(fuku_path, os.path.join(KAO_DIR, kao_file), fuku_coords)
            if composed:
                output_path = os.path.join(TEMP_DIR, f"{fuku_base_name}_{os.path.splitext(kao_file)[0]}.png")
                if not os.path.exists(output_path): composed.save(output_path)

        # Step 2
        print("  第二步: temp + kami -> output/")
        if kami_files:
            temp_files_s1 = [f for f in os.listdir(TEMP_DIR) if f.startswith(fuku_base_name)]
            for temp_file in temp_files_s1:
                base_path = os.path.join(TEMP_DIR, temp_file)
                for kami_file in kami_files:
                    composed = composite_images(base_path, os.path.join(KAMI_DIR, kami_file), fuku_coords)
                    if composed:
                        output_path = os.path.join(FINAL_BASE_DIR, f"{os.path.splitext(temp_file)[0]}_{os.path.splitext(kami_file)[0]}.png")
                        if not os.path.exists(output_path): composed.save(output_path)
        else:
            print("  資訊: 'kami' 為空，已跳過合成。")

        # Step 3
        source_dir_s3 = FINAL_BASE_DIR if kami_files else TEMP_DIR
        print(f"  第三步: {'output/' if kami_files else 'temp'} + kuchi -> kao_kuchi")
        if not os.path.isdir(source_dir_s3): print(f"  警告: 來源 '{source_dir_s3}' 不存在。"); continue
        base_files_s2 = [f for f in os.listdir(source_dir_s3) if f.startswith(fuku_base_name)]
        if not base_files_s2: print(f"  警告: 在 '{source_dir_s3}' 中找不到檔案。"); continue
        for base_file in base_files_s2:
            base_path = os.path.join(source_dir_s3, base_file)
            if kuchi_files:
                for kuchi_file in kuchi_files:
                    composed = composite_images(base_path, os.path.join(KUCHI_DIR, kuchi_file), fuku_coords)
                    if composed:
                        output_path = os.path.join(KAO_KUCHI_DIR, f"{os.path.splitext(base_file)[0]}_{os.path.splitext(kuchi_file)[0]}.png")
                        if not os.path.exists(output_path): composed.save(output_path)
            else:
                output_path = os.path.join(KAO_KUCHI_DIR, base_file)
                if not os.path.exists(output_path): shutil.copy(base_path, output_path)
        
        # Step 4
        if effect_files:
            ensure_dir(KAO_KUCHI_EFFECT_DIR)
            print("  第四步: kao_kuchi + [效果組合] -> kao_kuchi_effect")
            base_files_s3 = [f for f in os.listdir(KAO_KUCHI_DIR) if f.startswith(fuku_base_name)]
            for base_file in base_files_s3:
                base_path = os.path.join(KAO_KUCHI_DIR, base_file)
                if GENERATE_NO_EFFECT_VERSION:
                    output_path = os.path.join(KAO_KUCHI_EFFECT_DIR, f"{os.path.splitext(base_file)[0]}_no_effect.png")
                    if not os.path.exists(output_path): shutil.copy(base_path, output_path)
                for size in range(1, MAX_EFFECT_LAYERS + 1):
                    if len(effect_files) < size: continue
                    for effect_combo in itertools.combinations(effect_files, size):
                        print(f"    - 正在生成組合: {effect_combo}")
                        current_image = Image.open(base_path).convert("RGBA")
                        for effect_file in effect_combo:
                            effect_path = os.path.join(EFFECT_DIR, effect_file)
                            result_image = composite_images(current_image, effect_path, fuku_coords)
                            if result_image: current_image = result_image
                            else: print(f"      └ 警告：合成 {effect_file} 失敗。")
                        combo_name_parts = [os.path.splitext(f)[0] for f in effect_combo]
                        combo_suffix = "_".join(sorted(combo_name_parts))
                        output_path = os.path.join(KAO_KUCHI_EFFECT_DIR, f"{os.path.splitext(base_file)[0]}_{combo_suffix}.png")
                        if not os.path.exists(output_path): print(f"    └ 儲存至: {os.path.basename(output_path)}"); current_image.save(output_path)
        else:
            print("  資訊: 'effect' 資料夾為空，已跳過第四步。")

        # Step 5
        if hoho_files:
            ensure_dir(KAO_KUCHI_HOHO_DIR)
            print("  第五步: kao_kuchi + hoho -> kao_kuchi_hoho")
            base_files_s3_for_hoho = [f for f in os.listdir(KAO_KUCHI_DIR) if f.startswith(fuku_base_name)]
            for base_file in base_files_s3_for_hoho:
                base_path = os.path.join(KAO_KUCHI_DIR, base_file)
                for hoho_file in hoho_files:
                    composed = composite_images(base_path, os.path.join(HOHO_DIR, hoho_file), fuku_coords)
                    if composed:
                        output_path = os.path.join(KAO_KUCHI_HOHO_DIR, f"{os.path.splitext(base_file)[0]}_{os.path.splitext(hoho_file)[0]}.png")
                        if not os.path.exists(output_path): composed.save(output_path)
        else:
            print("  資訊: 'hoho' 資料夾為空，已跳過第五步。")
            
        # Step 6
        if hoho_files and effect_files:
            ensure_dir(KAO_KUCHI_HOHO_EFFECT_DIR)
            print("  第六步: kao_kuchi_hoho + [效果組合] -> kao_kuchi_hoho_effect")
            base_files_s5 = [f for f in os.listdir(KAO_KUCHI_HOHO_DIR) if f.startswith(fuku_base_name)]
            for base_file in base_files_s5:
                base_path = os.path.join(KAO_KUCHI_HOHO_DIR, base_file)
                if GENERATE_NO_EFFECT_VERSION:
                    output_path = os.path.join(KAO_KUCHI_HOHO_EFFECT_DIR, f"{os.path.splitext(base_file)[0]}.png")
                    if not os.path.exists(output_path): shutil.copy(base_path, output_path)
                for size in range(1, MAX_EFFECT_LAYERS + 1):
                    if len(effect_files) < size: continue
                    for effect_combo in itertools.combinations(effect_files, size):
                        print(f"    - 正在生成組合: {effect_combo}")
                        current_image = Image.open(base_path).convert("RGBA")
                        for effect_file in effect_combo:
                            effect_path = os.path.join(EFFECT_DIR, effect_file)
                            result_image = composite_images(current_image, effect_path, fuku_coords)
                            if result_image: current_image = result_image
                            else: print(f"      └ 警告：合成 {effect_file} 失敗。")
                        combo_name_parts = [os.path.splitext(f)[0] for f in effect_combo]
                        combo_suffix = "_".join(sorted(combo_name_parts))
                        output_path = os.path.join(KAO_KUCHI_HOHO_EFFECT_DIR, f"{os.path.splitext(base_file)[0]}_{combo_suffix}.png")
                        if not os.path.exists(output_path): print(f"    └ 儲存至: {os.path.basename(output_path)}"); current_image.save(output_path)
        else:
            print("  資訊: 'hoho' 或 'effect' 資料夾為空，已跳過第六步。")

    print("\n--- 所有組合處理完畢！---")

if __name__ == '__main__':
    # 為了方便您直接複製貼上，這裡提供完整的 main 函式
    # 上面省略的部分，在這裡補全
    main_full()