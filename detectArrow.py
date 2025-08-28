import cv2
import pyautogui
import numpy as np
import time
import math

# --- 參數設定 ---
SCREEN_WIDTH, SCREEN_HEIGHT = pyautogui.size()

image_to_find  = 'character.png'
ARROW_IMAGE_PATH = 'arrow.png'

search_region = (200, 700, 700, 400)
ARROW_SEARCH_RADIUS = 100
SEARCH_INTERVAL = 0.5

DRAG_DISTANCE = 100
DRAG_HOLD_SECONDS = 1.0
DRAG_BUTTON = 'left'

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

def wait_for_arrow(center_x, center_y, radius, timeout=3.0, poll=0.12, min_hits=2, min_area=300):
    """
    在 timeout 秒內重複偵測箭頭，蒐集角度並做圓形平均。
    回傳：(arrow_location, avg_angle, hits_count)；若失敗回傳 (None, None, 0)
    """
    angles = []
    last_loc = None
    t0 = time.time()
    while time.time() - t0 < timeout:
        loc, _, ang = find_mvp_arrow_by_color(center_x, center_y, radius, min_area=min_area)
        if loc is not None and ang is not None:
            angles.append(ang)
            last_loc = loc
        time.sleep(poll)
    if len(angles) >= min_hits:
        return last_loc, circular_mean_deg(angles), len(angles)
    return None, None, 0

def to_edge(image_gray):
    # 輕微降噪再取邊緣
    blur = cv2.GaussianBlur(image_gray, (3, 3), 0)
    edges = cv2.Canny(blur, 50, 150)  # 50/150 可依素材微調
    return edges

def find_image_with_scaling(template_path, region, scale_steps=10, scale_range=(0.7, 1.3), confidence=0.5):
    """
    在指定區域內尋找一個可能輕微縮放的圖片。
    回傳：((x, y), best_scale) 或 (None, None)
    """
    template_img = cv2.imread(template_path, 0)
    if template_img is None:
        print(f"錯誤：無法載入模板圖片 '{template_path}'")
        return None, None

    # region 必須是四個整數
    rx, ry, rw, rh = region
    rx, ry, rw, rh = int(round(rx)), int(round(ry)), int(round(rw)), int(round(rh))

    screenshot = pyautogui.screenshot(region=(rx, ry, rw, rh))
    screenshot_np = np.array(screenshot)
    # PIL 是 RGB，要用 RGB2GRAY（原程式用 BGR2GRAY 會錯）
    screenshot_gray = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2GRAY)

    found_location = None
    max_corr = -1.0
    best_scale = None

    th, tw = template_img.shape[:2]

    for scale in np.linspace(scale_range[0], scale_range[1], scale_steps):
        w = max(1, int(round(tw * scale)))   # 確保至少 1
        h = max(1, int(round(th * scale)))
        resized_template = cv2.resize(template_img, (w, h))

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

def rotate_image(image, angle, center=None):
    """旋轉圖片（保持原圖尺寸）。"""
    (h, w) = image.shape[:2]
    if center is None:
        center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(image, M, (w, h))
    return rotated

def clamp_region_to_screen(x, y, w, h):
    """將擷取區域夾在螢幕邊界內且為整數，寬高最少為 1。"""
    sw, sh = pyautogui.size()
    x = int(round(max(0, min(x, sw - 1))))
    y = int(round(max(0, min(y, sh - 1))))
    # 防止超出邊界
    w = int(round(max(1, min(w, sw - x))))
    h = int(round(max(1, min(h, sh - y))))
    return x, y, w, h

