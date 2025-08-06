import os
import shutil

# --- 不需要手動設定路徑 ---

# 1. 取得此腳本的絕對路徑
script_path = os.path.abspath(__file__)

# 2. 取得此腳本所在的目錄路徑 (這就是我們要處理的資料夾)
current_directory = os.path.dirname(script_path)

# 3. 取得腳本本身的檔案名稱，這樣我們才不會移動到它自己
script_name = os.path.basename(script_path)

print(f"準備處理目錄: {current_directory}")
print("==========================================")

# 4. 遍歷當前目錄下的所有項目
for filename in os.listdir(current_directory):
    
    # 組合出完整的檔案路徑
    full_path = os.path.join(current_directory, filename)

    # 5. 檢查這是不是一個檔案，並且不是這個腳本自己
    if os.path.isfile(full_path) and filename != script_name:
        
        # 6. 檢查檔案名稱中是否包含底線
        if '_' in filename:
            # 取得第一個底線前的名稱作為資料夾名稱
            folder_name = filename.split('_')[0]
            
            # 7. 建立目標資料夾的路徑
            target_folder_path = os.path.join(current_directory, folder_name)
            
            # 如果目標資料夾不存在，就建立它
            if not os.path.exists(target_folder_path):
                print(f"建立新資料夾: {folder_name}")
                os.makedirs(target_folder_path)
            
            # 8. 移動檔案
            destination_path = os.path.join(target_folder_path, filename)
            print(f"正在移動檔案: {filename} -> {folder_name}/")
            shutil.move(full_path, destination_path)
        else:
            # 如果檔名沒有底線，則跳過
            print(f"檔案 '{filename}' 沒有底線，跳過處理。")


print("==========================================")
print("所有檔案分類完成！")