import os
import re
from PIL import Image
import sys

# --- 設定來源和目標資料夾 ---
# SOURCE_DIR 是存放 `ev_kan_c01` 等子資料夾的地方
# OUTPUT_DIR 是儲存結果的地方
SOURCE_DIR = "images"
OUTPUT_DIR = "output"

# 存放已處理完成的圖片快取，避免重複合成
# 鍵(key)是圖片的完整路徑，值(value)是 Pillow 的 Image 物件
# 在處理每個子資料夾時會清空
processed_images_cache = {}

def parse_ipt(ipt_path):
    """
    解析 .ipt 檔案，提取基礎圖檔名和座標。
    
    Args:
        ipt_path (str): .ipt 檔案的完整路徑。
        
    Returns:
        dict: 包含 'base_name' (基礎圖檔名, 不含副檔名), 'x' (座標), 'y' (座標) 的字典。
              如果解析失敗則返回 None。
    """
    try:
        with open(ipt_path, 'r', encoding='utf-8') as f:
            content = f.read().replace('\n', ' ') # 將換行符移除，方便 regex 處理
            
            # 1. 提取 base 名稱
            base_match = re.search(r'base\s*=\s*\{"([^"]+)"', content)

            # 2. 精準定位到包含 "file=" 的差分圖定義區塊 (一個被大括號包圍的區段)
            #    這個正規表示式會找到如: { id=1, file="ev_kan_c01_07", x=444, y=208 }
            diff_block_match = re.search(r'\{\s*id\s*=\s*\d+.*?file\s*=\s*".*?x\s*=\s*\d+.*?y\s*=\s*\d+.*?\}', content)

            if base_match and diff_block_match:
                diff_block = diff_block_match.group(0) # 取得整個差分區塊的字串
                
                # 3. 只在這個差分區塊內尋找 x 和 y
                x_match = re.search(r'x\s*=\s*(\d+)', diff_block)
                y_match = re.search(r'y\s*=\s*(\d+)', diff_block)

                if x_match and y_match:
                    return {
                        "base_name": base_match.group(1),
                        "x": int(x_match.group(1)),
                        "y": int(y_match.group(1))
                    }

    except Exception as e:
        print(f"  [錯誤] 解析 IPT 檔案 {ipt_path} 失敗: {e}")
    
    print(f"  [警告] 無法從 {ipt_path} 中正確解析出所有需要的資訊。")
    return None


def build_image(image_name, current_dir, diff_map):
    """
    遞迴地建立一張完整的圖片。
    如果圖片是差分圖，它會先建立其基礎圖，然後將差分貼上。
    如果圖片是基礎圖，它會直接從磁碟讀取。
    使用快取來避免重複工作。

    Args:
        image_name (str): 要建立的圖片檔名 (例如 "ev_kan_c01_07.png")。
        current_dir (str): 目前處理的子資料夾路徑。
        diff_map (dict): 包含此資料夾中所有差分圖資訊的字典。

    Returns:
        PIL.Image: 一個 Pillow 的 Image 物件，代表最終合成的圖片。
    """
    image_path = os.path.join(current_dir, image_name)
    
    # 1. 檢查快取中是否已經有這張圖
    if image_path in processed_images_cache:
        return processed_images_cache[image_path]

    # 2. 檢查這張圖是不是一張差分圖
    if image_name in diff_map:
        print(f"  合成差分圖: {image_name}")
        diff_info = diff_map[image_name]
        base_image_name = diff_info['base_name'] + ".png"
        
        # 3. 遞迴呼叫來建立基礎圖
        print(f"    -> 基礎圖是: {base_image_name}")
        base_image = build_image(base_image_name, current_dir, diff_map)
        
        # 複製一份基礎圖來進行修改，避免影響快取中的原圖
        final_image = base_image.copy()
        
        # 讀取差分圖層
        diff_layer_path = os.path.join(current_dir, image_name)
        try:
            diff_layer = Image.open(diff_layer_path).convert("RGBA")
        except FileNotFoundError:
            print(f"  [錯誤] 找不到差分圖檔: {diff_layer_path}")
            # 如果差分圖不存在，直接返回基礎圖
            return final_image
        
        # 獲取座標並貼上
        x, y = diff_info['x'], diff_info['y']
        # 第三個參數 `diff_layer` 作為遮罩，這樣才能正確處理透明度
        final_image.paste(diff_layer, (x, y), diff_layer)
        
        # 4. 將完成的圖存入快取
        processed_images_cache[image_path] = final_image
        return final_image
    else:
        # 5. 如果不是差分圖，它就是一張基礎圖
        print(f"  讀取基礎圖: {image_name}")
        try:
            base_image = Image.open(image_path).convert("RGBA")
            # 存入快取
            processed_images_cache[image_path] = base_image
            return base_image
        except FileNotFoundError:
            print(f"  [致命錯誤] 找不到基礎圖檔: {image_path}")
            # 終止程式，因為後續的合成都無法進行
            sys.exit(1)


def process_all_images():
    """
    主函數，遍歷所有資料夾並處理圖片。
    """
    print("--- 開始處理圖片合併 ---")
    if not os.path.isdir(SOURCE_DIR):
        print(f"[錯誤] 來源資料夾 '{SOURCE_DIR}' 不存在！")
        return

    # 遍歷來源資料夾中的所有項目
    for subdir_name in os.listdir(SOURCE_DIR):
        current_dir = os.path.join(SOURCE_DIR, subdir_name)
        
        if os.path.isdir(current_dir):
            print(f"\n[處理中] 資料夾: {subdir_name}")
            
            # 清空上一資料夾的快取
            processed_images_cache.clear()
            
            # 建立對應的輸出資料夾
            output_subdir = os.path.join(OUTPUT_DIR, subdir_name)
            os.makedirs(output_subdir, exist_ok=True)
            
            # --- 第一步: 掃描資料夾，建立差分圖地圖 ---
            diff_map = {}
            all_png_files = []
            
            files_in_dir = os.listdir(current_dir)
            files_in_dir.sort() # 確保處理順序一致

            for filename in files_in_dir:
                if filename.endswith(".ipt"):
                    ipt_path = os.path.join(current_dir, filename)
                    info = parse_ipt(ipt_path)
                    if info:
                        # 將 .ipt 檔名換成 .png 作為 key
                        diff_png_name = os.path.splitext(filename)[0] + ".png"
                        diff_map[diff_png_name] = info
                
                elif filename.endswith(".png"):
                    all_png_files.append(filename)

            print(f"  找到 {len(all_png_files)} 個 PNG 檔案, {len(diff_map)} 個為差分圖。")

            # --- 第二步: 遍歷所有 PNG，建立並儲存它們 ---
            for png_file in all_png_files:
                final_image = build_image(png_file, current_dir, diff_map)
                
                # 儲存最終結果
                output_path = os.path.join(output_subdir, png_file)
                try:
                    final_image.save(output_path, "PNG")
                    print(f"  -> ✓ 已儲存: {output_path}\n")
                except Exception as e:
                    print(f"  -> X 儲存失敗: {output_path}, 原因: {e}\n")

    print("--- 所有處理完成 ---")


# --- 執行腳本 ---
if __name__ == "__main__":
    process_all_images()