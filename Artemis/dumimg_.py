# 匯入所需模組
import os  # 用於處理檔案和目錄路徑 (Operating System)
import shutil  # 用於移動檔案等進階檔案操作 (Shell Utilities)
from collections import defaultdict  # 匯入 defaultdict，這是一種特殊的字典，處理起來更方便

# --- 1. 請在這裡設定你的通用規則 ---
# 這是整個腳本最重要的設定部分，你可以根據自己的需求修改

# !! 關鍵設定：定義資料夾的優先級順序 !!
# 腳本會優先保留列表中「最靠前」的資料夾中的版本。
# 例如，如果一個檔案同時存在於 z2 和 z1，腳本會保留 z2 的版本，移動 z1 的版本。
PRIORITY_ORDER = ['z2', 'z1', 'no', 'fa', 'bc']

# 設定用來存放重複圖片的資料夾名稱
DUPLICATE_FOLDER_NAME = 'dupimg'


# --- 2. 核心處理邏輯 ---
# 這部分是核心功能的函式，通常設定好之後就不需要再修改

def get_identifier_from_filename(filename, character_name, action_name):
    """
    這是一個輔助函式，功能是從一個完整的檔名中，提取出獨特的「後綴識別碼」。
    例如：從 'fei_z1a0000_a0001.png' (在 'z1' 資料夾中) 提取出 'a0000_a0001.png'。
    """
    # 根據規則，構成檔名前綴，例如 'fei_z1'
    prefix = f"{character_name}_{action_name}"

    # 檢查檔名是否以此前綴開頭
    if filename.startswith(prefix):
        # 如果是，就返回前綴之後的所有部分，這就是我們要比對的後綴
        return filename[len(prefix):]
    
    # 如果檔名格式不符，則返回 None (代表沒有找到識別碼)
    return None

def process_character(character_folder):
    """
    這是處理「單一角色」的核心函式。
    它會對傳入的角色資料夾，執行完整的優先級排序與檔案移動邏輯。
    """
    # 印出分隔線和標題，讓執行日誌更清晰
    print(f"\n=============================================")
    print(f"=== 開始處理角色資料夾: {character_folder} ===")
    print(f"=============================================")
    
    # --- 第一步：建立所有檔案的索引地圖 (Index Map) ---
    # 使用 defaultdict 可以讓我們方便地對一個鍵直接附加 (append) 值，即使那個鍵是第一次出現。
    # 這樣就不需要每次都檢查鍵是否存在。
    identifier_map = defaultdict(list)
    print(f"步驟 1: 正在為 '{character_folder}' 建立檔案索引...")
    
    # 遍歷當前角色資料夾下的所有項目 (可能是檔案或資料夾)
    for subfolder_name in os.listdir(character_folder):
        # 只處理在我們優先級清單中定義的資料夾，忽略其他無關的資料夾或檔案。
        if subfolder_name not in PRIORITY_ORDER:
            continue
        
        # 組成完整的子資料夾路徑
        current_subfolder_path = os.path.join(character_folder, subfolder_name)
        # 再次確認這確實是一個資料夾
        if not os.path.isdir(current_subfolder_path):
            continue

        # 遍歷子資料夾中的所有檔案
        for filename in os.listdir(current_subfolder_path):
            # 確認這是一個檔案，而不是資料夾
            if not os.path.isfile(os.path.join(current_subfolder_path, filename)):
                continue
            
            # 呼叫輔助函式，從檔名中提取後綴識別碼
            identifier = get_identifier_from_filename(filename, character_folder, subfolder_name)
            # 如果成功提取到識別碼
            if identifier:
                # 就將這個子資料夾的名稱，加入到這個識別碼對應的列表中
                # 例如：identifier_map['a0001.png'].append('z2')
                identifier_map[identifier].append(subfolder_name)

    print(f"索引建立完成，共找到 {len(identifier_map)} 個獨立的圖片後綴。")

    # --- 第二步：根據優先級，決策並移動檔案 ---
    print(f"步驟 2: 正在根據優先級規則，檢查並移動重複檔案...")
    total_moved_count = 0
    duplicate_base_path = os.path.join(character_folder, DUPLICATE_FOLDER_NAME)

    # 遍歷剛剛建立的索引地圖
    for identifier, found_in_folders in identifier_map.items():
        # 如果一個圖片後綴只在一個地方出現，代表它沒有重複，直接跳過，處理下一個。
        if len(found_in_folders) <= 1:
            continue
            
        folder_to_keep = None
        # 根據我們的優先級列表 PRIORITY_ORDER，來決定要保留哪個資料夾的版本
        for priority_folder in PRIORITY_ORDER:
            # 檢查這個優先級較高的資料夾，是否存在於找到的資料夾列表中
            if priority_folder in found_in_folders:
                # 如果存在，那它就是我們要保留的目標
                folder_to_keep = priority_folder
                # 找到了最高優先級的，就不需要再往下找了，直接跳出這個迴圈。
                break
        
        # 如果成功找到了要保留的資料夾
        if folder_to_keep:
            # 就再次遍歷所有發現了這個檔案的資料夾
            for folder_to_move in found_in_folders:
                # 如果這個資料夾正是我們要保留的那個，就跳過它
                if folder_to_move == folder_to_keep:
                    continue
                
                # 對於其他需要被移動的檔案，重建它的原始檔名和路徑
                original_filename = f"{character_folder}_{folder_to_move}{identifier}"
                source_path = os.path.join(character_folder, folder_to_move, original_filename)
                
                # 建立它將被移動到的目標路徑
                destination_dir = os.path.join(duplicate_base_path, folder_to_move)
                destination_path = os.path.join(destination_dir, original_filename)

                # 【關鍵安全檢查】在移動之前，檢查目標位置是否已經有同名檔案了
                if os.path.exists(destination_path):
                    # 如果有，就跳過這次移動，並印出提示
                    print(f"  - 跳過 [{original_filename}]，目標位置已存在檔案。")
                    continue

                # 檢查原始檔案是否存在 (以防萬一)
                if os.path.exists(source_path):
                    # 確保目標資料夾存在，如果不存在就自動建立它 (exist_ok=True 參數很有用)
                    os.makedirs(destination_dir, exist_ok=True)
                    print(f"  - 移動 [{original_filename}] 從 '{folder_to_move}' 資料夾...")
                    # 執行移動操作
                    shutil.move(source_path, destination_path)
                    total_moved_count += 1

    print(f"\n'{character_folder}' 處理完成！總共移動了 {total_moved_count} 個檔案。")

