import cv2
import pyautogui
import numpy as np
import time
import math
import random
import pygetwindow as gw
from config import *

def show_menu():
    """顯示主選單"""
    print("\n" + "="*50)
    print("          圖標偵測與箭頭追蹤系統")
    print("="*50)
    print("1. 調整遊戲窗口大小和位置")
    print("2. 開始圖標偵測")
    print("3. 查看當前配置")
    print("4. 退出程式")
    print("="*50)

def resize_game_window():
    """調整遊戲窗口大小和位置"""
    print(f"\n正在尋找標題包含 '{TARGET_TITLE_KEYWORD}' 的窗口...")
    
    try:
        found_window = None
        all_windows = gw.getAllWindows()
        for window in all_windows:
            if TARGET_TITLE_KEYWORD in window.title:
                found_window = window
                break

        if found_window:
            print(f"找到視窗：'{found_window.title}'")
            print(f"目前位置與尺寸：({found_window.left}, {found_window.top}) {found_window.width}x{found_window.height}")

            # 確保視窗是可見的
            found_window.activate()

            # 使用 pyautogui 的方法取得視窗物件
            pyautogui_window = pyautogui.getWindowsWithTitle(found_window.title)[0]

            # 移動視窗到新的位置
            pyautogui_window.moveTo(WINDOW_POSITION_X, WINDOW_POSITION_Y)

            # 調整視窗尺寸
            pyautogui_window.resizeTo(WINDOW_WIDTH, WINDOW_HEIGHT)

            # 等待一秒讓作業系統完成操作
            time.sleep(1)
            
            # 重新取得視窗資訊來驗證
            final_window = gw.getWindowsWithTitle(found_window.title)[0]
            print(f"視窗已移動並調整為：({final_window.left}, {final_window.top}) {final_window.width}x{final_window.height}")
            print("窗口調整完成！")
            return True
        else:
            print(f"沒有找到標題包含 '{TARGET_TITLE_KEYWORD}' 的視窗。")
            print("請確認遊戲已開啟且窗口標題正確。")
            return False

    except Exception as e:
        print(f"調整窗口時發生錯誤：{e}")
        return False

def show_config():
    """顯示當前配置"""
    print("\n" + "="*50)
    print("           當前配置")
    print("="*50)
    print(f"目標窗口關鍵字: {TARGET_TITLE_KEYWORD}")
    print(f"窗口位置: ({WINDOW_POSITION_X}, {WINDOW_POSITION_Y})")
    print(f"窗口尺寸: {WINDOW_WIDTH} x {WINDOW_HEIGHT}")
    print(f"目標圖標: {TARGET_IMAGE_PATH}")
    print(f"人物圖標: {CHARACTER_IMAGE_PATH}")
    print(f"圖標搜尋區域: {ICON_SEARCH_REGION}")
    print(f"人物搜尋區域: {CHARACTER_SEARCH_REGION}")
    print(f"圖標信心度: {ICON_CONFIDENCE}")
    print(f"人物信心度: {CHARACTER_CONFIDENCE}")
    print(f"箭頭搜尋半徑: {ARROW_SEARCH_RADIUS}")
    print(f"拖曳距離: {DRAG_DISTANCE}")
    print(f"拖曳時間: {DRAG_HOLD_SECONDS} 秒")
    print(f"最大箭頭嘗試: {MAX_ARROW_ATTEMPTS} 次")
    print("="*50)

def circular_mean_deg(angles_deg):
    """對 0°=上、順時針 的角度做圓形平均，回傳平均角度（度）。"""
    if not angles_deg:
        return None
    sum_x = sum(math.sin(math.radians(a)) for a in angles_deg)
    sum_y = sum(math.cos(math.radians(a)) for a in angles_deg)
    if sum_x == 0 and sum_y == 0:
        return None
    mean_rad = math.atan2(sum_x, sum_y)
    return (math.degrees(mean_rad) + 360) % 360

def clamp_region_to_screen(x, y, w, h):
    """將擷取區域夾在螢幕邊界內且為整數，寬高最少為 1。"""
    sw, sh = pyautogui.size()
    x = int(round(max(0, min(x, sw - 1))))
    y = int(round(max(0, min(y, sh - 1))))
    # 防止超出邊界
    w = int(round(max(1, min(w, sw - x))))
    h = int(round(max(1, min(h, sh - y))))
    return x, y, w, h

