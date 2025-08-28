# app.py
import sys, os, json, time, math, random, threading
import numpy as np
import cv2
import pyautogui
import pygetwindow as gw

from PySide6.QtCore import Qt, QRect, QPoint, Signal, QObject, QThread
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, QFileDialog,
    QGridLayout, QGroupBox, QTextEdit, QHBoxLayout, QVBoxLayout, QMessageBox,
    QSizePolicy, QDialog, QSlider, QSpinBox, QDoubleSpinBox, QFormLayout, QTabWidget
)
from PySide6.QtGui import QPainter, QPen, QColor, QGuiApplication, QImage, QPixmap, QIcon

# ==========================
# 設定檔處理
# ==========================
DEFAULT_CFG = {
    "TARGET_TITLE_KEYWORD": "Chrome",       # 預設關鍵字
    "WINDOW_POSITION_X": 0,
    "WINDOW_POSITION_Y": 0,
    "WINDOW_WIDTH": 1280,
    "WINDOW_HEIGHT": 720,

    "TARGET_IMAGE_PATH": "target.png",
    "CHARACTER_IMAGE_PATH": "character.png",
    "ARROW_IMAGE_PATH": "arrow.png",  # 只是給你保留選檔，實際偵測走顏色

    # 區塊 (x, y, w, h)
    "ICON_SEARCH_REGION": [0, 0, 800, 600],
    "CHARACTER_SEARCH_REGION": [0, 0, 800, 600],

    # 偵測參數
    "ICON_CONFIDENCE": 0.8,
    "CHARACTER_CONFIDENCE": 0.8,
    "ICON_SCALE_RANGE": [0.8, 1.2],
    "ICON_SCALE_STEPS": 7,
    "CHARACTER_SCALE_RANGE": [0.8, 1.2],
    "CHARACTER_SCALE_STEPS": 7,

    # 箭頭/拖曳
    "ARROW_SEARCH_RADIUS": 140,
    "ARROW_MIN_AREA": 80,
    "ARROW_DETECTION_TIMEOUT": 3.0,
    "ARROW_POLL_INTERVAL": 0.08,
    "ARROW_MIN_HITS": 5,
    "DRAG_DISTANCE": 180,
    "DRAG_HOLD_SECONDS": 0.2,
    "DRAG_BUTTON": "left",

    # 主流程
    "MAX_ARROW_ATTEMPTS": 6,
    "MAIN_SEARCH_INTERVAL": 0.6,
    "PREVENTIVE_CLICK_DELAY": 0.2,
    "POST_MOVE_DELAY": 0.25,
    "FINAL_CHECK_DELAY": 0.2,
    "ARROW_SEARCH_INTERVAL": 0.2
}

CFG_PATH = "config.json"