def find_rotated_and_scaled_image(template_path, search_center_x, search_center_y, search_radius, 
                                  scale_steps=10, scale_range=(0.95, 1.05), 
                                  angle_steps=36, angle_range=(0, 360), confidence=0.75):
    """
    在指定中心點周圍搜尋可能旋轉和縮放的圖片（使用邊緣圖以抗亮暗呼吸效果）。
    回傳：(found_location, best_scale, best_angle) 或 (None, None, None)
    """
    template_gray = cv2.imread(template_path, 0)
    if template_gray is None:
        return None, None, None

    # 先把模板做成邊緣圖（只做一次）
    template_edge_base = to_edge(template_gray)

    # 計算擷取區域（可能是浮點，先夾在螢幕內並轉整數）
    screenshot_x = search_center_x - search_radius
    screenshot_y = search_center_y - search_radius
    screenshot_w = search_radius * 2
    screenshot_h = search_radius * 2
    screenshot_x, screenshot_y, screenshot_w, screenshot_h = clamp_region_to_screen(
        screenshot_x, screenshot_y, screenshot_w, screenshot_h
    )
    screenshot_region = (screenshot_x, screenshot_y, screenshot_w, screenshot_h)

    try:
        screenshot = pyautogui.screenshot(region=screenshot_region)
    except pyautogui.PyAutoGUIException:
        return None, None, None

    screenshot_np = np.array(screenshot)
    screenshot_gray = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2GRAY)
    # ★ 截圖也轉成邊緣圖（只做一次）
    screenshot_edge = to_edge(screenshot_gray)

    max_corr = -1.0
    found_location = None
    best_scale = None
    best_angle = None

    # 在邊緣圖上做旋轉 + 縮放匹配
    for angle in np.linspace(angle_range[0], angle_range[1], angle_steps, endpoint=False):
        rotated_edge = rotate_image(template_edge_base, angle)  # 旋轉後仍是單通道邊緣圖
        rth, rtw = rotated_edge.shape[:2]

        for scale in np.linspace(scale_range[0], scale_range[1], scale_steps):
            w = max(1, int(round(rtw * scale)))
            h = max(1, int(round(rth * scale)))
            # 用最近鄰插值避免邊緣被模糊
            resized_edge = cv2.resize(rotated_edge, (w, h), interpolation=cv2.INTER_NEAREST)

            if h > screenshot_edge.shape[0] or w > screenshot_edge.shape[1]:
                continue

            res = cv2.matchTemplate(screenshot_edge, resized_edge, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)

            if max_val > max_corr:
                max_corr = max_val
                top_left_in_screenshot = max_loc
                found_location = (top_left_in_screenshot[0] + screenshot_region[0],
                                  top_left_in_screenshot[1] + screenshot_region[1])
                best_scale = scale
                best_angle = angle

    if max_corr >= confidence and found_location is not None:
        return found_location, best_scale, best_angle
    else:
        return None, None, None

def get_direction_from_angle(angle):
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

def find_mvp_arrow_by_color(search_center_x, search_center_y, search_radius,
                            min_area=300):
    """
    以 HSV 紅色 + 形狀抓 MVP 箭頭，並回傳相對於「人物中心」的方向角度
    回傳：(top_left_global_xy, 1.0, angle_deg_from_up)
    抓不到： (None, None, None)
    """
    # 擷取區域（人物為中心的方形窗）
    sx = search_center_x - search_radius
    sy = search_center_y - search_radius
    sw = sh = search_radius * 2
    sx, sy, sw, sh = clamp_region_to_screen(sx, sy, sw, sh)

    try:
        pil_img = pyautogui.screenshot(region=(sx, sy, sw, sh))
    except pyautogui.PyAutoGUIException:
        return None, None, None

    img = np.array(pil_img)  # RGB
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)

    # 紅色兩段（可依實況調 S/V 下界，如 (0,60,60) 或 (0,90,90)）
    mask1 = cv2.inRange(hsv, (0, 80, 80), (10, 255, 255))
    mask2 = cv2.inRange(hsv, (170, 80, 80), (180, 255, 255))
    mask = cv2.bitwise_or(mask1, mask2)

    # 降噪 + 閉運算
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
        if circularity > 0.8:  # 太圓的排除
            continue

        score = area * (0.5 + 0.3 * extent + 0.2 * solidity)
        if score > best_score:
            best_score = score
            best = c

    if best is None:
        return None, None, None

    # 箭頭質心（區域內座標）
    M = cv2.moments(best)
    if M["m00"] == 0:
        return None, None, None
    cx_local = M["m10"] / M["m00"]
    cy_local = M["m01"] / M["m00"]

    # 轉成全螢幕座標
    cx = cx_local + sx
    cy = cy_local + sy

    # 方向角（以人物中心為原點；0°=正上，順時針增加）
    dx = cx - search_center_x
    dy = cy - search_center_y
    angle_deg = (math.degrees(math.atan2(dx, -dy)) + 360) % 360

    # 回傳外框左上角（可當作點擊或標示位置）
    x, y, w, h = cv2.boundingRect(best)
    top_left_global = (int(x + sx), int(y + sy))

    return top_left_global, 1.0, angle_deg

