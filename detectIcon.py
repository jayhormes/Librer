import cv2
import pyautogui
import numpy as np
import time

def find_image_with_scaling(template_path, region, scale_steps=10, scale_range=(0.95, 1.05), confidence=0.85):
    """
    在指定區域內尋找一個可能輕微縮放的圖片。
    
    Args:
        template_path (str): 要尋找的圖片檔案路徑。
        region (tuple): 搜尋區域，格式為 (x, y, width, height)。
        scale_steps (int): 縮放的步數。
        scale_range (tuple): 縮放範圍，例如 (0.95, 1.05)。
        confidence (float): 匹配的最低信心水準 (0.0 ~ 1.0)。
        
    Returns:
        tuple or None: 如果找到，返回 (x, y)，否則返回 None。
    """
    # 載入模板圖片
    template_img = cv2.imread(template_path, 0)
    if template_img is None:
        print(f"錯誤：無法載入模板圖片 '{template_path}'")
        return None

    screenshot = pyautogui.screenshot(region=region)
    screenshot_np = np.array(screenshot)
    screenshot_gray = cv2.cvtColor(screenshot_np, cv2.COLOR_BGR2GRAY)

    found_location = None
    max_corr = -1
    best_scale = None
    
    # 進行多重縮放比對
    for scale in np.linspace(scale_range[0], scale_range[1], scale_steps):
        w, h = template_img.shape[::-1]
        resized_template = cv2.resize(template_img, (int(w * scale), int(h * scale)))

        res = cv2.matchTemplate(screenshot_gray, resized_template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

        if max_val > max_corr:
            max_corr = max_val
            top_left = max_loc
            found_location = (top_left[0] + region[0], top_left[1] + region[1])
            best_scale = scale

    if max_corr >= confidence:
        # 回傳找到的圖片左上角座標和當時的最佳縮放比例
        return found_location, best_scale
    else:
        return None, None


# --- 參數設定 ---
search_region = (800, 800, 300, 300)
image_to_find = 'target.png'
search_interval = 1 # 每次搜尋的間隔秒數
image_width, image_height = cv2.imread(image_to_find, 0).shape[::-1]

# --- 執行無限循環搜尋 ---
try:
    while True:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}] 正在搜尋圖片...")
        location, best_scale  = find_image_with_scaling(image_to_find, search_region)

        if location:
            # 找到圖片後，計算中心點並點擊
            center_x = location[0] + (image_width * best_scale) / 2
            center_y = location[1] + (image_height * best_scale) / 2
            
            print(f"找到了！圖片位置在：({location[0]}, {location[1]})")
            #print(f"點擊圖片中心點：({center_x:.0f}, {center_y:.0f})")

            # 點擊中心點
            #pyautogui.click(center_x, center_y)

            # 點擊後可以選擇暫停或跳出迴圈
            # 如果你只想點擊一次，可以在這裡使用 break
            # break 
        else:
            print("未找到圖片。")

except KeyboardInterrupt:
    print("\n程式已手動停止。")