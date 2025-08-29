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
# 資源文件路徑處理
# ==========================
def resource_path(relative_path):
    """獲取資源文件的絕對路徑，處理打包後的路徑"""
    try:
        # PyInstaller 打包後的臨時文件夾
        base_path = sys._MEIPASS
    except Exception:
        # 開發環境下的路徑
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)

# ==========================
# 設定檔處理
# ==========================
DEFAULT_CFG = {
    "TARGET_TITLE_KEYWORD": "Chrome",       # 預設關鍵字
    "WINDOW_POSITION_X": 0,
    "WINDOW_POSITION_Y": 0,
    "WINDOW_WIDTH": 1280,
    "WINDOW_HEIGHT": 720,

    "TARGET_IMAGE_PATH": "images/target.png",
    "CHARACTER_IMAGE_PATH": "images/character.png",
    "ARROW_IMAGE_PATH": "images/arrow.png",  # 只是給你保留選檔，實際偵測走顏色

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

    # 點擊參數
    "CLICK_RANDOM_OFFSET_X": 10,     # 隨機偏移X像素範圍
    "CLICK_RANDOM_OFFSET_Y": 10,     # 隨機偏移Y像素範圍
    "CLICK_COUNT_MIN": 2,            # 最少點擊次數
    "CLICK_COUNT_MAX": 4,            # 最多點擊次數
    "CLICK_INTERVAL_MIN": 0.08,      # 最短點擊間隔(秒)
    "CLICK_INTERVAL_MAX": 0.25,      # 最長點擊間隔(秒)

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
        
        # 設置窗口圖標
        zeny_ico_path = resource_path("zeny.ico")
        zeny_png_path = resource_path("zeny.png")
        if os.path.exists(zeny_ico_path):
            self.setWindowIcon(QIcon(zeny_ico_path))
        elif os.path.exists(zeny_png_path):
            self.setWindowIcon(QIcon(zeny_png_path))
        
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
        
        # 點擊隨機偏移X
        self.click_offset_x_spin = QSpinBox()
        self.click_offset_x_spin.setRange(0, 50)
        self.click_offset_x_spin.setValue(self.cfg["CLICK_RANDOM_OFFSET_X"])
        movement_layout.addRow("點擊隨機偏移X(像素):", self.click_offset_x_spin)
        
        # 點擊隨機偏移Y
        self.click_offset_y_spin = QSpinBox()
        self.click_offset_y_spin.setRange(0, 50)
        self.click_offset_y_spin.setValue(self.cfg["CLICK_RANDOM_OFFSET_Y"])
        movement_layout.addRow("點擊隨機偏移Y(像素):", self.click_offset_y_spin)
        
        # 點擊次數範圍
        self.click_count_min_spin = QSpinBox()
        self.click_count_min_spin.setRange(1, 10)
        self.click_count_min_spin.setValue(self.cfg["CLICK_COUNT_MIN"])
        
        self.click_count_max_spin = QSpinBox()
        self.click_count_max_spin.setRange(1, 10)
        self.click_count_max_spin.setValue(self.cfg["CLICK_COUNT_MAX"])
        
        click_count_layout = QHBoxLayout()
        click_count_layout.addWidget(QLabel("最少:"))
        click_count_layout.addWidget(self.click_count_min_spin)
        click_count_layout.addWidget(QLabel("最多:"))
        click_count_layout.addWidget(self.click_count_max_spin)
        movement_layout.addRow("點擊次數範圍:", click_count_layout)
        
        # 點擊間隔範圍
        self.click_interval_min_spin = QDoubleSpinBox()
        self.click_interval_min_spin.setRange(0.01, 1.0)
        self.click_interval_min_spin.setSingleStep(0.01)
        self.click_interval_min_spin.setDecimals(3)
        self.click_interval_min_spin.setValue(self.cfg["CLICK_INTERVAL_MIN"])
        
        self.click_interval_max_spin = QDoubleSpinBox()
        self.click_interval_max_spin.setRange(0.01, 1.0)
        self.click_interval_max_spin.setSingleStep(0.01)
        self.click_interval_max_spin.setDecimals(3)
        self.click_interval_max_spin.setValue(self.cfg["CLICK_INTERVAL_MAX"])
        
        click_interval_layout = QHBoxLayout()
        click_interval_layout.addWidget(QLabel("最短:"))
        click_interval_layout.addWidget(self.click_interval_min_spin)
        click_interval_layout.addWidget(QLabel("最長:"))
        click_interval_layout.addWidget(self.click_interval_max_spin)
        movement_layout.addRow("點擊間隔範圍(秒):", click_interval_layout)
        
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
        
        # 點擊設置
        self.click_offset_x_spin.setValue(DEFAULT_CFG["CLICK_RANDOM_OFFSET_X"])
        self.click_offset_y_spin.setValue(DEFAULT_CFG["CLICK_RANDOM_OFFSET_Y"])
        self.click_count_min_spin.setValue(DEFAULT_CFG["CLICK_COUNT_MIN"])
        self.click_count_max_spin.setValue(DEFAULT_CFG["CLICK_COUNT_MAX"])
        self.click_interval_min_spin.setValue(DEFAULT_CFG["CLICK_INTERVAL_MIN"])
        self.click_interval_max_spin.setValue(DEFAULT_CFG["CLICK_INTERVAL_MAX"])
        
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
        
        # 點擊設置
        self.cfg["CLICK_RANDOM_OFFSET_X"] = self.click_offset_x_spin.value()
        self.cfg["CLICK_RANDOM_OFFSET_Y"] = self.click_offset_y_spin.value()
        self.cfg["CLICK_COUNT_MIN"] = self.click_count_min_spin.value()
        self.cfg["CLICK_COUNT_MAX"] = self.click_count_max_spin.value()
        self.cfg["CLICK_INTERVAL_MIN"] = self.click_interval_min_spin.value()
        self.cfg["CLICK_INTERVAL_MAX"] = self.click_interval_max_spin.value()
        
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

    def click_center(self, location, scale, cfg=None):
        """點擊目標中心位置，支持可配置的隨機偏移和多次點擊"""
        cx, cy = self.get_center_position(location, scale)
        if cx and cy:
            # 使用傳入的配置或預設值
            if cfg is None:
                cfg = {
                    "CLICK_RANDOM_OFFSET_X": 10,
                    "CLICK_RANDOM_OFFSET_Y": 10,
                    "CLICK_COUNT_MIN": 2,
                    "CLICK_COUNT_MAX": 4,
                    "CLICK_INTERVAL_MIN": 0.08,
                    "CLICK_INTERVAL_MAX": 0.25
                }
            
            # 隨機決定點擊次數
            click_count = random.randint(cfg["CLICK_COUNT_MIN"], cfg["CLICK_COUNT_MAX"])
            sw, sh = pyautogui.size()
            
            for i in range(click_count):
                # 每次點擊都重新計算隨機偏移
                offx = random.randint(-cfg["CLICK_RANDOM_OFFSET_X"], cfg["CLICK_RANDOM_OFFSET_X"])
                offy = random.randint(-cfg["CLICK_RANDOM_OFFSET_Y"], cfg["CLICK_RANDOM_OFFSET_Y"])
                
                click_x = max(0, min(sw - 1, cx + offx))
                click_y = max(0, min(sh - 1, cy + offy))
                
                pyautogui.click(click_x, click_y)
                
                # 如果不是最後一次點擊，則等待隨機間隔
                if i < click_count - 1:
                    interval = random.uniform(cfg["CLICK_INTERVAL_MIN"], cfg["CLICK_INTERVAL_MAX"])
                    time.sleep(interval)
            
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

    def _circular_stats(self, angles_deg):
        """回傳 (均值角度deg, R, circular_std_deg)；angles_deg 為 list[float]"""
        if not angles_deg:
            return None, 0.0, None
        ang = np.deg2rad(np.array(angles_deg, dtype=np.float64))
        C = np.cos(ang).sum()
        S = np.sin(ang).sum()
        n = max(len(angles_deg), 1)
        R = np.sqrt(C*C + S*S) / n
        mean_rad = math.atan2(S, C)
        mean_deg = (math.degrees(mean_rad) + 360) % 360
        # circular std（R<=1），避免 log(0)
        R = max(min(R, 0.999999), 1e-6)
        circ_std_rad = math.sqrt(-2.0 * math.log(R))
        circ_std_deg = math.degrees(circ_std_rad)
        return mean_deg, R, circ_std_deg

    def _internal_angle_deg(self, a, b, c):
        """回傳點 b 的內角角度（a-b-c）"""
        v1 = a - b
        v2 = c - b
        n1 = np.linalg.norm(v1) + 1e-9
        n2 = np.linalg.norm(v2) + 1e-9
        cosang = np.clip(np.dot(v1, v2) / (n1 * n2), -1.0, 1.0)
        return math.degrees(math.acos(cosang))

    def _preprocess_red_mask(self, img_bgr):
        """
        回傳更穩定的紅色遮罩：
        - HSV 兩段紅 + 自適應 S/V 下限（使用百分位數）
        - Lab a* 強化紅色
        - 開閉運算去雜訊
        """
        hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)

        # 對 V 做 CLAHE 提升陰影區辨識
        h, s, v = cv2.split(hsv)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        v = clahe.apply(v)
        hsv = cv2.merge([h, s, v])

        # 自適應 S/V 下界（避免過暗或過灰被忽略）
        s_floor = int(np.percentile(s.flatten(), 70))
        v_floor = int(np.percentile(v.flatten(), 50))
        s_floor = max(60, min(180, s_floor - 10))
        v_floor = max(60, min(180, v_floor - 10))

        mask1 = cv2.inRange(hsv, (0,   s_floor, v_floor), (10, 255, 255))
        mask2 = cv2.inRange(hsv, (170, s_floor, v_floor), (180, 255, 255))
        mask_hsv = cv2.bitwise_or(mask1, mask2)

        # Lab a* 強化紅（a* 偏高代表偏紅）
        lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
        a = lab[:,:,1]
        a_thr = int(np.percentile(a.flatten(), 85))  # 偏嚴格，避免白/橙誤判
        mask_a = (a > a_thr).astype(np.uint8) * 255

        mask = cv2.bitwise_and(mask_hsv, mask_a)

        # 去雜訊（先開再閉）
        mask = cv2.medianBlur(mask, 3)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5,5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
        return mask

    def _score_arrow_candidate(self, cnt, center_xy):
        """
        對候選輪廓評分並求方向：
        - 盡量以「最銳利頂點」當箭頭尖端；找不到就用「距中心最遠點」
        - 回傳 (score, angle_deg, top_left, has_acute_tip)
        """
        area = cv2.contourArea(cnt)
        if area < self.min_area:
            return -1, None, None, False

        x, y, w, h = cv2.boundingRect(cnt)
        rect_area = max(w*h, 1)
        extent = area / rect_area
        if not (0.30 <= extent <= 0.92):
            return -1, None, None, False

        hull = cv2.convexHull(cnt)
        hull_area = cv2.contourArea(hull) or 1
        solidity = area / hull_area
        if solidity < 0.70:  # 稍微放寬，因為箭頭尖端會降低 solidity
            return -1, None, None, False

        peri = cv2.arcLength(cnt, True) or 1
        circularity = 4 * math.pi * area / (peri * peri)
        if circularity > 0.85:  # 越圓越不像箭頭
            return -1, None, None, False

        # 多邊形近似，找最小內角的頂點（箭頭尖端）
        eps = 0.02 * peri
        approx = cv2.approxPolyDP(cnt, eps, True)
        pts = approx.reshape(-1, 2).astype(np.float32)

        has_acute_tip = False
        tip = None
        if len(pts) >= 3:
            min_angle = 1e9
            for i in range(len(pts)):
                a = pts[(i-1) % len(pts)]
                b = pts[i]
                c = pts[(i+1) % len(pts)]
                ang = self._internal_angle_deg(a, b, c)
                if ang < min_angle:
                    min_angle = ang
                    tip = b
            if min_angle < 70:  # 夠尖，視為箭頭
                has_acute_tip = True

        cx, cy = center_xy
        if tip is None or not has_acute_tip:
            # 退而求其次：用相對人物中心最遠點
            cnt_pts = cnt.reshape(-1, 2).astype(np.float32)
            d2 = np.square(cnt_pts[:,0]-cx) + np.square(cnt_pts[:,1]-cy)
            tip = cnt_pts[int(np.argmax(d2))]

        dx = float(tip[0] - cx)
        dy = float(tip[1] - cy)
        angle_deg = (math.degrees(math.atan2(dx, -dy)) + 360) % 360

        # 綜合評分：面積、extent、solidity、是否有銳角尖端、長寬比
        ar = w / max(h, 1)
        ar_score = 1.0 if 0.4 <= ar <= 2.8 else 0.7
        tip_bonus = 1.25 if has_acute_tip else 1.0
        score = area * (0.45 + 0.25*extent + 0.20*solidity + 0.10*ar_score) * tip_bonus

        return score, angle_deg, (int(x), int(y)), has_acute_tip

    def find_arrow_by_color(self, search_center_x, search_center_y):
        """
        升級版：HSV+Lab 遮罩 + 尖端導向 + 穩定評分
        回： (top_left_global, 1.0, angle_deg) 或 (None, None, None)
        """
        r = self.arrow_search_radius
        sx = int(round(search_center_x - r))
        sy = int(round(search_center_y - r))
        sw = sh = int(round(2*r))
        sx, sy, sw, sh = clamp_region_to_screen(sx, sy, sw, sh)

        try:
            pil_img = pyautogui.screenshot(region=(sx, sy, sw, sh))
        except pyautogui.PyAutoGUIException:
            return None, None, None

        img = np.array(pil_img)[:, :, ::-1]  # to BGR
        mask = self._preprocess_red_mask(img)

        # 找候選
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        best = (-1, None, None, False)  # (score, angle, top_left, tipflag)
        for c in cnts:
            # 將局部座標換算為全域前，先用局部判斷
            score, ang, tl, tip_ok = self._score_arrow_candidate(c, center_xy=(r, r))
            if score > best[0]:
                best = (score, ang, tl, tip_ok)

        if best[0] < 0 or best[1] is None:
            return None, None, None

        # 轉回全域 top-left
        tl_local = best[2]
        top_left_global = (int(tl_local[0] + sx), int(tl_local[1] + sy))
        return top_left_global, 1.0, float(best[1])

    def wait_for_arrow(self, center_x, center_y):
        """
        收集樣本直到：
        - 命中數量 >= min_hits，且
        - 角度「環向標準差」足夠小（例如 <= 14°）→ 早收斂
        超時仍不足則維持舊邏輯。
        """
        angles = []
        last_loc = None
        t0 = time.time()

        # 可視情況微調
        early_stop_std_deg = 14.0

        while time.time() - t0 < self.timeout:
            loc, _, ang = self.find_arrow_by_color(center_x, center_y)
            if loc is not None and ang is not None:
                angles.append(ang)
                last_loc = loc

                if len(angles) >= self.min_hits:
                    mean_deg, R, std_deg = self._circular_stats(angles)
                    # 集中度高（std 小）則提前返回
                    if std_deg is not None and std_deg <= early_stop_std_deg:
                        return last_loc, mean_deg, len(angles)
            time.sleep(self.poll)

        if len(angles) >= self.min_hits:
            mean_deg, _, _ = self._circular_stats(angles)
            return last_loc, mean_deg, len(angles)
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
                    icon.click_center(current_location, current_scale, self.cfg)
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
                            icon.click_center(current_location, current_scale, self.cfg)
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
# 半透明區域預覽遮罩
# ==========================
class RegionPreviewOverlay(QWidget):
    def __init__(self, regions_list, main_window_ref=None):
        """
        初始化區域預覽遮罩
        regions_list: 包含 (region_rect, title, color) 的列表
        main_window_ref: 主視窗參考，用於DPI轉換
        """
        super().__init__()
        self.regions_list = regions_list
        self.main_window = main_window_ref
        
        # 設置窗口圖標
        zeny_ico_path = resource_path("zeny.ico")
        zeny_png_path = resource_path("zeny.png")
        if os.path.exists(zeny_ico_path):
            self.setWindowIcon(QIcon(zeny_ico_path))
        elif os.path.exists(zeny_png_path):
            self.setWindowIcon(QIcon(zeny_png_path))
        
        # 設定視窗屬性 - 全螢幕遮罩
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool |
            Qt.WindowSystemMenuHint
        )
        
        # 設定透明背景
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        
        # 覆蓋整個虛擬桌面（多螢幕）
        vg = QGuiApplication.primaryScreen().virtualGeometry()
        self.setGeometry(vg)
        
        # 顯示遮罩
        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        self.setFocus()
        
        region_names = [item[1] for item in regions_list]
        print(f"區域預覽遮罩已顯示: {', '.join(region_names)}")

    def keyPressEvent(self, e):
        # 按 ESC 關閉預覽
        if e.key() == Qt.Key_Escape:
            print("用戶按下 ESC 鍵，關閉預覽")
            self.close()

    def mousePressEvent(self, e):
        # 點擊任何地方都關閉預覽
        print("用戶點擊螢幕，關閉預覽")
        self.close()

    def paintEvent(self, e):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 繪製半透明黑色遮罩覆蓋整個螢幕
        painter.fillRect(self.rect(), QColor(0, 0, 0, 120))
        
        # 為每個區域繪製透明區域和邊框
        colors = [
            QColor(0, 255, 0, 255),    # 綠色
            QColor(255, 165, 0, 255),  # 橙色
            QColor(0, 191, 255, 255),  # 深天藍色
            QColor(255, 20, 147, 255), # 深粉色
        ]
        
        for i, (region_rect, title, custom_color) in enumerate(self.regions_list):
            if region_rect:
                # 使用自定義顏色或默認顏色
                color = custom_color if custom_color else colors[i % len(colors)]
                
                # 選擇區域顯示透明（清除遮罩）
                painter.setCompositionMode(QPainter.CompositionMode_Clear)
                painter.fillRect(region_rect, QColor(0, 0, 0, 0))
                
                # 恢復正常繪製模式
                painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
                
                # 繪製彩色邊框
                pen = QPen(color, 4, Qt.SolidLine)
                painter.setPen(pen)
                painter.drawRect(region_rect)
                
                # 顯示區域資訊
                painter.setPen(QPen(QColor(255, 255, 255, 255), 2))
                painter.setFont(painter.font())
                text = f"{title}: ({region_rect.x()}, {region_rect.y()}) {region_rect.width()}×{region_rect.height()}"
                
                # 在區域上方顯示文字，確保不超出螢幕邊界
                text_pos = region_rect.topLeft() + QPoint(5, -10)
                if text_pos.y() < 20:
                    text_pos = region_rect.bottomLeft() + QPoint(5, 20)
                painter.drawText(text_pos, text)
        
        # 在螢幕中央顯示操作提示
        painter.setPen(QPen(QColor(255, 255, 255, 200), 2))
        painter.setFont(painter.font())
        hint_text = "按 ESC 鍵或點擊任意地方關閉預覽"
        hint_rect = painter.fontMetrics().boundingRect(hint_text)
        screen_center = self.rect().center()
        hint_pos = QPoint(screen_center.x() - hint_rect.width() // 2, 50)
        painter.drawText(hint_pos, hint_text)

# ==========================
# 矩形框選 Overlay
# ==========================
class RegionPicker(QWidget):
    picked = Signal(tuple)  # (x,y,w,h) - 邏輯像素

    def __init__(self):
        super().__init__()
        self.setWindowTitle("選擇區域")
        
        # 設置窗口圖標
        zeny_ico_path = resource_path("zeny.ico")
        zeny_png_path = resource_path("zeny.png")
        if os.path.exists(zeny_ico_path):
            self.setWindowIcon(QIcon(zeny_ico_path))
        elif os.path.exists(zeny_png_path):
            self.setWindowIcon(QIcon(zeny_png_path))
        
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
        
        # 設置窗口圖標
        zeny_ico_path = resource_path("zeny.ico")
        zeny_png_path = resource_path("zeny.png")
        if os.path.exists(zeny_ico_path):
            self.setWindowIcon(QIcon(zeny_ico_path))
        elif os.path.exists(zeny_png_path):
            self.setWindowIcon(QIcon(zeny_png_path))
        
        self.cfg = load_cfg()
        self.worker = None
        self._picker = None 
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
        b6 = QPushButton("螢幕預覽")
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
        
        # 嘗試載入內嵌的齒輪圖標
        try:
            # 優先嘗試從內部資源載入
            gear_icon_path = resource_path("gear_icon_24.png")
            if os.path.exists(gear_icon_path):
                self.btn_settings.setIcon(QIcon(gear_icon_path))
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

    def _device_to_logical_rect(self, x, y, w, h):
        """把螢幕『實際像素』矩形轉成 Qt『邏輯像素』矩形（用於預覽顯示）。"""
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
                return int(x), int(y), int(w), int(h)
            
            result_x = round(x / dpr)
            result_y = round(y / dpr) 
            result_w = round(w / dpr)
            result_h = round(h / dpr)
            
            self.append_log(f"逆DPI 轉換: 比例={dpr:.2f}, 實際({x},{y},{w},{h}) -> 邏輯({result_x},{result_y},{result_w},{result_h})")
            return result_x, result_y, result_w, result_h
            
        except Exception as e:
            self.append_log(f"逆DPI 轉換失敗: {e}，使用原始值")
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

        self.append_log("區域選擇完成")

        # 釋放 overlay 參考
        self._picker = None

    def show_current_region_preview(self):
        """使用半透明遮罩顯示當前設定區域的預覽（支援多區域同時顯示）"""
        icon_text = self.le_icon_region.text().strip()
        char_text = self.le_char_region.text().strip()
        
        regions_to_preview = []
        
        # 檢查目標圖標區域
        if icon_text and "," in icon_text:
            try:
                values = list(map(int, icon_text.split(",")))
                if len(values) == 4:
                    # 輸入框中儲存的是實際像素座標，需要轉換為邏輯像素用於Qt顯示
                    dx, dy, dw, dh = values
                    lx, ly, lw, lh = self._device_to_logical_rect(dx, dy, dw, dh)
                    region_rect = QRect(lx, ly, lw, lh)
                    regions_to_preview.append((region_rect, "目標圖標區域", QColor(0, 255, 0, 255)))  # 綠色
                    self.append_log(f"準備預覽目標圖標區域: 實際({dx}, {dy}, {dw}, {dh}) -> 邏輯({lx}, {ly}, {lw}, {lh})")
            except ValueError:
                self.append_log("目標圖標區域格式錯誤，請使用 x,y,w,h 格式")
        
        # 檢查人物活動區域
        if char_text and "," in char_text:
            try:
                values = list(map(int, char_text.split(",")))
                if len(values) == 4:
                    # 輸入框中儲存的是實際像素座標，需要轉換為邏輯像素用於Qt顯示
                    dx, dy, dw, dh = values
                    lx, ly, lw, lh = self._device_to_logical_rect(dx, dy, dw, dh)
                    region_rect = QRect(lx, ly, lw, lh)
                    regions_to_preview.append((region_rect, "人物活動區域", QColor(255, 165, 0, 255)))  # 橙色
                    self.append_log(f"準備預覽人物活動區域: 實際({dx}, {dy}, {dw}, {dh}) -> 邏輯({lx}, {ly}, {lw}, {lh})")
            except ValueError:
                self.append_log("人物活動區域格式錯誤，請使用 x,y,w,h 格式")

        if regions_to_preview:
            try:
                self.preview_overlay = RegionPreviewOverlay(regions_to_preview, self)
                region_names = [item[1] for item in regions_to_preview]
                self.append_log(f"半透明預覽遮罩已顯示: {', '.join(region_names)}，按 ESC 或點擊任意地方關閉")
            except Exception as e:
                self.append_log(f"預覽遮罩顯示失敗: {e}")
        else:
            self.append_log("請先設定目標圖標區域或人物活動區域後再預覽")
            QMessageBox.information(self, "提示", "請先設定目標圖標區域或人物活動區域後再預覽")

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