def load_cfg():
    if os.path.exists(CFG_PATH):
        with open(CFG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        # 舊檔案補缺欄
        for k,v in DEFAULT_CFG.items():
            if k not in data:
                data[k] = v
        return data
    return DEFAULT_CFG.copy()

def save_cfg(cfg):
    with open(CFG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

# ==========================
# 公用函式
# ==========================
def circular_mean_deg(angles_deg):
    if not angles_deg:
        return None
    sum_x = sum(math.sin(math.radians(a)) for a in angles_deg)
    sum_y = sum(math.cos(math.radians(a)) for a in angles_deg)
    if sum_x == 0 and sum_y == 0:
        return None
    mean_rad = math.atan2(sum_x, sum_y)
    return (math.degrees(mean_rad) + 360) % 360

def clamp_region_to_screen(x, y, w, h):
    sw, sh = pyautogui.size()
    x = int(round(max(0, min(x, sw - 1))))
    y = int(round(max(0, min(y, sh - 1))))
    w = int(round(max(1, min(w, sw - x))))
    h = int(round(max(1, min(h, sh - y))))
    return x, y, w, h

# ==========================
# 配置設定對話框
# ==========================
class ConfigDialog(QDialog):
    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.setWindowTitle("參數設定")
        self.setModal(True)
        self.resize(500, 600)
        
        # 複製配置以避免直接修改原始配置
        self.cfg = cfg.copy()
        
        self._build_ui()
        self._load_values()
        
    def _build_ui(self):
        layout = QVBoxLayout(self)
        
        # 使用標籤頁來組織不同類型的設定
        tabs = QTabWidget()
        
        # 偵測參數標籤頁
        detection_tab = QWidget()
        detection_layout = QFormLayout(detection_tab)
        
        # 圖標偵測信心度
        self.icon_confidence_slider = QSlider(Qt.Horizontal)
        self.icon_confidence_slider.setRange(0, 100)
        self.icon_confidence_slider.setValue(int(self.cfg["ICON_CONFIDENCE"] * 100))
        self.icon_confidence_label = QLabel()
        self.icon_confidence_slider.valueChanged.connect(self._update_icon_confidence_label)
        
        icon_conf_layout = QHBoxLayout()
        icon_conf_layout.addWidget(self.icon_confidence_slider)
        icon_conf_layout.addWidget(self.icon_confidence_label)
        detection_layout.addRow("圖標偵測信心度:", icon_conf_layout)
        
        # 人物偵測信心度
        self.character_confidence_slider = QSlider(Qt.Horizontal)
        self.character_confidence_slider.setRange(0, 100)
        self.character_confidence_slider.setValue(int(self.cfg["CHARACTER_CONFIDENCE"] * 100))
        self.character_confidence_label = QLabel()
        self.character_confidence_slider.valueChanged.connect(self._update_character_confidence_label)
        
        char_conf_layout = QHBoxLayout()
        char_conf_layout.addWidget(self.character_confidence_slider)
        char_conf_layout.addWidget(self.character_confidence_label)
        detection_layout.addRow("人物偵測信心度:", char_conf_layout)
        
        # 圖標縮放步數
        self.icon_scale_steps_spin = QSpinBox()
        self.icon_scale_steps_spin.setRange(1, 20)
        self.icon_scale_steps_spin.setValue(self.cfg["ICON_SCALE_STEPS"])
        detection_layout.addRow("圖標縮放步數:", self.icon_scale_steps_spin)
        
        # 人物縮放步數
        self.character_scale_steps_spin = QSpinBox()
        self.character_scale_steps_spin.setRange(1, 20)
        self.character_scale_steps_spin.setValue(self.cfg["CHARACTER_SCALE_STEPS"])
        detection_layout.addRow("人物縮放步數:", self.character_scale_steps_spin)
        
        # 圖標縮放範圍
        self.icon_scale_min_spin = QDoubleSpinBox()
        self.icon_scale_min_spin.setRange(0.1, 2.0)
        self.icon_scale_min_spin.setSingleStep(0.05)
        self.icon_scale_min_spin.setDecimals(2)
        self.icon_scale_min_spin.setValue(self.cfg["ICON_SCALE_RANGE"][0])
        
        self.icon_scale_max_spin = QDoubleSpinBox()
        self.icon_scale_max_spin.setRange(0.1, 2.0)
        self.icon_scale_max_spin.setSingleStep(0.05)
        self.icon_scale_max_spin.setDecimals(2)
        self.icon_scale_max_spin.setValue(self.cfg["ICON_SCALE_RANGE"][1])
        
        icon_scale_layout = QHBoxLayout()
        icon_scale_layout.addWidget(QLabel("最小:"))
        icon_scale_layout.addWidget(self.icon_scale_min_spin)
        icon_scale_layout.addWidget(QLabel("最大:"))
        icon_scale_layout.addWidget(self.icon_scale_max_spin)
        detection_layout.addRow("圖標縮放範圍:", icon_scale_layout)
        
        # 人物縮放範圍
        self.character_scale_min_spin = QDoubleSpinBox()
        self.character_scale_min_spin.setRange(0.1, 2.0)
        self.character_scale_min_spin.setSingleStep(0.05)
        self.character_scale_min_spin.setDecimals(2)
        self.character_scale_min_spin.setValue(self.cfg["CHARACTER_SCALE_RANGE"][0])
        
        self.character_scale_max_spin = QDoubleSpinBox()
        self.character_scale_max_spin.setRange(0.1, 2.0)
        self.character_scale_max_spin.setSingleStep(0.05)
        self.character_scale_max_spin.setDecimals(2)
        self.character_scale_max_spin.setValue(self.cfg["CHARACTER_SCALE_RANGE"][1])
        
        character_scale_layout = QHBoxLayout()
        character_scale_layout.addWidget(QLabel("最小:"))
        character_scale_layout.addWidget(self.character_scale_min_spin)
        character_scale_layout.addWidget(QLabel("最大:"))
        character_scale_layout.addWidget(self.character_scale_max_spin)
        detection_layout.addRow("人物縮放範圍:", character_scale_layout)
        
        tabs.addTab(detection_tab, "偵測參數")
        
        # 箭頭偵測標籤頁
        arrow_tab = QWidget()
        arrow_layout = QFormLayout(arrow_tab)
        
        # 箭頭搜尋半徑
        self.arrow_radius_slider = QSlider(Qt.Horizontal)
        self.arrow_radius_slider.setRange(50, 300)
        self.arrow_radius_slider.setValue(self.cfg["ARROW_SEARCH_RADIUS"])
        self.arrow_radius_label = QLabel()
        self.arrow_radius_slider.valueChanged.connect(self._update_arrow_radius_label)
        
        arrow_radius_layout = QHBoxLayout()
        arrow_radius_layout.addWidget(self.arrow_radius_slider)
        arrow_radius_layout.addWidget(self.arrow_radius_label)
        arrow_layout.addRow("箭頭搜尋半徑:", arrow_radius_layout)
        
        # 箭頭最小面積
        self.arrow_min_area_slider = QSlider(Qt.Horizontal)
        self.arrow_min_area_slider.setRange(10, 500)
        self.arrow_min_area_slider.setValue(self.cfg["ARROW_MIN_AREA"])
        self.arrow_min_area_label = QLabel()
        self.arrow_min_area_slider.valueChanged.connect(self._update_arrow_min_area_label)
        
        arrow_area_layout = QHBoxLayout()
        arrow_area_layout.addWidget(self.arrow_min_area_slider)
        arrow_area_layout.addWidget(self.arrow_min_area_label)
        arrow_layout.addRow("箭頭最小面積:", arrow_area_layout)
        
        # 箭頭偵測超時時間
        self.arrow_timeout_spin = QDoubleSpinBox()
        self.arrow_timeout_spin.setRange(0.5, 10.0)
        self.arrow_timeout_spin.setSingleStep(0.1)
        self.arrow_timeout_spin.setValue(self.cfg["ARROW_DETECTION_TIMEOUT"])
        arrow_layout.addRow("箭頭偵測超時時間(秒):", self.arrow_timeout_spin)
        
        # 箭頭最小命中次數
        self.arrow_min_hits_spin = QSpinBox()
        self.arrow_min_hits_spin.setRange(1, 20)
        self.arrow_min_hits_spin.setValue(self.cfg["ARROW_MIN_HITS"])
        arrow_layout.addRow("箭頭最小命中次數:", self.arrow_min_hits_spin)
        
        tabs.addTab(arrow_tab, "箭頭偵測")
        
        # 移動控制標籤頁
        movement_tab = QWidget()
        movement_layout = QFormLayout(movement_tab)
        
        # 拖曳距離
        self.drag_distance_slider = QSlider(Qt.Horizontal)
        self.drag_distance_slider.setRange(50, 500)
        self.drag_distance_slider.setValue(self.cfg["DRAG_DISTANCE"])
        self.drag_distance_label = QLabel()
        self.drag_distance_slider.valueChanged.connect(self._update_drag_distance_label)
        
        drag_dist_layout = QHBoxLayout()
        drag_dist_layout.addWidget(self.drag_distance_slider)
        drag_dist_layout.addWidget(self.drag_distance_label)
        movement_layout.addRow("拖曳距離(像素):", drag_dist_layout)
        
        # 拖曳持續時間
        self.drag_hold_spin = QDoubleSpinBox()
        self.drag_hold_spin.setRange(0.1, 5.0)
        self.drag_hold_spin.setSingleStep(0.1)
        self.drag_hold_spin.setValue(self.cfg["DRAG_HOLD_SECONDS"])
        movement_layout.addRow("拖曳持續時間(秒):", self.drag_hold_spin)
        
        tabs.addTab(movement_tab, "移動控制")
        
        # 時間控制標籤頁
        timing_tab = QWidget()
        timing_layout = QFormLayout(timing_tab)
        
        # 主搜尋間隔
        self.main_interval_spin = QDoubleSpinBox()
        self.main_interval_spin.setRange(0.1, 5.0)
        self.main_interval_spin.setSingleStep(0.1)
        self.main_interval_spin.setValue(self.cfg["MAIN_SEARCH_INTERVAL"])
        timing_layout.addRow("主搜尋間隔(秒):", self.main_interval_spin)
        
        # 箭頭偵測間隔
        self.arrow_interval_spin = QDoubleSpinBox()
        self.arrow_interval_spin.setRange(0.05, 2.0)
        self.arrow_interval_spin.setSingleStep(0.05)
        self.arrow_interval_spin.setValue(self.cfg["ARROW_SEARCH_INTERVAL"])
        timing_layout.addRow("箭頭偵測間隔(秒):", self.arrow_interval_spin)
        
        # 最大箭頭嘗試次數
        self.max_attempts_spin = QSpinBox()
        self.max_attempts_spin.setRange(1, 20)
        self.max_attempts_spin.setValue(self.cfg["MAX_ARROW_ATTEMPTS"])
        timing_layout.addRow("最大箭頭嘗試次數:", self.max_attempts_spin)
        
        tabs.addTab(timing_tab, "時間控制")
        
        layout.addWidget(tabs)
        
        # 按鈕
        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("確定")
        self.cancel_button = QPushButton("取消")
        self.reset_button = QPushButton("重設為預設值")
        
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        self.reset_button.clicked.connect(self._reset_to_defaults)
        
        button_layout.addWidget(self.reset_button)
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        
    def _load_values(self):
        """載入初始值並更新標籤"""
        self._update_icon_confidence_label()
        self._update_character_confidence_label()
        self._update_arrow_radius_label()
        self._update_arrow_min_area_label()
        self._update_drag_distance_label()
        
    def _update_icon_confidence_label(self):
        value = self.icon_confidence_slider.value() / 100.0
        self.icon_confidence_label.setText(f"{value:.2f}")
        
    def _update_character_confidence_label(self):
        value = self.character_confidence_slider.value() / 100.0
        self.character_confidence_label.setText(f"{value:.2f}")
        
    def _update_arrow_radius_label(self):
        value = self.arrow_radius_slider.value()
        self.arrow_radius_label.setText(f"{value} px")
        
    def _update_arrow_min_area_label(self):
        value = self.arrow_min_area_slider.value()
        self.arrow_min_area_label.setText(f"{value} px²")
        
    def _update_drag_distance_label(self):
        value = self.drag_distance_slider.value()
        self.drag_distance_label.setText(f"{value} px")
        
    def _reset_to_defaults(self):
        """重設所有值為預設值"""
        # 偵測參數
        self.icon_confidence_slider.setValue(int(DEFAULT_CFG["ICON_CONFIDENCE"] * 100))
        self.character_confidence_slider.setValue(int(DEFAULT_CFG["CHARACTER_CONFIDENCE"] * 100))
        self.icon_scale_steps_spin.setValue(DEFAULT_CFG["ICON_SCALE_STEPS"])
        self.character_scale_steps_spin.setValue(DEFAULT_CFG["CHARACTER_SCALE_STEPS"])
        
        # 縮放範圍
        self.icon_scale_min_spin.setValue(DEFAULT_CFG["ICON_SCALE_RANGE"][0])
        self.icon_scale_max_spin.setValue(DEFAULT_CFG["ICON_SCALE_RANGE"][1])
        self.character_scale_min_spin.setValue(DEFAULT_CFG["CHARACTER_SCALE_RANGE"][0])
        self.character_scale_max_spin.setValue(DEFAULT_CFG["CHARACTER_SCALE_RANGE"][1])
        
        # 箭頭偵測
        self.arrow_radius_slider.setValue(DEFAULT_CFG["ARROW_SEARCH_RADIUS"])
        self.arrow_min_area_slider.setValue(DEFAULT_CFG["ARROW_MIN_AREA"])
        self.arrow_timeout_spin.setValue(DEFAULT_CFG["ARROW_DETECTION_TIMEOUT"])
        self.arrow_min_hits_spin.setValue(DEFAULT_CFG["ARROW_MIN_HITS"])
        
        # 移動控制
        self.drag_distance_slider.setValue(DEFAULT_CFG["DRAG_DISTANCE"])
        self.drag_hold_spin.setValue(DEFAULT_CFG["DRAG_HOLD_SECONDS"])
        
        # 時間控制
        self.main_interval_spin.setValue(DEFAULT_CFG["MAIN_SEARCH_INTERVAL"])
        self.arrow_interval_spin.setValue(DEFAULT_CFG["ARROW_SEARCH_INTERVAL"])
        self.max_attempts_spin.setValue(DEFAULT_CFG["MAX_ARROW_ATTEMPTS"])
        
    def get_config(self):
        """返回更新後的配置"""
        self.cfg["ICON_CONFIDENCE"] = self.icon_confidence_slider.value() / 100.0
        self.cfg["CHARACTER_CONFIDENCE"] = self.character_confidence_slider.value() / 100.0
        self.cfg["ICON_SCALE_STEPS"] = self.icon_scale_steps_spin.value()
        self.cfg["CHARACTER_SCALE_STEPS"] = self.character_scale_steps_spin.value()
        
        # 縮放範圍
        self.cfg["ICON_SCALE_RANGE"] = [self.icon_scale_min_spin.value(), self.icon_scale_max_spin.value()]
        self.cfg["CHARACTER_SCALE_RANGE"] = [self.character_scale_min_spin.value(), self.character_scale_max_spin.value()]
        
        self.cfg["ARROW_SEARCH_RADIUS"] = self.arrow_radius_slider.value()
        self.cfg["ARROW_MIN_AREA"] = self.arrow_min_area_slider.value()
        self.cfg["ARROW_DETECTION_TIMEOUT"] = self.arrow_timeout_spin.value()
        self.cfg["ARROW_MIN_HITS"] = self.arrow_min_hits_spin.value()
        
        self.cfg["DRAG_DISTANCE"] = self.drag_distance_slider.value()
        self.cfg["DRAG_HOLD_SECONDS"] = self.drag_hold_spin.value()
        
        self.cfg["MAIN_SEARCH_INTERVAL"] = self.main_interval_spin.value()
        self.cfg["ARROW_SEARCH_INTERVAL"] = self.arrow_interval_spin.value()
        self.cfg["MAX_ARROW_ATTEMPTS"] = self.max_attempts_spin.value()
        
        return self.cfg

# ==========================
# 你的偵測類別（略微改為讀 cfg 變數）
# ==========================
class ImageDetector:
    def __init__(self, template_path, search_region, confidence=0.8, scale_steps=7, scale_range=(0.8,1.2)):
        self.template_path = template_path
        self.search_region = tuple(search_region)
        self.confidence = confidence
        self.scale_steps = scale_steps
        self.scale_range = scale_range

        self.template_img = cv2.imread(template_path, 0)
        if self.template_img is None:
            raise ValueError(f"無法載入圖片: {template_path}")
        self.template_width, self.template_height = self.template_img.shape[::-1]

    def find_image_with_scaling(self):
        scale_steps = self.scale_steps
        scale_range = self.scale_range
        screenshot = pyautogui.screenshot(region=self.search_region)
        screenshot_np = np.array(screenshot)
        screenshot_gray = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2GRAY)

        found_location = None
        max_corr = -1
        best_scale = None

        for scale in np.linspace(scale_range[0], scale_range[1], scale_steps):
            w, h = self.template_img.shape[::-1]
            resized_template = cv2.resize(self.template_img, (int(w * scale), int(h * scale)))
            if resized_template.shape[0] > screenshot_gray.shape[0] or resized_template.shape[1] > screenshot_gray.shape[1]:
                continue
            res = cv2.matchTemplate(screenshot_gray, resized_template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
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
        if location and scale:
            center_x = location[0] + (self.template_width * scale) / 2
            center_y = location[1] + (self.template_height * scale) / 2
            return center_x, center_y
        return None, None

    def click_center(self, location, scale):
        cx, cy = self.get_center_position(location, scale)
        if cx and cy:
            offx = random.randint(-10, 10)
            offy = random.randint(-10, 10)
            sw, sh = pyautogui.size()
            click_x = max(0, min(sw - 1, cx + offx))
            click_y = max(0, min(sh - 1, cy + offy))
            pyautogui.click(click_x, click_y)
            return True
        return False


class ArrowDetector:
    def __init__(self, character_template_path, search_region, arrow_search_radius=140,
                 min_area=80, conf=0.8, scale_steps=7, scale_range=(0.8,1.2),
                 drag_distance=180, drag_seconds=0.2, drag_button="left",
                 timeout=3.0, poll=0.08, min_hits=5):
        self.character_template_path = character_template_path
        self.search_region = tuple(search_region)
        self.arrow_search_radius = arrow_search_radius
        self.min_area = min_area
        self.confidence = conf
        self.scale_steps = scale_steps
        self.scale_range = scale_range
        self.drag_distance = drag_distance
        self.drag_seconds = drag_seconds
        self.drag_button = drag_button
        self.timeout = timeout
        self.poll = poll
        self.min_hits = min_hits

        self.template_img = cv2.imread(character_template_path, 0)
        if self.template_img is None:
            raise ValueError(f"無法載入圖片: {character_template_path}")
        self.template_width, self.template_height = self.template_img.shape[::-1]

    def find_character(self):
        rx, ry, rw, rh = map(int, self.search_region)
        screenshot = pyautogui.screenshot(region=(rx, ry, rw, rh))
        screenshot_np = np.array(screenshot)
        screenshot_gray = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2GRAY)

        found_location = None
        max_corr = -1.0
        best_scale = None
        th, tw = self.template_img.shape[:2]

        for scale in np.linspace(self.scale_range[0], self.scale_range[1], self.scale_steps):
            w = max(1, int(round(tw * scale)))
            h = max(1, int(round(th * scale)))
            resized = cv2.resize(self.template_img, (w, h))
            if h > screenshot_gray.shape[0] or w > screenshot_gray.shape[1]:
                continue
            res = cv2.matchTemplate(screenshot_gray, resized, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            if max_val > max_corr:
                max_corr = max_val
                top_left = max_loc
                found_location = (top_left[0] + rx, top_left[1] + ry)
                best_scale = scale

        if max_corr >= self.confidence and found_location is not None:
            return found_location, best_scale
        else:
            return None, None

    def find_arrow_by_color(self, search_center_x, search_center_y):
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

        mask1 = cv2.inRange(hsv, (0, 80, 80), (10, 255, 255))
        mask2 = cv2.inRange(hsv, (170, 80, 80), (180, 255, 255))
        mask = cv2.bitwise_or(mask1, mask2)

        mask = cv2.medianBlur(mask, 3)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5,5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)

        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        best = None
        best_score = -1
        for c in cnts:
            area = cv2.contourArea(c)
            if area < self.min_area:
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
            score = area * (0.5 + 0.3*extent + 0.2*solidity)
            if score > best_score:
                best_score = score
                best = c

        if best is None:
            return None, None, None
        M = cv2.moments(best)
        if M["m00"] == 0:
            return None, None, None
        cx_local = M["m10"] / M["m00"]
        cy_local = M["m01"] / M["m00"]
        cx = cx_local + sx
        cy = cy_local + sy
        dx = cx - search_center_x
        dy = cy - search_center_y
        angle_deg = (math.degrees(math.atan2(dx, -dy)) + 360) % 360
        x, y, w, h = cv2.boundingRect(best)
        top_left_global = (int(x + sx), int(y + sy))
        return top_left_global, 1.0, angle_deg

    def wait_for_arrow(self, center_x, center_y):
        angles = []
        last_loc = None
        t0 = time.time()
        while time.time() - t0 < self.timeout:
            loc, _, ang = self.find_arrow_by_color(center_x, center_y)
            if loc is not None and ang is not None:
                angles.append(ang)
                last_loc = loc
            time.sleep(self.poll)
        if len(angles) >= self.min_hits:
            return last_loc, circular_mean_deg(angles), len(angles)
        return None, None, 0

    def drag_towards_arrow(self, center_x, center_y, angle_deg):
        sw, sh = pyautogui.size()
        rad = math.radians(angle_deg)
        dx = self.drag_distance * math.sin(rad)
        dy = -self.drag_distance * math.cos(rad)
        tx = max(0, min(sw - 1, center_x + dx))
        ty = max(0, min(sh - 1, center_y + dy))
        cx = int(round(center_x)); cy = int(round(center_y))
        tx = int(round(tx)); ty = int(round(ty))
        pyautogui.moveTo(cx, cy)
        pyautogui.mouseDown(button=self.drag_button)
        pyautogui.moveTo(tx, ty, duration=self.drag_seconds)
        pyautogui.mouseUp(button=self.drag_button)

# ==========================
# Worker 執行緒（Start/Pause/Stop）
# ==========================
class WorkerSignals(QObject):
    log = Signal(str)
    finished = Signal()

class DetectorWorker(QThread):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.signals = WorkerSignals()
        self._pause_ev = threading.Event()
        self._stop_ev = threading.Event()
        self._pause_ev.set()  # 預設可跑

    def pause(self):
        self._pause_ev.clear()

    def resume(self):
        self._pause_ev.set()

    def stop(self):
        self._stop_ev.set()
        self._pause_ev.set()

    def _log(self, msg):
        self.signals.log.emit(msg)

    def run(self):
        try:
            icon = ImageDetector(
                template_path=self.cfg["TARGET_IMAGE_PATH"],
                search_region=self.cfg["ICON_SEARCH_REGION"],
                confidence=self.cfg["ICON_CONFIDENCE"],
                scale_steps=self.cfg["ICON_SCALE_STEPS"],
                scale_range=tuple(self.cfg["ICON_SCALE_RANGE"])
            )
            arrow = ArrowDetector(
                character_template_path=self.cfg["CHARACTER_IMAGE_PATH"],
                search_region=self.cfg["CHARACTER_SEARCH_REGION"],
                arrow_search_radius=self.cfg["ARROW_SEARCH_RADIUS"],
                min_area=self.cfg["ARROW_MIN_AREA"],
                conf=self.cfg["CHARACTER_CONFIDENCE"],
                scale_steps=self.cfg["CHARACTER_SCALE_STEPS"],
                scale_range=tuple(self.cfg["CHARACTER_SCALE_RANGE"]),
                drag_distance=self.cfg["DRAG_DISTANCE"],
                drag_seconds=self.cfg["DRAG_HOLD_SECONDS"],
                drag_button=self.cfg["DRAG_BUTTON"],
                timeout=self.cfg["ARROW_DETECTION_TIMEOUT"],
                poll=self.cfg["ARROW_POLL_INTERVAL"],
                min_hits=self.cfg["ARROW_MIN_HITS"]
            )
        except Exception as e:
            self._log(f"[初始化失敗] {e}")
            self.signals.finished.emit()
            return

        last_status = None
        search_t0 = 0

        self._log("=== 偵測開始 ===")
        while not self._stop_ev.is_set():
            # 暫停
            if not self._pause_ev.is_set():
                time.sleep(0.1)
                continue

            # 尋找目標圖標
            location, scale = icon.find_image_with_scaling()
            if location and scale:
                if last_status != "found":
                    self._log(f"[{time.strftime('%H:%M:%S')}] 找到目標圖標：{location}")
                    last_status = "found"

                # 箭頭偵測迴圈
                attempts = 0
                while attempts < self.cfg["MAX_ARROW_ATTEMPTS"] and self._pause_ev.is_set() and not self._stop_ev.is_set():
                    # 圖標是否還在
                    current_location, current_scale = icon.find_image_with_scaling()
                    if not current_location:
                        self._log("目標圖標消失，回到搜尋。")
                        last_status = None
                        break

                    self._log(f"[箭頭偵測 {attempts+1}] 點擊圖標(預防性)")
                    icon.click_center(current_location, current_scale)
                    time.sleep(self.cfg["PREVENTIVE_CLICK_DELAY"])

                    # 找人物
                    char_loc, char_scale = arrow.find_character()
                    if char_loc and char_scale:
                        cx = char_loc[0] + (arrow.template_width * char_scale) / 2
                        cy = char_loc[1] + (arrow.template_height * char_scale) / 2
                        self._log(f"人物座標：({cx:.1f}, {cy:.1f})，蒐集箭頭角度…")
                        arrow_loc, best_angle, hits = arrow.wait_for_arrow(cx, cy)
                        if arrow_loc and best_angle is not None:
                            self._log(f"命中 {hits} 次 → 角度 {best_angle:.1f}° → 拖曳移動")
                            arrow.drag_towards_arrow(cx, cy, best_angle)
                            time.sleep(self.cfg["POST_MOVE_DELAY"])
                            self._log("移動後再次點圖標")
                            icon.click_center(current_location, current_scale)
                            time.sleep(self.cfg["FINAL_CHECK_DELAY"])
                        else:
                            self._log("未穩定偵測到箭頭")
                    else:
                        self._log("未找到人物")

                    attempts += 1
                    time.sleep(self.cfg["ARROW_SEARCH_INTERVAL"])
            else:
                if last_status != "searching":
                    self._log(f"[{time.strftime('%H:%M:%S')}] 搜尋目標圖標中…")
                    last_status = "searching"
                    search_t0 = time.time()
                else:
                    if time.time() - search_t0 > 30:
                        self._log("持續搜尋中…(>30s)")
                        search_t0 = time.time()
                time.sleep(self.cfg["MAIN_SEARCH_INTERVAL"])

        self._log("=== 偵測結束 ===")
        self.signals.finished.emit()

# ==========================
# 矩形框選 Overlay
# ==========================
class RegionPicker(QWidget):
    picked = Signal(tuple)  # (x,y,w,h) - 邏輯像素

    def __init__(self):
        super().__init__()
        self.setWindowTitle("選擇區域")
        
        # 設定視窗屬性 - 更強制的置頂和全螢幕
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool |
            Qt.WindowSystemMenuHint
        )
        
        # 設定透明背景
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)

        self.origin = None
        self.end = None

        # 覆蓋整個虛擬桌面（多螢幕）
        vg = QGuiApplication.primaryScreen().virtualGeometry()
        print(f"RegionPicker 初始化: 虛擬桌面 = {vg}")
        self.setGeometry(vg)
        
        # 確保視窗完全可見和可互動
        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        self.setFocus()
        
        # 確保視窗在最頂層
        self.setWindowState(Qt.WindowActive)
        
        print("RegionPicker 已顯示，請在螢幕上拖拽選擇區域...")

    def showEvent(self, event):
        """當視窗顯示時確保它在最頂層"""
        super().showEvent(event)
        self.raise_()
        self.activateWindow()
        self.setFocus()
        print("RegionPicker showEvent 觸發")

    def keyPressEvent(self, e):
        # 按 ESC 取消選擇
        if e.key() == Qt.Key_Escape:
            print("用戶按下 ESC 鍵，取消選擇")
            self.close()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.origin = e.position().toPoint()  # 使用新的 API
            self.end = e.position().toPoint()
            print(f"開始拖拽: {self.origin}")
            self.update()

    def mouseMoveEvent(self, e):
        if self.origin:
            self.end = e.position().toPoint()  # 使用新的 API
            self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.origin:
            rect = QRect(self.origin, self.end).normalized()
            x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
            print(f"選擇完成: 邏輯座標 ({x}, {y}, {w}, {h})")
            
            # 確保區域有效
            if w > 5 and h > 5:  # 最小尺寸限制
                # 立即發出信號，然後關閉
                print(f"發送選擇區域: ({x}, {y}, {w}, {h})")
                self.picked.emit((x, y, w, h))
                # 使用定時器延遲關閉，確保信號處理完成
                from PySide6.QtCore import QTimer
                QTimer.singleShot(50, self.close)
            else:
                print("選擇區域太小，已忽略")
                self.close()

    def paintEvent(self, e):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 繪製半透明黑色遮罩覆蓋整個螢幕
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        
        # 如果有選擇區域，繪製選擇框
        if self.origin and self.end:
            rect = QRect(self.origin, self.end).normalized()
            
            # 選擇區域顯示透明（清除遮罩）
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(rect, QColor(0, 0, 0, 0))
            
            # 恢復正常繪製模式
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            
            # 繪製綠色邊框
            pen = QPen(QColor(0, 255, 0, 255), 3, Qt.SolidLine)
            painter.setPen(pen)
            painter.drawRect(rect)
            
            # 顯示座標資訊
            painter.setPen(QPen(QColor(255, 255, 255, 255), 1))
            text = f"({rect.x()}, {rect.y()}) {rect.width()}×{rect.height()}"
            painter.drawText(rect.bottomLeft() + QPoint(5, -5), text)

