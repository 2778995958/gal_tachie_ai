import os
import shutil

# --- 設定區 (請根據你的情況修改這裡) ---

# 1. 來源資料夾：存放你所有圖片的地方
#    '.' 代表程式碼檔案所在的目前資料夾
#    你也可以指定絕對路徑，例如 'C:/Users/YourUser/Desktop/images'
SOURCE_DIRECTORY = '.' 

# 2. 目標資料夾：用來存放「不符合規則」的檔案
DEST_DIRECTORY = 'notuse'

# --- 主要程式邏輯區 (通常不需要修改) ---

def process_and_move_files_by_rule():
    """
    主程式函式：根據「每5組留最後一組」的規則處理檔案分類與移動
    """
    print("--- 檔案分類程式 ---")
    print("規則：在每5個一組的編號中，只保留最後一個 (即號碼 % 5 == 4 的檔案)")
    print(f"來源資料夾: {os.path.abspath(SOURCE_DIRECTORY)}")
    
    # 建立目標資料夾 (如果不存在的話)
    dest_path_full = os.path.join(SOURCE_DIRECTORY, DEST_DIRECTORY)
    os.makedirs(dest_path_full, exist_ok=True)
    print(f"不符合規則的檔案將被移動到: {dest_path_full}\n")

    # 取得來源資料夾中的所有檔案和資料夾名稱
    try:
        all_items = os.listdir(SOURCE_DIRECTORY)
    except FileNotFoundError:
        print(f"錯誤：找不到來源資料夾 '{SOURCE_DIRECTORY}'。請檢查路徑是否正確。")
        return

    # 遍歷所有項目
    for item_name in all_items:
        # 組合出完整的來源路徑
        source_item_path = os.path.join(SOURCE_DIRECTORY, item_name)

        # 只處理檔案，跳過資料夾 (例如我們剛建立的 notuse 資料夾)
        if not os.path.isfile(source_item_path):
            continue

        # 檔名必須至少有8個字元才能從中提取ID
        if len(item_name) < 8:
            continue
            
        # 提取檔名的後4碼作為判斷依據 (檔名第4到第8字元)
        sequence_str = item_name[4:8]
        
        try:
            # 將後4碼字串轉換為整數
            sequence_num = int(sequence_str)
            
            # 核心規則：檢查數字除以5的餘數是否為4
            if sequence_num % 5 == 4:
                # 如果是，就保留不動，並印出訊息
                print(f"✅ 保留檔案： {item_name} (規則: {sequence_num} % 5 == 4)")
            else:
                # 如果不是，就移動檔案
                dest_file_path = os.path.join(dest_path_full, item_name)
                shutil.move(source_item_path, dest_file_path)
                print(f"➡️ 移動檔案： {item_name} (規則: {sequence_num} % 5 != 4)")
        except ValueError:
            # 如果後4碼不是純數字 (例如 'P000')，就直接移動
            dest_file_path = os.path.join(dest_path_full, item_name)
            shutil.move(source_item_path, dest_file_path)
            print(f"➡️ 移動檔案： {item_name} (原因: 後4碼非數字序列)")
        except Exception as e:
            print(f"處理檔案 {item_name} 時發生未知錯誤: {e}")

# --- 執行程式 ---
if __name__ == "__main__":
    process_and_move_files_by_rule()
    print("\n處理完成！")