def main():
    """
    這是整個腳本的主執行函式 (Entry Point)。
    它的工作是自動掃描當前目錄，並對所有找到的角色資料夾，呼叫 process_character 函式進行處理。
    """
    print("開始自動掃描目錄以尋找角色資料夾...")
    
    # 找出當前目錄下所有的項目，並篩選出其中的「資料夾」
    candidate_folders = [item for item in os.listdir('.') if os.path.isdir(item)]
    characters_to_process = []
    
    # 遍歷所有候選資料夾
    for folder in candidate_folders:
        # 忽略我們自己建立的備份資料夾，不要處理它
        if folder == DUPLICATE_FOLDER_NAME:
            continue
        # 判斷依據：資料夾內部是否至少包含一個我們在 PRIORITY_ORDER 中定義的資料夾
        for priority_folder in PRIORITY_ORDER:
            # 如果找到了，就代表這是一個合格的角色資料夾
            if os.path.isdir(os.path.join(folder, priority_folder)):
                # 將其加入到待處理列表中
                characters_to_process.append(folder)
                # 同樣地，找到一個就夠了，跳出內層迴圈，去檢查下一個候選資料夾
                break
                
    # 如果掃描完後，一個合格的角色資料夾都沒找到
    if not characters_to_process:
        print("錯誤：在當前目錄下未找到任何可處理的角色資料夾。")
        print(f"一個可處理的資料夾應至少包含以下子資料夾之一：{PRIORITY_ORDER}")
        return # 結束程式

    # 告訴使用者我們找到了哪些資料夾準備處理
    print(f"掃描完畢，找到 {len(characters_to_process)} 個待處理的角色資料夾: {', '.join(characters_to_process)}")
    
    # 逐一處理所有找到的角色資料夾
    for character in characters_to_process:
        process_character(character)
        
    # 所有任務都完成後，印出結束訊息
    print("\n=============================================")
    print("=== 所有任務已全部完成！ ===")
    print("=============================================")

# 這是一個 Python 的標準寫法
# 意思是，只有當這個 .py 檔案是「直接被執行」時，才執行 main() 函式。
# 如果這個檔案是被其他 Python 腳本作為模組匯入 (import)，則不會自動執行 main()。
if __name__ == "__main__":
    main()