# ==========================
# 主視窗
# ==========================
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Librer - [V.1.0.0, 2025/08/25]")
        self.cfg = load_cfg()
        self.worker = None
        self._picker = None 
        self.preview_label = QLabel()       # 預覽縮圖區
        self.preview_label.setMinimumHeight(160)
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("border: 1px dashed #888; color:#888;")
        self.preview_label.setText("（框選完成後顯示預覽）")
        self.preview_label.hide()  # 初始時隱藏
        self._build_ui()
        self._load_cfg_to_ui()

    def _create_vertical_line(self):
        """創建垂直分隔線"""
        line = QLabel()
        line.setText("|")
        line.setStyleSheet("color: #ccc; font-size: 18px; margin: 0 5px;")
        line.setAlignment(Qt.AlignCenter)
        return line

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # --- 視窗關鍵字 ---
        grp_win = QGroupBox("目標視窗")
        g1 = QGridLayout()
        self.le_title = QLineEdit()
        btn_resize = QPushButton("一鍵定位/調整大小")
        btn_resize.clicked.connect(self.on_resize_window)
        
        # 視窗尺寸調整控制項
        self.le_win_x = QLineEdit()
        self.le_win_y = QLineEdit()
        self.le_win_width = QLineEdit()
        self.le_win_height = QLineEdit()
        
        # 設定寬度限制
        self.le_win_x.setMaximumWidth(80)
        self.le_win_y.setMaximumWidth(80)
        self.le_win_width.setMaximumWidth(80)
        self.le_win_height.setMaximumWidth(80)
        
        g1.addWidget(QLabel("視窗標題關鍵字："), 0, 0)
        g1.addWidget(self.le_title, 0, 1, 1, 2)
        g1.addWidget(btn_resize, 0, 3)
        
        g1.addWidget(QLabel("視窗位置 X："), 1, 0)
        g1.addWidget(self.le_win_x, 1, 1)
        g1.addWidget(QLabel("Y："), 1, 2)
        g1.addWidget(self.le_win_y, 1, 3)
        
        g1.addWidget(QLabel("視窗尺寸 寬："), 2, 0)
        g1.addWidget(self.le_win_width, 2, 1)
        g1.addWidget(QLabel("高："), 2, 2)
        g1.addWidget(self.le_win_height, 2, 3)
        
        grp_win.setLayout(g1)

        # --- 區域設定 ---
        grp_region = QGroupBox("偵測區域")
        g3 = QGridLayout()
        self.le_icon_region = QLineEdit()
        self.le_char_region = QLineEdit()
        b4 = QPushButton("框選『集合圖標』區域")
        b5 = QPushButton("框選『人物活動』區域")
        b6 = QPushButton("顯示預覽")
        b6.setMaximumWidth(80)
        b6.clicked.connect(self.show_current_region_preview)
        b4.clicked.connect(lambda: self.pick_region(self.le_icon_region))
        b5.clicked.connect(lambda: self.pick_region(self.le_char_region))
        g3.addWidget(QLabel("集合圖標區域："), 0, 0)
        g3.addWidget(self.le_icon_region, 0, 1)
        g3.addWidget(b4, 0, 2)
        g3.addWidget(QLabel("人物活動區域："), 1, 0)
        g3.addWidget(self.le_char_region, 1, 1)
        g3.addWidget(b5, 1, 2)
        g3.addWidget(b6, 2, 0)
        grp_region.setLayout(g3)

        # --- 控制 ---
        grp_ctrl = QGroupBox("控制")
        
        # 控制按鈕佈局
        control_layout = QHBoxLayout()
        self.btn_start = QPushButton("Start")
        self.btn_pause = QPushButton("Pause")
        self.btn_resume = QPushButton("Resume")
        self.btn_stop = QPushButton("Stop")
        self.btn_start.clicked.connect(self.on_start)
        self.btn_pause.clicked.connect(self.on_pause)
        self.btn_resume.clicked.connect(self.on_resume)
        self.btn_stop.clicked.connect(self.on_stop)
        
        control_layout.addWidget(self.btn_start)
        control_layout.addWidget(self.btn_pause)
        control_layout.addWidget(self.btn_resume)
        control_layout.addWidget(self.btn_stop)
        
        # 添加分隔線和設定按鈕
        control_layout.addWidget(self._create_vertical_line())
        
        # 齒輪設定按鈕
        self.btn_settings = QPushButton()
        
        # 嘗試載入齒輪圖標，如果失敗則使用文字
        try:
            if os.path.exists("gear_icon_24.png"):
                self.btn_settings.setIcon(QIcon("gear_icon_24.png"))
                self.btn_settings.setText("")
            else:
                self.btn_settings.setText("⚙")  # 備用齒輪圖標
        except:
            self.btn_settings.setText("設定")  # 最終備用方案
            
        self.btn_settings.setToolTip("參數設定")
        self.btn_settings.setFixedSize(32, 32)  # 稍微增大一點
        self.btn_settings.setStyleSheet("""
            QPushButton {
                font-size: 16px;
                border: 1px solid #ccc;
                border-radius: 6px;
                background-color: #f8f8f8;
                padding: 2px;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
                border-color: #999;
            }
            QPushButton:pressed {
                background-color: #d8d8d8;
                border-color: #666;
            }
        """)
        self.btn_settings.clicked.connect(self.on_settings)
        control_layout.addWidget(self.btn_settings)
        
        grp_ctrl.setLayout(control_layout)
        
        self.update_button_status("stopped")

        # --- Log ---
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(180)

        layout.addWidget(grp_win)
        layout.addWidget(grp_region)
        layout.addWidget(grp_ctrl)
        layout.addWidget(QLabel("Log"))
        layout.addWidget(self.log)
        
        # 預覽區域標題欄（包含隱藏按鈕）
        preview_header = QHBoxLayout()
        self.preview_title_label = QLabel("區域預覽")
        self.preview_hide_btn = QPushButton("隱藏預覽")
        self.preview_hide_btn.setMaximumWidth(80)
        self.preview_hide_btn.clicked.connect(self.hide_preview)
        preview_header.addWidget(self.preview_title_label)
        preview_header.addStretch()
        preview_header.addWidget(self.preview_hide_btn)
        
        preview_header_widget = QWidget()
        preview_header_widget.setLayout(preview_header)
        self.preview_header_widget = preview_header_widget
        self.preview_header_widget.hide()
        
        layout.addWidget(self.preview_header_widget)
        layout.addWidget(self.preview_label)

        # Save on close
        self.setLayout(layout)
        
        # 設定視窗大小策略，允許自動調整
        layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)

    def _load_cfg_to_ui(self):
        self.le_title.setText(self.cfg["TARGET_TITLE_KEYWORD"])
        self.le_icon_region.setText(",".join(map(str, self.cfg["ICON_SEARCH_REGION"])))
        self.le_char_region.setText(",".join(map(str, self.cfg["CHARACTER_SEARCH_REGION"])))
        
        # 載入視窗位置和尺寸設定
        self.le_win_x.setText(str(self.cfg["WINDOW_POSITION_X"]))
        self.le_win_y.setText(str(self.cfg["WINDOW_POSITION_Y"]))
        self.le_win_width.setText(str(self.cfg["WINDOW_WIDTH"]))
        self.le_win_height.setText(str(self.cfg["WINDOW_HEIGHT"]))

    def _logical_to_device_rect(self, x, y, w, h):
        """把 Qt『邏輯像素』矩形轉成螢幕『實際像素』矩形（配合高 DPI）。"""
        try:
            screen = QGuiApplication.screenAt(QPoint(x, y)) or QGuiApplication.primaryScreen()
            dpr = screen.devicePixelRatio()
            
            # 如果 DPI 比例無效，嘗試其他方法
            if not dpr or dpr <= 0:
                try:
                    dpr = screen.logicalDotsPerInchX() / 96.0
                except Exception:
                    dpr = 1.0
            
            # 在某些系統上 DPI 比例可能不需要調整
            if dpr == 1.0:
                self.append_log(f"DPI 比例為 1.0，不進行縮放")
                return int(x), int(y), int(w), int(h)
            
            result_x = round(x * dpr)
            result_y = round(y * dpr) 
            result_w = round(w * dpr)
            result_h = round(h * dpr)
            
            self.append_log(f"DPI 轉換: 比例={dpr:.2f}, 原始({x},{y},{w},{h}) -> 結果({result_x},{result_y},{result_w},{result_h})")
            return result_x, result_y, result_w, result_h
            
        except Exception as e:
            self.append_log(f"DPI 轉換失敗: {e}，使用原始值")
            return int(x), int(y), int(w), int(h)


    def _ui_to_cfg(self):
        self.cfg["TARGET_TITLE_KEYWORD"] = self.le_title.text().strip()
        
        # 安全解析視窗位置和尺寸
        try:
            self.cfg["WINDOW_POSITION_X"] = int(self.le_win_x.text().strip() or "0")
            self.cfg["WINDOW_POSITION_Y"] = int(self.le_win_y.text().strip() or "0")
            self.cfg["WINDOW_WIDTH"] = int(self.le_win_width.text().strip() or "1280")
            self.cfg["WINDOW_HEIGHT"] = int(self.le_win_height.text().strip() or "720")
        except ValueError as e:
            self.append_log(f"[警告] 視窗位置/尺寸格式錯誤: {e}")
        
        # 安全解析區域資訊
        try:
            icon_text = self.le_icon_region.text().strip()
            if icon_text and "," in icon_text:
                self.cfg["ICON_SEARCH_REGION"] = list(map(int, icon_text.split(",")))
        except ValueError as e:
            self.append_log(f"[警告] 目標圖標區域格式錯誤: {e}")
            
        try:
            char_text = self.le_char_region.text().strip()
            if char_text and "," in char_text:
                self.cfg["CHARACTER_SEARCH_REGION"] = list(map(int, char_text.split(",")))
        except ValueError as e:
            self.append_log(f"[警告] 人物區域格式錯誤: {e}")

    # ------- UI handlers -------
    def pick_region(self, lineedit: QLineEdit):
        # 若之前有尚未關閉的 overlay，先關閉
        if self._picker is not None:
            try:
                self._picker.close()
            except:
                pass
            self._picker = None

        self.append_log("開始框選區域，請在螢幕上拖拽選擇區域...")
        
        # 顯示預覽區域
        self.preview_header_widget.show()
        self.preview_label.show()
        self.preview_label.setText("正在等待框選...")
        
        # 自動調整視窗大小以容納預覽區域
        from PySide6.QtCore import QTimer
        QTimer.singleShot(10, self._adjust_window_size)
        
        # 暫時隱藏主視窗，避免干擾框選
        self.setWindowState(Qt.WindowState.WindowMinimized)
        
        # 建立並保留參考（避免被回收）
        self._picker = RegionPicker()
        self._picker.picked.connect(lambda r: self._on_region_picked_and_restore(lineedit, r))
        
        # 使用定時器確保視窗顯示
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, self._show_picker)

    def _show_picker(self):
        """延遲顯示框選器，確保主視窗已經最小化"""
        if self._picker:
            print("顯示框選器...")
            self._picker.show()
            self._picker.raise_()
            self._picker.activateWindow()
            self._picker.setFocus()
            print("框選器已顯示，等待用戶操作...")

    def _on_region_picked_and_restore(self, lineedit: QLineEdit, region_logical: tuple):
        """處理區域選擇完成並恢復主視窗"""
        print("開始恢復主視窗...")
        
        # 立即恢復主視窗
        self.setWindowState(Qt.WindowState.WindowNoState)
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()
        
        print("主視窗已恢復，處理選擇區域...")
        
        # 處理選擇的區域
        self._on_region_picked(lineedit, region_logical)
        
        # 延遲調整視窗大小
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, self._adjust_window_size)
        
        print("區域處理完成")

    def on_resize_window(self):
        self._ui_to_cfg(); save_cfg(self.cfg)
        key = self.cfg["TARGET_TITLE_KEYWORD"]
        self.append_log(f"尋找標題包含：{key}")
        try:
            found = None
            for w in gw.getAllWindows():
                if key in w.title:
                    found = w; break
            if not found:
                self.append_log("找不到視窗")
                return
            # 使用 pyautogui Window 物件搬移/調整大小
            pgw = pyautogui.getWindowsWithTitle(found.title)[0]
            pgw.moveTo(self.cfg["WINDOW_POSITION_X"], self.cfg["WINDOW_POSITION_Y"])
            pgw.resizeTo(self.cfg["WINDOW_WIDTH"], self.cfg["WINDOW_HEIGHT"])
            time.sleep(0.8)
            self.append_log(f"已調整：({pgw.left},{pgw.top}) {pgw.width}x{pgw.height}")
        except Exception as e:
            self.append_log(f"[調整視窗失敗] {e}")

    def update_button_status(self, status):
        """
        status: "running", "paused", "stopped"
        """
        default_style = ""
        self.btn_start.setStyleSheet(default_style)
        self.btn_pause.setStyleSheet(default_style)
        self.btn_resume.setStyleSheet(default_style)
        self.btn_stop.setStyleSheet(default_style)
        
        if status == "running":
            self.btn_start.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        elif status == "paused":
            self.btn_pause.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold;")
        elif status == "stopped":
            self.btn_stop.setStyleSheet("background-color: #F44336; color: white; font-weight: bold;")

    def on_start(self):
        self._ui_to_cfg(); save_cfg(self.cfg)
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "提示", "已在執行中")
            return
        self.worker = DetectorWorker(self.cfg)
        self.worker.signals.log.connect(self.append_log)
        self.worker.signals.finished.connect(lambda: self.append_log("[Worker 結束]"))
        self.worker.signals.finished.connect(lambda: self.update_button_status("stopped"))
        self.worker.start()
        self.append_log("[Worker 啟動]")
        self.update_button_status("running")

    def on_pause(self):
        if self.worker and self.worker.isRunning():
            self.worker.pause()
            self.append_log("[暫停]")
            self.update_button_status("paused")

    def on_resume(self):
        if self.worker and self.worker.isRunning():
            self.worker.resume()
            self.append_log("[恢復]")
            self.update_button_status("running")

    def on_stop(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(2000)
            self.append_log("[停止]")
            self.update_button_status("stopped")

    def on_settings(self):
        """打開參數設定對話框"""
        try:
            dialog = ConfigDialog(self.cfg, self)
            if dialog.exec() == QDialog.Accepted:
                # 獲取更新後的配置
                self.cfg = dialog.get_config()
                # 保存配置到文件
                save_cfg(self.cfg)
                self.append_log("[設定] 參數設定已更新並儲存")
            else:
                self.append_log("[設定] 取消參數設定")
        except Exception as e:
            self.append_log(f"[設定錯誤] {e}")
            QMessageBox.warning(self, "錯誤", f"打開設定對話框時發生錯誤：{e}")

    def _on_region_picked(self, lineedit: QLineEdit, region_logical: tuple):
        # region_logical 是 Qt 的『邏輯像素』(x,y,w,h)
        lx, ly, lw, lh = region_logical
        self.append_log(f"框選邏輯座標: ({lx}, {ly}, {lw}, {lh})")

        # 轉成『實際像素』供 pyautogui / OpenCV 使用（避免高 DPI 偏移）
        dx, dy, dw, dh = self._logical_to_device_rect(lx, ly, lw, lh)
        self.append_log(f"轉換實際座標: ({dx}, {dy}, {dw}, {dh})")

        # 寫回輸入框：以『實際像素』為準
        lineedit.setText(f"{dx},{dy},{dw},{dh}")

        # 在 GUI 顯示縮圖預覽
        try:
            self.append_log(f"正在截取預覽: region=({dx}, {dy}, {dw}, {dh})")
            img = pyautogui.screenshot(region=(dx, dy, dw, dh)).convert("RGB")
            qimg = QImage(img.tobytes("raw", "RGB"), img.width, img.height, QImage.Format_RGB888)
            # 依 Label 大小縮放顯示
            if self.preview_label.width() > 0 and self.preview_label.height() > 0:
                pix = QPixmap.fromImage(qimg).scaled(
                    self.preview_label.width(), self.preview_label.height(),
                    Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
            else:
                pix = QPixmap.fromImage(qimg).scaledToWidth(360, Qt.SmoothTransformation)
            self.preview_label.setPixmap(pix)
            self.append_log("預覽圖片已更新")
        except Exception as e:
            self.append_log(f"[預覽失敗] {e}")

        # 釋放 overlay 參考
        self._picker = None

    def hide_preview(self):
        """隱藏預覽區域"""
        self.preview_header_widget.hide()
        self.preview_label.hide()
        self.append_log("預覽區域已隱藏")
        
        # 使用定時器延遲調整視窗大小，確保佈局更新完成
        from PySide6.QtCore import QTimer
        QTimer.singleShot(10, self._adjust_window_size)

    def show_current_region_preview(self):
        """顯示當前設定區域的預覽"""
        # 顯示預覽區域
        self.preview_header_widget.show()
        self.preview_label.show()
        
        # 自動調整視窗大小以容納預覽區域
        from PySide6.QtCore import QTimer
        QTimer.singleShot(10, self._adjust_window_size)
        
        # 嘗試預覽目標圖標區域（如果有設定的話）
        icon_text = self.le_icon_region.text().strip()
        char_text = self.le_char_region.text().strip()
        
        preview_region = None
        preview_name = ""
        
        if icon_text and "," in icon_text:
            try:
                values = list(map(int, icon_text.split(",")))
                if len(values) == 4:
                    preview_region = values
                    preview_name = "目標圖標區域"
            except ValueError:
                pass
        
        if not preview_region and char_text and "," in char_text:
            try:
                values = list(map(int, char_text.split(",")))
                if len(values) == 4:
                    preview_region = values
                    preview_name = "人物/箭頭區域"
            except ValueError:
                pass
        
        if preview_region:
            try:
                dx, dy, dw, dh = preview_region
                self.append_log(f"顯示 {preview_name} 預覽: ({dx}, {dy}, {dw}, {dh})")
                img = pyautogui.screenshot(region=(dx, dy, dw, dh)).convert("RGB")
                qimg = QImage(img.tobytes("raw", "RGB"), img.width, img.height, QImage.Format_RGB888)
                if self.preview_label.width() > 0 and self.preview_label.height() > 0:
                    pix = QPixmap.fromImage(qimg).scaled(
                        self.preview_label.width(), self.preview_label.height(),
                        Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                else:
                    pix = QPixmap.fromImage(qimg).scaledToWidth(360, Qt.SmoothTransformation)
                self.preview_label.setPixmap(pix)
                self.append_log(f"{preview_name} 預覽已更新")
            except Exception as e:
                self.preview_label.setText(f"預覽失敗: {e}")
                self.append_log(f"預覽失敗: {e}")
        else:
            self.preview_label.setText("請先設定區域座標")
            self.append_log("沒有有效的區域座標可以預覽")

    def _adjust_window_size(self):
        """調整視窗大小以適應內容"""
        self.adjustSize()
        # 獲取建議的大小
        hint = self.sizeHint()
        # 設定最小高度，避免視窗太小
        min_height = 400
        new_height = max(hint.height(), min_height)
        self.resize(hint.width(), new_height)

    def append_log(self, s):
        self.log.append(s)

    def closeEvent(self, e):
        try:
            self._ui_to_cfg(); save_cfg(self.cfg)
            if self.worker and self.worker.isRunning():
                self.worker.stop()
                self.worker.wait(1500)
        finally:
            return super().closeEvent(e)

# ==========================
# 入口
# ==========================
if __name__ == "__main__":
    import os
    import warnings
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    
    # 抑制 Qt DPI 相關警告
    os.environ['QT_LOGGING_RULES'] = 'qt.qpa.window.warning=false'
    
    # 建議：Windows 關閉 PyAutoGUI 失敗保護的 fail-safe（視需要）
    pyautogui.FAILSAFE = False

    app = QApplication(sys.argv)
    
    w = MainWindow()
    w.resize(500, 600)
    w.show()
    sys.exit(app.exec())