class ImageDetector:
    """圖標偵測器"""
    
    def __init__(self, template_path, search_region, confidence=None):
        self.template_path = template_path
        self.search_region = search_region
        self.confidence = confidence if confidence is not None else ICON_CONFIDENCE
        
        # 載入模板圖片
        self.template_img = cv2.imread(template_path, 0)
        if self.template_img is None:
            print(f"錯誤：無法載入模板圖片 '{template_path}'")
            raise ValueError(f"無法載入圖片: {template_path}")
        
        self.template_width, self.template_height = self.template_img.shape[::-1]
    
    def find_image_with_scaling(self, scale_steps=None, scale_range=None):
        """
        在指定區域內尋找一個可能輕微縮放的圖片
        """
        if scale_steps is None:
            scale_steps = ICON_SCALE_STEPS
        if scale_range is None:
            scale_range = ICON_SCALE_RANGE
            
        screenshot = pyautogui.screenshot(region=self.search_region)
        screenshot_np = np.array(screenshot)
        screenshot_gray = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2GRAY)

        found_location = None
        max_corr = -1
        best_scale = None
        
        # 進行多重縮放比對
        for scale in np.linspace(scale_range[0], scale_range[1], scale_steps):
            w, h = self.template_img.shape[::-1]
            resized_template = cv2.resize(self.template_img, (int(w * scale), int(h * scale)))

            res = cv2.matchTemplate(screenshot_gray, resized_template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

            if max_val > max_corr:
                max_corr = max_val
                top_left = max_loc
                found_location = (top_left[0] + self.search_region[0], top_left[1] + self.search_region[1])
                best_scale = scale

        if max_corr >= self.confidence:
            return found_location, best_scale
        else:
            return None, None
    
    def get_center_position(self, location, scale):
        """取得圖片中心位置"""
        if location and scale:
            center_x = location[0] + (self.template_width * scale) / 2
            center_y = location[1] + (self.template_height * scale) / 2
            return center_x, center_y
        return None, None
    
    def click_center(self, location, scale):
        """點擊圖片中心（加入隨機偏移）"""
        center_x, center_y = self.get_center_position(location, scale)
        if center_x and center_y:
            # 在中心點附近20像素範圍內隨機偏移
            random_offset_x = random.randint(-20, 20)
            random_offset_y = random.randint(-20, 20)
            
            # 計算最終點擊位置
            click_x = center_x + random_offset_x
            click_y = center_y + random_offset_y
            
            # 確保點擊位置在螢幕範圍內
            screen_width, screen_height = pyautogui.size()
            click_x = max(0, min(screen_width - 1, click_x))
            click_y = max(0, min(screen_height - 1, click_y))
            
            print(f"點擊圖片中心點：({center_x:.0f}, {center_y:.0f})，隨機偏移：({random_offset_x}, {random_offset_y})，最終位置：({click_x:.0f}, {click_y:.0f})")
            pyautogui.click(click_x, click_y)
            return True
        return False


class ArrowDetector:
    """箭頭偵測器"""
    
    def __init__(self, character_template_path, search_region, arrow_search_radius=None):
        self.character_template_path = character_template_path
        self.search_region = search_region
        self.arrow_search_radius = arrow_search_radius if arrow_search_radius is not None else ARROW_SEARCH_RADIUS
        
        # 載入人物模板圖片
        self.template_img = cv2.imread(character_template_path, 0)
        if self.template_img is None:
            print(f"錯誤：無法載入人物模板圖片 '{character_template_path}'")
            raise ValueError(f"無法載入圖片: {character_template_path}")
        
        self.template_width, self.template_height = self.template_img.shape[::-1]
    
    def find_character(self, scale_steps=None, scale_range=None, confidence=None):
        """尋找人物位置"""
        if scale_steps is None:
            scale_steps = CHARACTER_SCALE_STEPS
        if scale_range is None:
            scale_range = CHARACTER_SCALE_RANGE
        if confidence is None:
            confidence = CHARACTER_CONFIDENCE
            
        rx, ry, rw, rh = self.search_region
        rx, ry, rw, rh = int(round(rx)), int(round(ry)), int(round(rw)), int(round(rh))

        screenshot = pyautogui.screenshot(region=(rx, ry, rw, rh))
        screenshot_np = np.array(screenshot)
        screenshot_gray = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2GRAY)

        found_location = None
        max_corr = -1.0
        best_scale = None

        th, tw = self.template_img.shape[:2]

        for scale in np.linspace(scale_range[0], scale_range[1], scale_steps):
            w = max(1, int(round(tw * scale)))   # 確保至少 1
            h = max(1, int(round(th * scale)))
            resized_template = cv2.resize(self.template_img, (w, h))

            # 模板不可比搜尋圖還大
            if h > screenshot_gray.shape[0] or w > screenshot_gray.shape[1]:
                continue

            res = cv2.matchTemplate(screenshot_gray, resized_template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)

            if max_val > max_corr:
                max_corr = max_val
                top_left = max_loc
                found_location = (top_left[0] + rx, top_left[1] + ry)
                best_scale = scale

        if max_corr >= confidence and found_location is not None:
            return found_location, best_scale
        else:
            return None, None
    
    def find_arrow_by_color(self, search_center_x, search_center_y, min_area=None):
        """通過顏色偵測箭頭"""
        if min_area is None:
            min_area = ARROW_MIN_AREA
            
        # 擷取區域（人物為中心的方形窗）
        sx = search_center_x - self.arrow_search_radius
        sy = search_center_y - self.arrow_search_radius
        sw = sh = self.arrow_search_radius * 2
        sx, sy, sw, sh = clamp_region_to_screen(sx, sy, sw, sh)

        try:
            pil_img = pyautogui.screenshot(region=(sx, sy, sw, sh))
        except pyautogui.PyAutoGUIException:
            return None, None, None

        img = np.array(pil_img)
        hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)

        # 紅色兩段
        mask1 = cv2.inRange(hsv, (0, 80, 80), (10, 255, 255))
        mask2 = cv2.inRange(hsv, (170, 80, 80), (180, 255, 255))
        mask = cv2.bitwise_or(mask1, mask2)

        # 降噪
        mask = cv2.medianBlur(mask, 3)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)

        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        best = None
        best_score = -1
        for c in cnts:
            area = cv2.contourArea(c)
            if area < min_area:
                continue

            x, y, w, h = cv2.boundingRect(c)
            rect_area = w * h or 1
            extent = area / rect_area
            if not (0.35 <= extent <= 0.90):
                continue

            hull = cv2.convexHull(c)
            hull_area = cv2.contourArea(hull) or 1
            solidity = area / hull_area
            if solidity < 0.75:
                continue

            peri = cv2.arcLength(c, True) or 1
            circularity = 4 * math.pi * area / (peri * peri)
            if circularity > 0.8:
                continue

            score = area * (0.5 + 0.3 * extent + 0.2 * solidity)
            if score > best_score:
                best_score = score
                best = c

        if best is None:
            return None, None, None

        # 箭頭質心
        M = cv2.moments(best)
        if M["m00"] == 0:
            return None, None, None
        cx_local = M["m10"] / M["m00"]
        cy_local = M["m01"] / M["m00"]

        # 轉成全螢幕座標
        cx = cx_local + sx
        cy = cy_local + sy

        # 方向角
        dx = cx - search_center_x
        dy = cy - search_center_y
        angle_deg = (math.degrees(math.atan2(dx, -dy)) + 360) % 360

        x, y, w, h = cv2.boundingRect(best)
        top_left_global = (int(x + sx), int(y + sy))

        return top_left_global, 1.0, angle_deg
    
    def wait_for_arrow(self, center_x, center_y, timeout=None, poll=None, min_hits=None, min_area=None):
        """
        在 timeout 秒內重複偵測箭頭，蒐集角度並做圓形平均。
        回傳：(arrow_location, avg_angle, hits_count)；若失敗回傳 (None, None, 0)
        """
        if timeout is None:
            timeout = ARROW_DETECTION_TIMEOUT
        if poll is None:
            poll = ARROW_POLL_INTERVAL
        if min_hits is None:
            min_hits = ARROW_MIN_HITS
        if min_area is None:
            min_area = ARROW_MIN_AREA
            
        angles = []
        last_loc = None
        t0 = time.time()
        while time.time() - t0 < timeout:
            loc, _, ang = self.find_arrow_by_color(center_x, center_y, min_area=min_area)
            if loc is not None and ang is not None:
                angles.append(ang)
                last_loc = loc
            time.sleep(poll)
        if len(angles) >= min_hits:
            return last_loc, circular_mean_deg(angles), len(angles)
        return None, None, 0
    
    def drag_towards_arrow(self, center_x, center_y, angle_deg, distance=None, hold_seconds=None):
        """朝箭頭方向拖曳"""
        if distance is None:
            distance = DRAG_DISTANCE
        if hold_seconds is None:
            hold_seconds = DRAG_HOLD_SECONDS
            
        sw, sh = pyautogui.size()
        rad = math.radians(angle_deg)
        dx = distance * math.sin(rad)     # 0°在正上方 → x 用 sin
        dy = -distance * math.cos(rad)    # y 軸向下 → 取負的 cos

        tx = max(0, min(sw - 1, center_x + dx))
        ty = max(0, min(sh - 1, center_y + dy))

        cx = int(round(center_x))
        cy = int(round(center_y))
        tx = int(round(tx))
        ty = int(round(ty))

        # 執行拖曳：按住 -> 移動（持續 hold_seconds）-> 放開
        pyautogui.moveTo(cx, cy)
        pyautogui.mouseDown(button=DRAG_BUTTON)
        pyautogui.moveTo(tx, ty, duration=hold_seconds)
        pyautogui.mouseUp(button=DRAG_BUTTON)


