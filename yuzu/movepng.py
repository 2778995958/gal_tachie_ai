import os
import shutil

def move_files_by_keywords():
    """
    根據使用者輸入的來源、目標路徑與關鍵字，遍歷並移動檔案。
    單次執行的核心功能。
    """
    # 1. 由使用者輸入來源與目標資料夾路徑
    print("\n======================================================")
    print("新的檔案移動任務")
    print("======================================================")

    # 技巧: `or 'output'` 表示如果使用者直接按 Enter，則使用預設值 'output'
    source_dir = input("👉 請輸入【來源資料夾】的路徑 (預設為 'output'): ") or 'output'
    dest_dir = input("👉 請輸入【目標資料夾】的路徑 (預設為 'finaloutput'): ") or 'finaloutput'

    # 檢查來源資料夾是否存在
    if not os.path.isdir(source_dir):
        print(f"\n❌ 錯誤：來源資料夾 '{source_dir}' 不存在，請檢查路徑是否正確。任務已取消。")
        return

    # 2. 取得使用者輸入的關鍵字
    print("------------------------------------------------------")
    print(f"準備從 '{source_dir}' 資料夾中尋找檔案...")
    print(f"符合條件的檔案將被移動到 '{dest_dir}' 資料夾。")
    print("------------------------------------------------------")
    
    keywords_input = input("👉 請輸入要篩選的關鍵字，用逗號分隔 (例如: bb,cc,vv,nn): ")
    
    # 將輸入的字串分割成一個列表，並移除每個關鍵字前後可能存在的空格和空字串
    keywords_to_find = [keyword.strip() for keyword in keywords_input.split(',') if keyword.strip()]
    
    if not keywords_to_find:
        print("\n❌ 沒有輸入任何有效的關鍵字，任務已取消。")
        return

    print(f"\n🔍 正在尋找檔名中包含以下任一關鍵字的圖片: {keywords_to_find}\n")

    # 3. 確保目標資料夾存在，如果不存在就建立它
    os.makedirs(dest_dir, exist_ok=True)

    moved_count = 0
    # 4. 遍歷來源資料夾及其所有子資料夾
    for root, dirs, files in os.walk(source_dir):
        for filename in files:
            file_base, file_ext = os.path.splitext(filename)
            parts = file_base.split('_')
            
            # 5. 檢查檔案名稱的片段是否包含任何一個關鍵字
            if not set(parts).isdisjoint(keywords_to_find):
                source_path = os.path.join(root, filename)
                destination_path = os.path.join(dest_dir, filename)
                
                # 6. 移動檔案
                try:
                    shutil.move(source_path, destination_path)
                    print(f"✅ 已移動檔案: {filename}")
                    moved_count += 1
                except Exception as e:
                    print(f"❌ 移動檔案 {filename} 時發生錯誤: {e}")

    print("\n======================================================")
    if moved_count > 0:
        print(f"🎉 任務完成！總共移動了 {moved_count} 個檔案到 '{dest_dir}' 資料夾。")
    else:
        print(f"📂 任務完成，但沒有找到符合條件的檔案。")
    print("======================================================")


# --- 主程式執行區塊 ---
if __name__ == "__main__":
    # 使用一個無限迴圈讓程式可以重複執行
    while True:
        # 執行一次移動任務
        move_files_by_keywords()

        # 詢問使用者是否要繼續
        print("\n------------------------------------------------------")
        # .lower() 可以將輸入的 'Y' 也視為 'y'
        continue_choice = input("👉 是否要執行新的移動任務？(輸入 y 繼續，或按任意其他鍵結束): ").lower()

        # 如果輸入的不是 'y'，就跳出迴圈，結束程式
        if continue_choice != 'y':
            print("👋 感謝使用，程式已結束。")
            break