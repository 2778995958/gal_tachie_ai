import os
import shutil

# 這是你要整理的資料夾路徑
# '.' 代表目前資料夾，也就是你執行這個 python 檔案的地方
source_directory = '.'

print(f"開始整理資料夾: {os.path.abspath(source_directory)}")

# 取得資料夾中所有檔案的列表
try:
    all_files = os.listdir(source_directory)
except FileNotFoundError:
    print(f"錯誤：找不到資料夾 '{source_directory}'。請檢查路徑是否正確。")
    exit()

# 遍歷所有檔案
for filename in all_files:
    # 檢查檔案是否為 .png 檔案且名稱中包含 '_'
    if filename.endswith('.png') and '_' in filename:
        
        # 1. 解析檔名，取得 '_' 前面的部分作為資料夾名稱
        #    例如： 'xxxa_image01.png' -> 'xxxa'
        folder_name = filename.split('_')[0]
        
        # 2. 建立目標資料夾的路徑
        destination_folder = os.path.join(source_directory, folder_name)
        
        # 3. 檢查目標資料夾是否存在，如果不存在就建立一個
        if not os.path.exists(destination_folder):
            print(f"建立新資料夾: {destination_folder}")
            os.makedirs(destination_folder)
            
        # 4. 組合檔案的原始路徑和目標路徑
        source_path = os.path.join(source_directory, filename)
        destination_path = os.path.join(destination_folder, filename)
        
        # 5. 移動檔案
        try:
            shutil.move(source_path, destination_path)
            print(f"已移動 '{filename}' 到 '{folder_name}' 資料夾")
        except Exception as e:
            print(f"移動 '{filename}' 時發生錯誤: {e}")

print("整理完畢！")