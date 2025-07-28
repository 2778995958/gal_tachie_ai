import os
from pykakasi import kakasi

def convert_japanese_filename_to_romaji(filename):
    """
    將檔案名稱中的日文（漢字、平假名、片假名）轉換為羅馬字，
    同時保持數字和底線等結構。
    """
    # 初始化 kakasi
    kks = kakasi()
    
    # 分離主檔名和副檔名
    base_name, extension = os.path.splitext(filename)
    
    # 執行轉換
    result = kks.convert(base_name)
    
    # --- 說明文件 1: 重新設計的組合邏輯 ---
    # pykakasi 會將無法轉換的部分 (如數字, _) 原樣返回。
    # 我們將所有轉換後的部分先組合起來。
    # 例如 "カスミ_統合_93_67" -> "kasumi_tougou_93_67"
    temp_new_base = "".join([part['hepburn'] for part in result])

    # 為了實現像 "Kasumi_Tougou" 這樣的首字母大寫，我們按底線分割後再處理
    final_parts = []
    for component in temp_new_base.split('_'):
        # 只將純文字的部分首字母大寫
        if component and component.isalpha():
            final_parts.append(component.capitalize())
        # 數字或其他部分保持原樣
        else:
            final_parts.append(component)
            
    new_base_name = "_".join(final_parts)

    return f"{new_base_name}{extension}"

def batch_rename_pngs_in_directory(root_dir):
    """
    遍歷指定目錄及其所有子目錄，將所有 .png 檔案的日文名稱轉換為羅馬字。
    """
    # --- 說明文件 2: 檢查目錄是否存在 ---
    if not os.path.isdir(root_dir):
        print(f"錯誤：目錄 '{root_dir}' 不存在。")
        return
        
    print(f"開始掃描目錄：{root_dir}\n")
    renamed_count = 0

    # --- 說明文件 3: 使用 os.walk() 遍歷目錄 ---
    # os.walk 會產生三個值的元組：
    # dirpath: 目前所在的資料夾路徑
    # dirnames: 在 dirpath 中的子資料夾名稱列表
    # filenames: 在 dirpath 中的檔案名稱列表
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for filename in filenames:
            # 檢查檔案是否為 png 檔 (使用 .lower() 來忽略大小寫)
            if filename.lower().endswith('.png'):
                
                # 執行轉換邏輯
                new_filename = convert_japanese_filename_to_romaji(filename)
                
                # 只有在檔名確實有變更時才執行改名
                if new_filename != filename:
                    original_path = os.path.join(dirpath, filename)
                    new_path = os.path.join(dirpath, new_filename)
                    
                    print(f"正在改名: {original_path}")
                    print(f"  -> 新檔名: {new_path}")
                    
                    try:
                        os.rename(original_path, new_path)
                        renamed_count += 1
                    except OSError as e:
                        print(f"錯誤：無法重新命名檔案 {original_path} -> {e}")

    print(f"\n處理完成！總共重新命名了 {renamed_count} 個檔案。")

# --- 主要執行區 ---
if __name__ == "__main__":
    # --- 說明文件 4: 設定你的目標資料夾！ ---
    # 請將這裡的路徑改成你存放 PNG 檔案的根目錄。
    # 使用 '.' 代表目前腳本所在的目錄。
    # 範例 (Windows): target_directory = r"C:\Users\YourUser\Pictures\Japanese_Art"
    # 範例 (Mac/Linux): target_directory = "/Users/youruser/Documents/images"
    
    target_directory = '.' 
    
    # 執行主函數
    batch_rename_pngs_in_directory(target_directory)