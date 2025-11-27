import os
import glob
from PIL import Image

# ================= 設定區 =================
# 你的輸入資料夾名稱 (上一部腳本解壓出來的結果)
INPUT_ROOT = "output"
# 合成後的圖片存放位置
OUTPUT_ROOT = "merged_output"
# =========================================

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def merge_groups():
    # 1. 掃描所有資料夾並進行分組
    # 結構: groups[prefix] = {'bases': [folder_paths], 'faces': [folder_paths]}
    groups = {}

    if not os.path.exists(INPUT_ROOT):
        print(f"找不到輸入資料夾: {INPUT_ROOT}")
        return

    print("正在掃描資料夾並分組...")
    
    # 取得 INPUT_ROOT 下的所有子資料夾
    subfolders = [f.path for f in os.scandir(INPUT_ROOT) if f.is_dir()]

    for folder_path in subfolders:
        folder_name = os.path.basename(folder_path)
        parts = folder_name.split('_')
        
        # 確保檔名至少有足夠的部分 (例如 bs1_mk1_base...)
        if len(parts) < 3:
            continue
            
        # 提取前綴 (例如: bs1_mk1)
        prefix = f"{parts[0]}_{parts[1]}"
        
        if prefix not in groups:
            groups[prefix] = {'bases': [], 'faces': []}
            
        if 'base' in folder_name.lower():
            groups[prefix]['bases'].append(folder_path)
        elif 'face' in folder_name.lower():
            groups[prefix]['faces'].append(folder_path)

    # 2. 開始執行合成
    ensure_dir(OUTPUT_ROOT)
    
    for prefix, data in groups.items():
        bases = data['bases']
        faces = data['faces']
        
        if not bases or not faces:
            print(f"[{prefix}] 跳過 - 缺少 base 或 face 資料夾")
            continue
            
        print(f"[{prefix}] 發現 {len(bases)} 個身體資料夾, {len(faces)} 個差分資料夾，開始合成...")
        
        # 建立該角色的輸出目錄
        character_output_dir = os.path.join(OUTPUT_ROOT, prefix)
        ensure_dir(character_output_dir)

        # 雙重迴圈：遍歷每個 base 資料夾 vs 每個 face 資料夾
        for base_folder in bases:
            base_folder_name = os.path.basename(base_folder)
            base_images = glob.glob(os.path.join(base_folder, "*.png"))
            
            for face_folder in faces:
                face_folder_name = os.path.basename(face_folder)
                face_images = glob.glob(os.path.join(face_folder, "*.png"))
                
                # 內層雙重迴圈：遍歷資料夾內的每一張圖片
                for base_img_path in base_images:
                    for face_img_path in face_images:
                        try:
                            # 讀取圖片
                            img_base = Image.open(base_img_path).convert("RGBA")
                            img_face = Image.open(face_img_path).convert("RGBA")
                            
                            # 檢查尺寸是否一致 (通常 G00 解出來的都是全畫布尺寸)
                            if img_base.size != img_face.size:
                                # 如果 face 比較小，通常代表它是 crop 過的，需要定位資訊 (這在 G00 已處理成全畫布則不需擔心)
                                # 這裡假設上一部腳本已經輸出全畫布大小的 PNG
                                print(f"  警告: 尺寸不符，跳過 ({base_img_path} vs {face_img_path})")
                                continue

                            # === 關鍵：使用 alpha_composite 處理透明度 ===
                            # 這能確保臉紅 (Blush) 等半透明效果正確疊加
                            result = Image.alpha_composite(img_base, img_face)
                            
                            # 產生輸出檔名
                            # 命名規則: Base檔名_Face檔名.png
                            b_name = os.path.splitext(os.path.basename(base_img_path))[0]
                            f_name = os.path.splitext(os.path.basename(face_img_path))[0]
                            
                            # 組合出比較易讀的檔名
                            # 例如: output/bs1_mk1/base11_001_face01_002.png
                            save_name = f"{base_folder_name}_{b_name}__{face_folder_name}_{f_name}.png"
                            save_path = os.path.join(character_output_dir, save_name)
                            
                            result.save(save_path)
                            
                        except Exception as e:
                            print(f"  合成失敗: {e}")
                            
        print(f"[{prefix}] 合成完成，已存入 {character_output_dir}")

    print("\n所有作業結束。")

if __name__ == "__main__":
    merge_groups()