class MainController:
    """主控制器"""
    
    def __init__(self):
        # 初始化偵測器
        self.icon_detector = ImageDetector(
            template_path=TARGET_IMAGE_PATH,
            search_region=ICON_SEARCH_REGION,
            confidence=ICON_CONFIDENCE
        )
        
        self.arrow_detector = ArrowDetector(
            character_template_path=CHARACTER_IMAGE_PATH,
            search_region=CHARACTER_SEARCH_REGION,
            arrow_search_radius=ARROW_SEARCH_RADIUS
        )
        
        # 狀態追蹤變數，避免重複訊息
        self.last_status = None  # 記錄上次的狀態
        self.search_start_time = None  # 記錄開始搜尋的時間
        
    def run(self):
        """主程式循環"""
        print("=== 主程式開始執行 ===")
        print("按 Ctrl+C 可停止程式")
        
        try:
            while True:
                # 步驟 1: 搜尋目標圖標
                location, scale = self.icon_detector.find_image_with_scaling()
                
                if location and scale:
                    # 找到圖標 - 只在狀態改變時顯示訊息
                    if self.last_status != "found":
                        print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] 找到目標圖標於位置: ({location[0]}, {location[1]})")
                        self.last_status = "found"
                    
                    # 步驟 2: 開始箭頭偵測循環
                    self.arrow_detection_loop(location, scale)
                    
                else:
                    # 未找到圖標 - 只在第一次顯示訊息
                    if self.last_status != "searching":
                        print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] 開始搜尋目標圖標...")
                        self.search_start_time = time.time()
                        self.last_status = "searching"
                    else:
                        # 如果已經搜尋超過30秒，顯示進度訊息
                        if time.time() - self.search_start_time > 30:
                            elapsed = int(time.time() - self.search_start_time)
                            print(f"持續搜尋中... (已搜尋 {elapsed} 秒)")
                            self.search_start_time = time.time()  # 重置計時器
                    
                    time.sleep(MAIN_SEARCH_INTERVAL)
                    
        except KeyboardInterrupt:
            print("\n程式已手動停止")
    
    def arrow_detection_loop(self, icon_location, icon_scale):
        """箭頭偵測循環"""
        print("開始箭頭偵測模式...")
        
        arrow_detection_count = 0
        
        while arrow_detection_count < MAX_ARROW_ATTEMPTS:
            # 檢查圖標是否還存在
            current_location, current_scale = self.icon_detector.find_image_with_scaling()
            if not current_location:
                print("目標圖標已消失，返回主搜尋模式")
                self.last_status = None  # 重置狀態，下次重新開始搜尋時會顯示訊息
                return
            
            # 更新圖標位置（可能有移動）
            icon_location = current_location
            icon_scale = current_scale
            
            # 每輪循環都先點擊一次圖標（預防性點擊）
            print(f"[箭頭偵測 {arrow_detection_count + 1}] 預防性點擊目標圖標...")
            if self.icon_detector.click_center(icon_location, icon_scale):
                print("預防性點擊完成")
            time.sleep(PREVENTIVE_CLICK_DELAY)  # 短暫等待
            
            print(f"[箭頭偵測 {arrow_detection_count + 1}] 搜尋人物位置...")
            
            # 尋找人物
            char_location, char_scale = self.arrow_detector.find_character()
            
            if char_location and char_scale:
                # 計算人物中心
                char_center_x = char_location[0] + (self.arrow_detector.template_width * char_scale) / 2
                char_center_y = char_location[1] + (self.arrow_detector.template_height * char_scale) / 2
                
                print(f"找到人物於: ({char_center_x:.1f}, {char_center_y:.1f})")
                
                # === 等待最多 3 秒，多幀蒐集箭頭角度 ===
                arrow_location, best_angle, hits = self.arrow_detector.wait_for_arrow(
                    char_center_x, char_center_y
                )
                
                if arrow_location and best_angle is not None:
                    direction = self.get_direction_from_angle(best_angle)
                    print(f"命中 {hits} 次 → 平均角度: {best_angle:.2f}°，方向：{direction}，箭頭座標：{arrow_location}")
                    
                    # 朝箭頭方向移動
                    print("執行移動...")
                    self.arrow_detector.drag_towards_arrow(char_center_x, char_center_y, best_angle)
                    
                    # 移動後等待一下
                    time.sleep(POST_MOVE_DELAY)
                    
                    # 移動後再次點擊目標圖標（確保點擊）
                    print("移動後再次點擊目標圖標...")
                    if self.icon_detector.click_center(icon_location, icon_scale):
                        print("移動後點擊圖標成功")
                    
                    # 短暫等待後檢查圖標是否消失
                    time.sleep(FINAL_CHECK_DELAY)
                    
                else:
                    print("人物在畫面中，但未穩定偵測到箭頭。")
                    
            else:
                print("未找到人物")
            
            arrow_detection_count += 1
            time.sleep(ARROW_SEARCH_INTERVAL)
        
        print(f"箭頭偵測嘗試已達上限 ({MAX_ARROW_ATTEMPTS} 次)，返回主搜尋模式")
    
    def get_direction_from_angle(self, angle):
        """根據旋轉角度判斷方向。"""
        angle = (angle + 360) % 360
        if 337.5 <= angle <= 360 or 0 <= angle <= 22.5:
            return "正上方"
        elif 22.5 < angle <= 67.5:
            return "右上"
        elif 67.5 < angle <= 112.5:
            return "正右方"
        elif 112.5 < angle <= 157.5:
            return "右下"
        elif 157.5 < angle <= 202.5:
            return "正下方"
        elif 202.5 < angle <= 247.5:
            return "左下"
        elif 247.5 < angle <= 292.5:
            return "正左方"
        elif 292.5 < angle <= 337.5:
            return "左上"
        else:
            return "未知方向"


def main():
    """主程式入口"""
    while True:
        try:
            show_menu()
            choice = input("\n請選擇操作 (1-4): ").strip()
            
            if choice == "1":
                resize_game_window()
                input("\n按 Enter 鍵返回選單...")
                
            elif choice == "2":
                print("\n正在初始化偵測器...")
                try:
                    controller = MainController()
                    controller.run()
                except ValueError as e:
                    print(f"初始化失敗: {e}")
                    print("請檢查圖片文件是否存在於當前目錄")
                    input("\n按 Enter 鍵返回選單...")
                except Exception as e:
                    print(f"運行時發生錯誤: {e}")
                    input("\n按 Enter 鍵返回選單...")
                    
            elif choice == "3":
                show_config()
                input("\n按 Enter 鍵返回選單...")
                
            elif choice == "4":
                print("\n程式已退出，再見！")
                break
                
            else:
                print("\n無效的選擇，請輸入 1-4")
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n\n程式已中斷")
            break
        except Exception as e:
            print(f"\n發生未預期的錯誤: {e}")
            input("按 Enter 鍵繼續...")


if __name__ == "__main__":
    main()
