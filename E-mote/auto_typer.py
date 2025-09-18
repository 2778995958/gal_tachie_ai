import pyautogui
import time
import keyboard
import threading

def get_user_inputs():
    """
    在程式啟動時，獲取一次使用者輸入。
    """
    print("--- 歡迎使用座標自動輸入工具 (循環版) ---")
    print("請輸入您要循環使用的參數：")
    
    while True:
        try:
            w = int(input("請輸入 w 的值: "))
            d = int(input("請輸入 d 的值: "))
            x_start = int(input("請輸入初始 x 的值: "))
            y_start = int(input("請輸入初始 y 的值: "))
            
            cols = int(input("請輸入網格的欄數: "))
            rows = int(input("請輸入網格的列數: "))
            
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
    主執行函式，每次重複都執行完整的 wdxy->xy 序列。
    """
    # 1. 在所有迴圈開始前，只獲取一次參數
    w, d, x_start, y_start, cols, rows = get_user_inputs()
    
    proceed_event = threading.Event()

    # 2. 只需設定 F8 一個快速鍵
    HOTKEY = 'f8'
    keyboard.add_hotkey(HOTKEY, lambda: proceed_event.set())

    print("\n設定完成！")
    print(f"現在程式將使用 '{HOTKEY}' 作為唯一的控制鍵。")
    print("你可以開始操作了。")

    # 3. 簡化為單一的無限迴圈
    run_count = 0
    while True:
        run_count += 1
        print(f"\n--- 準備開始第 {run_count} 輪輸入 ---")
        total_entries = cols * rows
        
        try:
            for r in range(rows):
                for c in range(cols):
                    entry_count = r * cols + c + 1
                    
                    proceed_event.clear()
                    print(f"請按下 '{HOTKEY}' 鍵以輸入第 {entry_count}/{total_entries} 組座標...")
                    proceed_event.wait()
                    
                    target_x = x_start - c * w
                    target_y = y_start - r * d
                    
                    # 4. 判斷邏輯簡化：只看是否為網格的起點
                    is_first_entry = (r == 0 and c == 0)
                    if is_first_entry:
                        print(f"正在輸入起始點 (WDXY): {w}, {d}, {target_x}, {target_y}")
                        pyautogui.press('tab')
                        pyautogui.write(str(w))
                        pyautogui.press('tab')
                        pyautogui.write(str(d))
                        pyautogui.press('tab')
                        pyautogui.write(str(target_x))
                        pyautogui.press('tab')
                        pyautogui.write(str(target_y))
                    else:
                        print(f"正在輸入後續點 (XY): {target_x}, {target_y}")
                        pyautogui.press('tab')
                        pyautogui.press('tab')
                        pyautogui.press('tab')
                        pyautogui.write(str(target_x))
                        pyautogui.press('tab')
                        pyautogui.write(str(target_y))

            print("\n--- 本輪序列輸入完畢！ ---")
            print(f" -> 請按下 '{HOTKEY}' 鍵以 [完整重複] 新的一輪。")
            print(" -> 若要結束程式，請直接關閉此視窗。")

        except Exception as e:
            print(f"\n程式執行時發生錯誤: {e}")
            break

    keyboard.unhook_all_hotkeys()
    print("程式已結束。")

if __name__ == "__main__":
    main()