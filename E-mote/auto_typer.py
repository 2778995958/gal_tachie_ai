import pyautogui
import time
import keyboard
import threading

def get_user_inputs():
    """
    這個函式負責向使用者取得所有必要的初始數值。
    w 和 d 的值已在此處固定為 1000。
    所有輸入都將被處理為整數。
    """
    print("--- 歡迎使用座標自動輸入工具 (可重複執行版) ---")
    print("(w 和 d 的值已固定為 1000)")
    # 直接設定 w 和 d 的值為整數
    w = 1000
    d = 1000
    while True:
        try:
            x_start = int(input("請輸入初始 x 的值: "))
            y_start = int(input("請輸入初始 y 的值: "))
            
            cols = int(input("請輸入網格的欄數 (例如 2x3 的 2): "))
            rows = int(input("請輸入網格的列數 (例如 2x3 的 3): "))
            
            if cols <= 0 or rows <= 0:
                print("錯誤：欄數和列數必須是大於 0 的整數。請重新輸入。")
                continue
            
            return w, d, x_start, y_start, cols, rows
        except ValueError:
            print("錯誤：輸入的內容必須是整數。請重新輸入。")
        except Exception as e:
            print(f"發生未知錯誤: {e}。請重新輸入。")

def main():
    """
    主執行函式，整合了快速鍵和重複執行功能。
    """
    w, d, x_start, y_start, cols, rows = get_user_inputs()
    
    proceed_event = threading.Event()
    HOTKEY = 'f8' 
    keyboard.add_hotkey(HOTKEY, lambda: proceed_event.set())

    print("\n設定完成！")
    print(f"現在程式將使用 '{HOTKEY}' 作為繼續的快速鍵。")
    print("請在 5 秒內將游標點擊到您要輸入的程式視窗中...")
    time.sleep(5)
    
    # ------------------- 程式碼變更部分 -------------------
    # 這是主執行迴圈，它會一直重複直到手動關閉程式
    run_count = 0
    while True:
        run_count += 1
        print(f"\n--- 準備開始第 {run_count} 輪輸入 ---")
        total_entries = cols * rows
        
        try:
            for r in range(rows):
                for c in range(cols):
                    entry_count = r * cols + c + 1
                    
                    # 將等待快速鍵的邏輯統一放在執行動ˋ作之前
                    proceed_event.clear()
                    print(f"請按下 '{HOTKEY}' 鍵以輸入第 {entry_count}/{total_entries} 組座標...")
                    proceed_event.wait()
                    
                    # 計算並執行輸入
                    target_x = x_start - c * w
                    target_y = y_start - r * d
                    
                    print(f"正在輸入: ({target_x}, {target_y})")
                    
                    pyautogui.write(str(target_x))
                    pyautogui.press('tab')
                    pyautogui.write(str(target_y))
            
            print("\n--- 本輪序列輸入完畢！ ---")
            print(f"你可以移動滑鼠到新的位置，再次按下 '{HOTKEY}' 以重新開始新的一輪。")
            print("若要結束程式，請直接關閉此視窗，或按 Ctrl+C。")

        except pyautogui.FailSafeException:
            print("\n錯誤：PyAutoGUI 安全機制觸發！程式已停止。")
            break # 發生錯誤時跳出迴圈
        except Exception as e:
            print(f"\n程式執行時發生錯誤: {e}")
            break # 發生錯誤時跳出迴圈
    # ----------------------------------------------------

    # 程式結束前清理快速鍵
    keyboard.unhook_all_hotkeys()
    print("程式已結束。")

if __name__ == "__main__":
    main()