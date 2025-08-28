import pygetwindow as gw
import pyautogui
import time

# 設定你想要尋找的視窗標題關鍵字
target_title_keyword = "[AFK1]"

# 設定你想要移動到的新座標 (X, Y)
new_position_x = 0
new_position_y = 0

# 設定你想要修改的視窗尺寸 (寬 x 高)
new_width = 1080
new_height = 1620

def find_move_and_resize_with_pyautogui(title_keyword, x, y, width, height):
    """
    使用 pyautogui 尋找、移動並修改視窗尺寸。
    """
    try:
        found_window = None
        all_windows = gw.getAllWindows()
        for window in all_windows:
            if title_keyword in window.title:
                found_window = window
                break # 找到第一個符合的視窗就跳出迴圈

        if found_window:
            print(f"找到視窗：'{found_window.title}'")
            print(f"目前位置與尺寸：({found_window.left}, {found_window.top}) {found_window.width}x{found_window.height}")

            # 確保視窗是可見的
            found_window.activate()

            # 使用 pyautogui 的方法取得視窗物件
            pyautogui_window = pyautogui.getWindowsWithTitle(found_window.title)[0]

            # 移動視窗到新的位置
            pyautogui_window.moveTo(x, y)

            # 調整視窗尺寸
            pyautogui_window.resizeTo(width, height)

            # 等待一秒讓作業系統完成操作
            time.sleep(1)
            
            # 重新取得視窗資訊來驗證
            final_window = gw.getWindowsWithTitle(found_window.title)[0]
            print(f"視窗已移動並調整為：({final_window.left}, {final_window.top}) {final_window.width}x{final_window.height}")
            print("操作完成。")
            return True
        else:
            print(f"沒有找到標題包含 '{title_keyword}' 的視窗。")
            return False

    except Exception as e:
        print(f"發生錯誤：{e}")
        return False

# 執行函式
find_move_and_resize_with_pyautogui(target_title_keyword, new_position_x, new_position_y, new_width, new_height)