def drag_from_center_towards(center_x, center_y, angle_deg, distance=DRAG_DISTANCE,
                             hold_seconds=DRAG_HOLD_SECONDS, button=DRAG_BUTTON):
    """
    從 (center_x, center_y) 朝 angle_deg 方向拖曳 'hold_seconds' 秒後放開。
    角度定義：0°=正上方、順時針增加（與你現有 best_angle 一致）
    """
    # 計算目標點（螢幕座標，避免超出螢幕）
    sw, sh = pyautogui.size()
    rad = math.radians(angle_deg)
    dx = distance * math.sin(rad)     # 0°在正上方 → x 用 sin
    dy = -distance * math.cos(rad)    # y 軸向下 → 取負的 cos

    tx = max(0, min(sw - 1, center_x + dx))
    ty = max(0, min(sh - 1, center_y + dy))

    cx = int(round(center_x)); cy = int(round(center_y))
    tx = int(round(tx));       ty = int(round(ty))

    # 執行拖曳：按住 -> 移動（持續 hold_seconds）-> 放開
    pyautogui.moveTo(cx, cy)
    pyautogui.mouseDown(button=button)
    pyautogui.moveTo(tx, ty, duration=hold_seconds)
    pyautogui.mouseUp(button=button)

original_template_img = cv2.imread(image_to_find, 0)
if original_template_img is None:
    print(f"錯誤：無法載入模板圖片 '{image_to_find}'，請檢查路徑。")
    raise SystemExit(1)
original_template_width, original_template_height = original_template_img.shape[::-1]

original_arrow_img = cv2.imread(ARROW_IMAGE_PATH, 0)
if original_arrow_img is None:
    print(f"無法載入模板圖片 '{ARROW_IMAGE_PATH}'，請檢查路徑。")
    raise SystemExit(1)
original_arrow_width, original_arrow_height = original_arrow_img.shape[::-1]

# --- 主程式循環 ---
try:
    while True:
        print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}] 正在偵測人物位置...")
        location, best_scale_char = find_image_with_scaling(image_to_find, search_region)

        if location and best_scale_char:
            center_x = location[0] + (original_template_width * best_scale_char) / 2.0
            center_y = location[1] + (original_template_height * best_scale_char) / 2.0
            print(f"找到了！人物中心位置在：({center_x:.1f}, {center_y:.1f})")

            # === 等待最多 3 秒，多幀蒐集箭頭角度 ===
            arrow_location, best_angle, hits = wait_for_arrow(
                center_x, center_y, ARROW_SEARCH_RADIUS,
                timeout=3.0, poll=0.12, min_hits=2, min_area=300
            )

            if arrow_location and best_angle is not None:
                direction = get_direction_from_angle(best_angle)
                print(f"命中 {hits} 次 → 平均角度: {best_angle:.2f}°，方向：{direction}，箭頭座標：{arrow_location}")

                # 拖曳人物朝平均角度移動
                drag_from_center_towards(center_x, center_y, best_angle)
            else:
                print("人物在畫面中，但未穩定偵測到箭頭。")
        else:
            print("未找到人物圖標，等待下次偵測。")

        time.sleep(SEARCH_INTERVAL)

except KeyboardInterrupt:
    print("\n程式已手動停止。")
