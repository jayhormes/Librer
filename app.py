# app.py
import sys, os, json, time, math, random, threading, requests, gc
import numpy as np
import cv2
import pyautogui
import pygetwindow as gw
from datetime import datetime

# 穩定性監控
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("[警告] psutil 未安裝，無法進行記憶體監控")

from PySide6.QtCore import Qt, QRect, QPoint, Signal, QObject, QThread
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, QFileDialog,
    QGridLayout, QGroupBox, QTextEdit, QHBoxLayout, QVBoxLayout, QMessageBox,
    QSizePolicy, QDialog, QSlider, QSpinBox, QDoubleSpinBox, QFormLayout, QTabWidget, QComboBox, QCheckBox
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

def config_file_path(relative_path):
    """獲取配置和資源文件路徑，優先使用執行檔目錄"""
    # 執行檔所在目錄
    if getattr(sys, 'frozen', False):
        # 打包後的執行檔目錄
        exe_dir = os.path.dirname(sys.executable)
    else:
        # 開發環境
        exe_dir = os.path.abspath(".")
    
    exe_path = os.path.join(exe_dir, relative_path)
    
    # 如果執行檔目錄有這個檔案，就用執行檔目錄的
    if os.path.exists(exe_path):
        return exe_path
    
    # 否則回退到內嵌資源路徑
    return resource_path(relative_path)

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

    # 連續導航/穩定性
    "DRAG_STEP_PIXELS": 60,         # 每次小步前進距離（像素）
    "DRAG_MAX_SECONDS": 5.0,        # 單次導航最長時間（秒）
    "DRAG_HOLD_MIN": 0.5,           # 最短握住時間（秒）＝小步
    "DRAG_HOLD_MAX": 5.0,          # 最長握住時間（秒）＝方向很準時就多走一些
    "DRAG_SESSION_MAX": 6.0,        # 單次導航上限秒數（安全網）
    "ANGLE_OK_STD": 12.0,           # 視為角度穩定的環向標準差（度）→ 可提前持續拖曳
    
    # 圓環檢測參數（增強版人物檢測）
    "RING_DETECTION_ENABLED": True,     # 是否啟用圓環檢測
    "RING_CIRCLE_R_MIN": 18,            # 圓環最小半徑
    "RING_CIRCLE_R_MAX": 40,            # 圓環最大半徑
    "RING_WHITE_V_THRESH": 200,         # 白色亮度閾值
    "RING_WHITE_S_MAX": 60,             # 白色飽和度最大值
    "RING_CONSISTENCY": 0.55,           # 圓周白色比例閾值
    "RING_REFINE_WINDOW": 120,          # 模板驗證窗口大小
    "RING_TEMPLATE_CONFIDENCE": 0.82,   # 模板二次驗證閾值
    
    # 圖標增強檢測參數
    "ICON_ENHANCED_DETECTION": True,    # 是否啟用圖標增強檢測
    "ICON_MASK_ALPHA": 0.5,             # 灰階+遮罩 與 邊緣 的融合權重
    "ICON_RATIO_THRESHOLD": 1.12,       # 最佳/次佳 比例門檻
    "ICON_ENHANCED_CONFIDENCE": 0.84,   # 增強檢測信心度閾值
    "ANGLE_RELOCK_STD": 25.0,       # 角度發散時「重新鎖定」的門檻（度），高於此值暫停拖
    "ANGLE_ABORT_DEG": 60.0,        # 與上次方向差超過此角度則視為大幅偏離，停止這輪
    "ANGLE_SMOOTH_ALPHA": 0.35,     # 角度 EMA 平滑係數（0~1）
    "ARROW_MISS_TOLERANCE": 4,      # 連續幾次找不到箭頭才視為「箭頭消失」

    # 動態拖曳反饋參數
    "DRAG_FEEDBACK_INTERVAL": 0.15, # 動態拖曳中檢查箭頭間隔（秒）
    "DRAG_ANGLE_TOLERANCE": 25.0,   # 動態拖曳中角度變化容忍度（度）
    "DRAG_MIN_TIME": 0.3,           # 動態拖曳最短時間（秒）
    
    # 呼吸式箭頭處理參數
    "ARROW_BREATHING_CYCLE": 1.0,    # 箭頭呼吸週期（秒）
    "ARROW_MISS_TOLERANCE_TIME": 0.5, # 容忍箭頭消失時間（秒）
    "DIRECTION_CHANGE_THRESHOLD": 3,  # 方向改變確認次數

    # 視窗聚焦功能
    "ENABLE_WINDOW_FOCUS": True,        # 是否啟用視窗聚焦功能
    "WINDOW_FOCUS_ON_DETECTION": True,  # 在偵測到圖標時聚焦視窗
    
    # Discord Webhook 通知設定
    "ENABLE_DISCORD_WEBHOOK": False,    # 是否啟用 Discord Webhook 通知
    "DISCORD_NOTIFICATION_TIMEOUT": 300, # 多少秒沒偵測到圖標後發送通知 (預設5分鐘)
    "DISCORD_SELECTED_CHANNEL": "嘎嘎",  # 預設選擇的頻道
    "DISCORD_CHANNELS": {               # 預設頻道列表
        "嘎嘎": "https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN",
        "斯拉": "https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN", 
        "毛": "https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN",
        "樹": "https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN",
        "棋": "https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN"
    },
    
    # 主流程
    "MAX_ARROW_ATTEMPTS": 6,
    "MAIN_SEARCH_INTERVAL": 0.6,
    "PREVENTIVE_CLICK_DELAY": 0.2,
    "POST_MOVE_DELAY": 0.25,
    "FINAL_CHECK_DELAY": 0.2,
    "ARROW_SEARCH_INTERVAL": 0.2,
    
    # 日誌管理
    "LOG_MAX_LINES": 500,           # 最大日誌行數，超過會自動清理
    "LOG_CLEANUP_LINES": 100,       # 清理時保留的行數
    "LOG_AUTO_CLEANUP": True,       # 是否啟用自動日誌清理
    
    # 穩定性設定
    "MEMORY_CHECK_INTERVAL": 300,   # 記憶體檢查間隔（秒）
    "MEMORY_WARNING_THRESHOLD": 500, # 記憶體警告閾值（MB）
    "GC_FORCE_INTERVAL": 300,       # 強制垃圾回收間隔（秒）
    "LOOP_STATUS_INTERVAL": 1000,   # 循環狀態報告間隔
    "WORKER_STOP_TIMEOUT": 5000,    # Worker停止超時（毫秒）
    "EXCEPTION_RETRY_COUNT": 3,     # 異常重試次數
    "EXCEPTION_RETRY_DELAY": 0.5,   # 異常重試延遲（秒）
    
    # 日誌安全設定
    "LOG_SAFE_MODE": True,          # 啟用安全日誌模式
    "LOG_MAX_MSG_LENGTH": 500,      # 單條日誌最大長度
    "LOG_CLEANUP_FREQUENCY": 10,    # 每N條日誌檢查一次清理需求
    "LOG_USE_FALLBACK": True,       # 啟用備用清理方案
    "LOG_DISABLE_ON_ERROR": True,   # 錯誤時禁用日誌功能
    
    # 日誌UI設定
    "LOG_AUTO_SCROLL": True,        # 預設啟用自動置底
    "LOG_SHOW_CONTROLS": True,      # 顯示日誌控制按鈕
    "LOG_SCROLL_SENSITIVITY": 10,   # 滾動敏感度（像素）
}

CFG_PATH = config_file_path("config.json")

def load_cfg():
    cfg_path = config_file_path("config.json")
    if os.path.exists(cfg_path):
        with open(cfg_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # 舊檔案補缺欄
        for k,v in DEFAULT_CFG.items():
            if k not in data:
                data[k] = v
        return data
    return DEFAULT_CFG.copy()

def save_cfg(cfg):
    cfg_path = config_file_path("config.json")
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

# ==========================
# Discord Webhook 通知功能
# ==========================
class DiscordNotifier:
    """Discord Webhook 通知器"""
    
    def __init__(self, cfg):
        self.cfg = cfg
        self.last_detection_time = time.time()  # 最後檢測到圖標的時間
        self.notification_sent = False  # 是否已發送通知
        
    def update_detection_time(self):
        """更新最後檢測時間"""
        self.last_detection_time = time.time()
        self.notification_sent = False  # 重置通知狀態
        
    def check_and_notify(self):
        """檢查是否需要發送通知"""
        if not self.cfg.get("ENABLE_DISCORD_WEBHOOK", False):
            return
            
        if self.notification_sent:
            return
            
        # 計算沒有檢測到圖標的時間
        no_detection_time = time.time() - self.last_detection_time
        timeout = self.cfg.get("DISCORD_NOTIFICATION_TIMEOUT", 300)
        
        if no_detection_time >= timeout:
            self.send_notification()
            self.notification_sent = True
            
    def send_notification(self):
        """發送 Discord 通知"""
        try:
            selected_channel = self.cfg.get("DISCORD_SELECTED_CHANNEL", "嘎嘎")
            channels = self.cfg.get("DISCORD_CHANNELS", {})
            webhook_url = channels.get(selected_channel, "")
            
            if not webhook_url:
                print(f"[Discord] 頻道 '{selected_channel}' 的 Webhook URL 未設定")
                return
                
            # 計算沒有檢測時間
            no_detection_time = time.time() - self.last_detection_time
            minutes = int(no_detection_time // 60)
            seconds = int(no_detection_time % 60)
            
            # 構建通知消息
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            embed = {
                "title": "🔍 圖標檢測警告",
                "description": f"已經 **{minutes}分{seconds}秒** 沒有檢測到目標圖標！",
                "color": 0xff6b6b,  # 紅色
                "timestamp": datetime.utcnow().isoformat() + "Z",  # 使用 UTC 時間
                "fields": [
                    {
                        "name": "⏰ 最後檢測時間",
                        "value": datetime.fromtimestamp(self.last_detection_time).strftime("%H:%M:%S"),
                        "inline": True
                    },
                    {
                        "name": "📍 通知頻道",
                        "value": selected_channel,
                        "inline": True
                    },
                    {
                        "name": "⚠️ 狀態",
                        "value": "需要檢查應用程式",
                        "inline": False
                    }
                ],
                "footer": {
                    "text": "Librer"
                }
            }
            
            payload = {
                "embeds": [embed],
                "username": "Librer Bot",
                "avatar_url": "https://cdn.discordapp.com/emojis/1234567890123456789.png"  # 可選的頭像
            }
            
            response = requests.post(webhook_url, json=payload, timeout=10)
            
            if response.status_code == 204:
                print(f"[Discord] 成功發送通知到頻道: {selected_channel}")
            else:
                print(f"[Discord] 發送通知失敗: {response.status_code} - {response.text}")
                
        except requests.exceptions.RequestException as e:
            print(f"[Discord] 網路錯誤: {e}")
        except Exception as e:
            print(f"[Discord] 發送通知時出現錯誤: {e}")
            
    def send_test_notification(self, channel_name, webhook_url):
        """發送測試通知"""
        try:
            if not webhook_url:
                return False, "Webhook URL 不能為空"
                
            embed = {
                "title": "✅ 測試通知",
                "description": "這是一個測試通知，確認 Webhook 設定正確！",
                "color": 0x00ff00,  # 綠色
                "timestamp": datetime.utcnow().isoformat() + "Z",  # 使用 UTC 時間
                "fields": [
                    {
                        "name": "📍 測試頻道",
                        "value": channel_name,
                        "inline": True
                    },
                    {
                        "name": "⏰ 測試時間",
                        "value": datetime.now().strftime("%H:%M:%S"),
                        "inline": True
                    }
                ],
                "footer": {
                    "text": "Librer - 測試模式"
                }
            }
            
            payload = {
                "embeds": [embed],
                "username": "Librer Bot (測試)",
                "avatar_url": "https://cdn.discordapp.com/emojis/1234567890123456789.png"
            }
            
            response = requests.post(webhook_url, json=payload, timeout=10)
            
            if response.status_code == 204:
                return True, "測試通知發送成功！"
            else:
                return False, f"發送失敗: {response.status_code} - {response.text}"
                
        except requests.exceptions.RequestException as e:
            return False, f"網路錯誤: {e}"
        except Exception as e:
            return False, f"發送錯誤: {e}"

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
    try:
        sw, sh = pyautogui.size()
        x = int(round(max(0, min(x, sw - 1))))
        y = int(round(max(0, min(y, sh - 1))))
        w = int(round(max(1, min(w, sw - x))))
        h = int(round(max(1, min(h, sh - y))))
        return x, y, w, h
    except Exception as e:
        print(f"[警告] 螢幕區域限制失敗: {e}")
        # 返回安全的預設值
        return 0, 0, 100, 100

# ==========================
# 視窗管理功能
# ==========================
class WindowManager:
    def __init__(self, title_keyword=""):
        self.title_keyword = title_keyword
        self.target_window = None
        self.window_status = "unknown"  # unknown, found, not_found
        
    def update_keyword(self, keyword):
        """更新目標視窗關鍵字"""
        self.title_keyword = keyword
        self.target_window = None
        self.window_status = "unknown"
    
    def find_target_window(self):
        """尋找目標視窗"""
        if not self.title_keyword:
            self.window_status = "not_found"
            return None
            
        try:
            # 使用 pygetwindow 尋找包含關鍵字的視窗
            windows = gw.getWindowsWithTitle(self.title_keyword)
            if windows:
                # 找到第一個匹配的視窗
                self.target_window = windows[0]
                self.window_status = "found"
                return self.target_window
            else:
                # 如果完全匹配失敗，嘗試模糊搜尋
                all_windows = gw.getAllWindows()
                for window in all_windows:
                    if self.title_keyword.lower() in window.title.lower():
                        self.target_window = window
                        self.window_status = "found"
                        return self.target_window
                        
                self.window_status = "not_found"
                self.target_window = None
                return None
        except Exception as e:
            print(f"尋找視窗時發生錯誤: {e}")
            self.window_status = "not_found"
            self.target_window = None
            return None
    
    def focus_window(self):
        """聚焦目標視窗"""
        if not self.target_window:
            window = self.find_target_window()
            if not window:
                return False
                
        try:
            # 嘗試聚焦視窗
            if hasattr(self.target_window, 'activate'):
                self.target_window.activate()
            elif hasattr(self.target_window, 'restore'):
                self.target_window.restore()
                
            # 確保視窗在前景
            if hasattr(self.target_window, 'minimize') and self.target_window.isMinimized:
                self.target_window.restore()
                
            return True
        except Exception as e:
            print(f"聚焦視窗時發生錯誤: {e}")
            return False
    
    def get_window_status(self):
        """獲取視窗狀態"""
        return self.window_status
    
    def refresh_window_status(self):
        """刷新視窗狀態"""
        self.find_target_window()
        return self.window_status

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
        
        # 動態拖曳標籤頁
        dynamic_drag_tab = QWidget()
        dynamic_drag_layout = QFormLayout(dynamic_drag_tab)
        
        # 拖曳最短時間
        self.drag_min_time_spin = QDoubleSpinBox()
        self.drag_min_time_spin.setRange(0.1, 2.0)
        self.drag_min_time_spin.setSingleStep(0.1)
        self.drag_min_time_spin.setValue(self.cfg["DRAG_HOLD_MIN"])
        dynamic_drag_layout.addRow("拖曳最短時間(秒):", self.drag_min_time_spin)
        
        # 拖曳最長時間
        self.drag_max_time_spin = QDoubleSpinBox()
        self.drag_max_time_spin.setRange(1.0, 10.0)
        self.drag_max_time_spin.setSingleStep(0.5)
        self.drag_max_time_spin.setValue(self.cfg["DRAG_HOLD_MAX"])
        dynamic_drag_layout.addRow("拖曳最長時間(秒):", self.drag_max_time_spin)
        
        # 動態拖曳檢查間隔
        self.drag_feedback_interval_spin = QDoubleSpinBox()
        self.drag_feedback_interval_spin.setRange(0.05, 0.5)
        self.drag_feedback_interval_spin.setSingleStep(0.05)
        self.drag_feedback_interval_spin.setValue(self.cfg["DRAG_FEEDBACK_INTERVAL"])
        dynamic_drag_layout.addRow("動態檢查間隔(秒):", self.drag_feedback_interval_spin)
        
        # 角度變化容忍度
        self.drag_angle_tolerance_spin = QDoubleSpinBox()
        self.drag_angle_tolerance_spin.setRange(5.0, 60.0)
        self.drag_angle_tolerance_spin.setSingleStep(5.0)
        self.drag_angle_tolerance_spin.setValue(self.cfg["DRAG_ANGLE_TOLERANCE"])
        dynamic_drag_layout.addRow("角度變化容忍度(度):", self.drag_angle_tolerance_spin)
        
        # 最短動態拖曳時間
        self.drag_min_dynamic_time_spin = QDoubleSpinBox()
        self.drag_min_dynamic_time_spin.setRange(0.1, 1.0)
        self.drag_min_dynamic_time_spin.setSingleStep(0.1)
        self.drag_min_dynamic_time_spin.setValue(self.cfg["DRAG_MIN_TIME"])
        dynamic_drag_layout.addRow("最短動態拖曳(秒):", self.drag_min_dynamic_time_spin)
        
        # 角度穩定標準差門檻
        self.angle_ok_std_spin = QDoubleSpinBox()
        self.angle_ok_std_spin.setRange(5.0, 30.0)
        self.angle_ok_std_spin.setSingleStep(1.0)
        self.angle_ok_std_spin.setValue(self.cfg["ANGLE_OK_STD"])
        dynamic_drag_layout.addRow("角度穩定標準差(度):", self.angle_ok_std_spin)
        
        # 角度重新鎖定門檻
        self.angle_relock_std_spin = QDoubleSpinBox()
        self.angle_relock_std_spin.setRange(15.0, 50.0)
        self.angle_relock_std_spin.setSingleStep(5.0)
        self.angle_relock_std_spin.setValue(self.cfg["ANGLE_RELOCK_STD"])
        dynamic_drag_layout.addRow("角度重鎖定門檻(度):", self.angle_relock_std_spin)
        
        # 呼吸式箭頭處理
        dynamic_drag_layout.addRow("", QLabel())  # 分隔線
        breathing_label = QLabel("呼吸式箭頭處理:")
        breathing_label.setStyleSheet("font-weight: bold; color: #0066cc;")
        dynamic_drag_layout.addRow(breathing_label)
        
        # 箭頭呼吸週期
        self.arrow_breathing_cycle_spin = QDoubleSpinBox()
        self.arrow_breathing_cycle_spin.setRange(0.5, 3.0)
        self.arrow_breathing_cycle_spin.setSingleStep(0.1)
        self.arrow_breathing_cycle_spin.setValue(self.cfg["ARROW_BREATHING_CYCLE"])
        dynamic_drag_layout.addRow("箭頭呼吸週期(秒):", self.arrow_breathing_cycle_spin)
        
        # 容忍消失時間
        self.arrow_miss_tolerance_time_spin = QDoubleSpinBox()
        self.arrow_miss_tolerance_time_spin.setRange(0.1, 2.0)
        self.arrow_miss_tolerance_time_spin.setSingleStep(0.1)
        self.arrow_miss_tolerance_time_spin.setValue(self.cfg["ARROW_MISS_TOLERANCE_TIME"])
        dynamic_drag_layout.addRow("容忍消失時間(秒):", self.arrow_miss_tolerance_time_spin)
        
        # 方向改變確認次數
        self.direction_change_threshold_spin = QSpinBox()
        self.direction_change_threshold_spin.setRange(1, 10)
        self.direction_change_threshold_spin.setValue(self.cfg["DIRECTION_CHANGE_THRESHOLD"])
        dynamic_drag_layout.addRow("方向改變確認次數:", self.direction_change_threshold_spin)
        
        tabs.addTab(dynamic_drag_tab, "動態拖曳")
        
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
        
        # 高級設定標籤頁
        advanced_tab = QWidget()
        advanced_layout = QFormLayout(advanced_tab)
        
        # 視窗聚焦設定區塊
        focus_label = QLabel("視窗聚焦設定:")
        focus_label.setStyleSheet("font-weight: bold; color: #0066cc;")
        advanced_layout.addRow(focus_label)
        
        # 啟用視窗聚焦功能
        self.enable_window_focus_checkbox = QCheckBox("啟用視窗聚焦功能")
        self.enable_window_focus_checkbox.setChecked(self.cfg["ENABLE_WINDOW_FOCUS"])
        advanced_layout.addRow("", self.enable_window_focus_checkbox)
        
        # 偵測時聚焦視窗
        self.window_focus_on_detection_checkbox = QCheckBox("偵測到圖標時自動聚焦目標視窗")
        self.window_focus_on_detection_checkbox.setChecked(self.cfg["WINDOW_FOCUS_ON_DETECTION"])
        advanced_layout.addRow("", self.window_focus_on_detection_checkbox)
        
        # 分隔線
        advanced_layout.addRow("", QLabel())
        
        # 箭頭輪詢間隔
        self.arrow_poll_interval_spin = QDoubleSpinBox()
        self.arrow_poll_interval_spin.setRange(0.01, 0.5)
        self.arrow_poll_interval_spin.setSingleStep(0.01)
        self.arrow_poll_interval_spin.setDecimals(3)
        self.arrow_poll_interval_spin.setValue(self.cfg["ARROW_POLL_INTERVAL"])
        advanced_layout.addRow("箭頭輪詢間隔(秒):", self.arrow_poll_interval_spin)
        
        # 拖曳按鈕選擇
        self.drag_button_combo = QPushButton("left")
        def toggle_drag_button():
            current = self.drag_button_combo.text()
            new_button = "right" if current == "left" else "left"
            self.drag_button_combo.setText(new_button)
        self.drag_button_combo.clicked.connect(toggle_drag_button)
        self.drag_button_combo.setText(self.cfg["DRAG_BUTTON"])
        advanced_layout.addRow("拖曳按鈕:", self.drag_button_combo)
        
        # 拖曳會話最長時間
        self.drag_session_max_spin = QDoubleSpinBox()
        self.drag_session_max_spin.setRange(1.0, 30.0)
        self.drag_session_max_spin.setSingleStep(1.0)
        self.drag_session_max_spin.setValue(self.cfg["DRAG_SESSION_MAX"])
        advanced_layout.addRow("拖曳會話最長時間(秒):", self.drag_session_max_spin)
        
        # 角度中止門檻
        self.angle_abort_deg_spin = QDoubleSpinBox()
        self.angle_abort_deg_spin.setRange(10.0, 120.0)
        self.angle_abort_deg_spin.setSingleStep(5.0)
        self.angle_abort_deg_spin.setValue(self.cfg["ANGLE_ABORT_DEG"])
        advanced_layout.addRow("角度中止門檻(度):", self.angle_abort_deg_spin)
        
        # 角度平滑係數
        self.angle_smooth_alpha_spin = QDoubleSpinBox()
        self.angle_smooth_alpha_spin.setRange(0.1, 1.0)
        self.angle_smooth_alpha_spin.setSingleStep(0.05)
        self.angle_smooth_alpha_spin.setValue(self.cfg["ANGLE_SMOOTH_ALPHA"])
        advanced_layout.addRow("角度平滑係數:", self.angle_smooth_alpha_spin)
        
        # 箭頭消失容忍次數
        self.arrow_miss_tolerance_spin = QSpinBox()
        self.arrow_miss_tolerance_spin.setRange(1, 20)
        self.arrow_miss_tolerance_spin.setValue(self.cfg["ARROW_MISS_TOLERANCE"])
        advanced_layout.addRow("箭頭消失容忍次數:", self.arrow_miss_tolerance_spin)
        
        # 分隔線
        advanced_layout.addRow("", QLabel())
        delay_label = QLabel("時間延遲設定:")
        delay_label.setStyleSheet("font-weight: bold; color: #0066cc;")
        advanced_layout.addRow(delay_label)
        
        # 預防性點擊延遲
        self.preventive_click_delay_spin = QDoubleSpinBox()
        self.preventive_click_delay_spin.setRange(0.05, 1.0)
        self.preventive_click_delay_spin.setSingleStep(0.05)
        self.preventive_click_delay_spin.setValue(self.cfg["PREVENTIVE_CLICK_DELAY"])
        advanced_layout.addRow("預防性點擊延遲(秒):", self.preventive_click_delay_spin)
        
        # 移動後延遲
        self.post_move_delay_spin = QDoubleSpinBox()
        self.post_move_delay_spin.setRange(0.05, 1.0)
        self.post_move_delay_spin.setSingleStep(0.05)
        self.post_move_delay_spin.setValue(self.cfg["POST_MOVE_DELAY"])
        advanced_layout.addRow("移動後延遲(秒):", self.post_move_delay_spin)
        
        # 最終檢查延遲
        self.final_check_delay_spin = QDoubleSpinBox()
        self.final_check_delay_spin.setRange(0.05, 1.0)
        self.final_check_delay_spin.setSingleStep(0.05)
        self.final_check_delay_spin.setValue(self.cfg["FINAL_CHECK_DELAY"])
        advanced_layout.addRow("最終檢查延遲(秒):", self.final_check_delay_spin)
        
        # 分隔線
        advanced_layout.addRow("", QLabel())
        log_label = QLabel("日誌管理設定:")
        log_label.setStyleSheet("font-weight: bold; color: #0066cc;")
        advanced_layout.addRow(log_label)
        
        # 啟用自動日誌清理
        self.log_auto_cleanup_checkbox = QCheckBox("啟用自動日誌清理")
        self.log_auto_cleanup_checkbox.setChecked(self.cfg.get("LOG_AUTO_CLEANUP", True))
        advanced_layout.addRow("", self.log_auto_cleanup_checkbox)
        
        # 最大日誌行數
        self.log_max_lines_spin = QSpinBox()
        self.log_max_lines_spin.setRange(100, 2000)
        self.log_max_lines_spin.setValue(self.cfg.get("LOG_MAX_LINES", 500))
        advanced_layout.addRow("最大日誌行數:", self.log_max_lines_spin)
        
        # 清理後保留行數
        self.log_cleanup_lines_spin = QSpinBox()
        self.log_cleanup_lines_spin.setRange(50, 500)
        self.log_cleanup_lines_spin.setValue(self.cfg.get("LOG_CLEANUP_LINES", 100))
        advanced_layout.addRow("清理後保留行數:", self.log_cleanup_lines_spin)
        
        tabs.addTab(advanced_tab, "高級設定")
        
        # 圓環檢測標籤頁（增強版人物檢測）
        ring_tab = QWidget()
        ring_layout = QFormLayout(ring_tab)
        
        # 啟用圓環檢測
        self.ring_detection_enabled_checkbox = QCheckBox("啟用圓環檢測（增強版人物檢測）")
        self.ring_detection_enabled_checkbox.setChecked(self.cfg.get("RING_DETECTION_ENABLED", True))
        ring_layout.addRow("", self.ring_detection_enabled_checkbox)
        
        # 圓環半徑範圍
        self.ring_r_min_spin = QSpinBox()
        self.ring_r_min_spin.setRange(5, 50)
        self.ring_r_min_spin.setValue(self.cfg.get("RING_CIRCLE_R_MIN", 18))
        ring_layout.addRow("圓環最小半徑(像素):", self.ring_r_min_spin)
        
        self.ring_r_max_spin = QSpinBox()
        self.ring_r_max_spin.setRange(20, 100)
        self.ring_r_max_spin.setValue(self.cfg.get("RING_CIRCLE_R_MAX", 40))
        ring_layout.addRow("圓環最大半徑(像素):", self.ring_r_max_spin)
        
        # 白色檢測參數
        ring_layout.addRow("", QLabel())
        white_label = QLabel("白色檢測參數:")
        white_label.setStyleSheet("font-weight: bold; color: #0066cc;")
        ring_layout.addRow(white_label)
        
        # 白色亮度閾值
        self.ring_white_v_slider = QSlider(Qt.Horizontal)
        self.ring_white_v_slider.setRange(150, 255)
        self.ring_white_v_slider.setValue(self.cfg.get("RING_WHITE_V_THRESH", 200))
        self.ring_white_v_label = QLabel()
        self.ring_white_v_slider.valueChanged.connect(self._update_ring_white_v_label)
        
        white_v_layout = QHBoxLayout()
        white_v_layout.addWidget(self.ring_white_v_slider)
        white_v_layout.addWidget(self.ring_white_v_label)
        ring_layout.addRow("白色亮度閾值:", white_v_layout)
        
        # 白色飽和度最大值
        self.ring_white_s_slider = QSlider(Qt.Horizontal)
        self.ring_white_s_slider.setRange(30, 120)
        self.ring_white_s_slider.setValue(self.cfg.get("RING_WHITE_S_MAX", 60))
        self.ring_white_s_label = QLabel()
        self.ring_white_s_slider.valueChanged.connect(self._update_ring_white_s_label)
        
        white_s_layout = QHBoxLayout()
        white_s_layout.addWidget(self.ring_white_s_slider)
        white_s_layout.addWidget(self.ring_white_s_label)
        ring_layout.addRow("白色飽和度上限:", white_s_layout)
        
        # 圓環一致性閾值
        self.ring_consistency_slider = QSlider(Qt.Horizontal)
        self.ring_consistency_slider.setRange(30, 90)
        self.ring_consistency_slider.setValue(int(self.cfg.get("RING_CONSISTENCY", 0.55) * 100))
        self.ring_consistency_label = QLabel()
        self.ring_consistency_slider.valueChanged.connect(self._update_ring_consistency_label)
        
        consistency_layout = QHBoxLayout()
        consistency_layout.addWidget(self.ring_consistency_slider)
        consistency_layout.addWidget(self.ring_consistency_label)
        ring_layout.addRow("圓周白色比例閾值:", consistency_layout)
        
        # 模板驗證參數
        ring_layout.addRow("", QLabel())
        template_label = QLabel("模板二次驗證:")
        template_label.setStyleSheet("font-weight: bold; color: #0066cc;")
        ring_layout.addRow(template_label)
        
        # 驗證窗口大小
        self.ring_refine_window_spin = QSpinBox()
        self.ring_refine_window_spin.setRange(60, 200)
        self.ring_refine_window_spin.setValue(self.cfg.get("RING_REFINE_WINDOW", 120))
        ring_layout.addRow("驗證窗口大小(像素):", self.ring_refine_window_spin)
        
        # 模板驗證信心度
        self.ring_template_conf_slider = QSlider(Qt.Horizontal)
        self.ring_template_conf_slider.setRange(60, 95)
        self.ring_template_conf_slider.setValue(int(self.cfg.get("RING_TEMPLATE_CONFIDENCE", 0.82) * 100))
        self.ring_template_conf_label = QLabel()
        self.ring_template_conf_slider.valueChanged.connect(self._update_ring_template_conf_label)
        
        template_conf_layout = QHBoxLayout()
        template_conf_layout.addWidget(self.ring_template_conf_slider)
        template_conf_layout.addWidget(self.ring_template_conf_label)
        ring_layout.addRow("模板驗證信心度:", template_conf_layout)
        
        # 添加說明
        ring_layout.addRow("", QLabel())
        ring_help_label = QLabel("💡 圓環檢測：先找人物腳下的白色圓環，再用模板驗證，提高檢測速度和精度")
        ring_help_label.setStyleSheet("color: #666; font-size: 10px;")
        ring_help_label.setWordWrap(True)
        ring_layout.addRow("", ring_help_label)
        
        tabs.addTab(ring_tab, "圓環檢測")
        
        # 圖標增強檢測標籤頁
        icon_enhanced_tab = QWidget()
        icon_enhanced_layout = QFormLayout(icon_enhanced_tab)
        
        # 啟用圖標增強檢測
        self.icon_enhanced_enabled_checkbox = QCheckBox("啟用圖標增強檢測（智能遮罩+多重比對）")
        self.icon_enhanced_enabled_checkbox.setChecked(self.cfg.get("ICON_ENHANCED_DETECTION", True))
        icon_enhanced_layout.addRow("", self.icon_enhanced_enabled_checkbox)
        
        # 融合權重參數
        icon_enhanced_layout.addRow("", QLabel())
        fusion_label = QLabel("融合權重參數:")
        fusion_label.setStyleSheet("font-weight: bold; color: #0066cc;")
        icon_enhanced_layout.addRow(fusion_label)
        
        # 遮罩與邊緣融合權重
        self.icon_mask_alpha_slider = QSlider(Qt.Horizontal)
        self.icon_mask_alpha_slider.setRange(0, 100)
        self.icon_mask_alpha_slider.setValue(int(self.cfg.get("ICON_MASK_ALPHA", 0.5) * 100))
        self.icon_mask_alpha_label = QLabel()
        self.icon_mask_alpha_slider.valueChanged.connect(self._update_icon_mask_alpha_label)
        
        mask_alpha_layout = QHBoxLayout()
        mask_alpha_layout.addWidget(self.icon_mask_alpha_slider)
        mask_alpha_layout.addWidget(self.icon_mask_alpha_label)
        icon_enhanced_layout.addRow("遮罩權重（vs邊緣）:", mask_alpha_layout)
        
        # 置信度參數
        icon_enhanced_layout.addRow("", QLabel())
        confidence_label = QLabel("置信度參數:")
        confidence_label.setStyleSheet("font-weight: bold; color: #0066cc;")
        icon_enhanced_layout.addRow(confidence_label)
        
        # 增強檢測信心度
        self.icon_enhanced_conf_slider = QSlider(Qt.Horizontal)
        self.icon_enhanced_conf_slider.setRange(70, 95)
        self.icon_enhanced_conf_slider.setValue(int(self.cfg.get("ICON_ENHANCED_CONFIDENCE", 0.84) * 100))
        self.icon_enhanced_conf_label = QLabel()
        self.icon_enhanced_conf_slider.valueChanged.connect(self._update_icon_enhanced_conf_label)
        
        enhanced_conf_layout = QHBoxLayout()
        enhanced_conf_layout.addWidget(self.icon_enhanced_conf_slider)
        enhanced_conf_layout.addWidget(self.icon_enhanced_conf_label)
        icon_enhanced_layout.addRow("增強檢測信心度:", enhanced_conf_layout)
        
        # 比例門檻
        self.icon_ratio_threshold_slider = QSlider(Qt.Horizontal)
        self.icon_ratio_threshold_slider.setRange(105, 150)
        self.icon_ratio_threshold_slider.setValue(int(self.cfg.get("ICON_RATIO_THRESHOLD", 1.12) * 100))
        self.icon_ratio_threshold_label = QLabel()
        self.icon_ratio_threshold_slider.valueChanged.connect(self._update_icon_ratio_threshold_label)
        
        ratio_threshold_layout = QHBoxLayout()
        ratio_threshold_layout.addWidget(self.icon_ratio_threshold_slider)
        ratio_threshold_layout.addWidget(self.icon_ratio_threshold_label)
        icon_enhanced_layout.addRow("最佳/次佳比例門檻:", ratio_threshold_layout)
        
        # 添加說明
        icon_enhanced_layout.addRow("", QLabel())
        icon_enhanced_help_label = QLabel("💡 智能遮罩檢測：自動識別關鍵特徵（白色對話框、青藍光圈），排除干擾（紅色驚嘆號）")
        icon_enhanced_help_label.setStyleSheet("color: #666; font-size: 10px;")
        icon_enhanced_help_label.setWordWrap(True)
        icon_enhanced_layout.addRow("", icon_enhanced_help_label)
        
        tabs.addTab(icon_enhanced_tab, "圖標增強檢測")
        
        # Discord 通知標籤頁
        discord_tab = QWidget()
        discord_layout = QFormLayout(discord_tab)
        
        # 啟用 Discord 通知
        self.enable_discord_checkbox = QCheckBox("啟用 Discord Webhook 通知")
        self.enable_discord_checkbox.setChecked(self.cfg.get("ENABLE_DISCORD_WEBHOOK", False))
        discord_layout.addRow("", self.enable_discord_checkbox)
        
        # 通知超時時間
        self.discord_timeout_spin = QSpinBox()
        self.discord_timeout_spin.setRange(60, 3600)  # 1分鐘到1小時
        self.discord_timeout_spin.setSuffix(" 秒")
        self.discord_timeout_spin.setValue(self.cfg.get("DISCORD_NOTIFICATION_TIMEOUT", 300))
        discord_layout.addRow("通知超時時間:", self.discord_timeout_spin)
        
        # 選擇頻道
        self.discord_channel_combo = QComboBox()
        self.discord_channel_combo.addItems(["嘎嘎", "斯拉", "毛", "樹", "棋"])
        selected_channel = self.cfg.get("DISCORD_SELECTED_CHANNEL", "嘎嘎")
        if selected_channel in ["嘎嘎", "斯拉", "毛", "樹", "棋"]:
            self.discord_channel_combo.setCurrentText(selected_channel)
        discord_layout.addRow("選擇頻道:", self.discord_channel_combo)
        
        # 頻道設定區塊
        discord_layout.addRow("", QLabel())
        channels_label = QLabel("頻道 Webhook URL 設定:")
        channels_label.setStyleSheet("font-weight: bold; color: #0066cc;")
        discord_layout.addRow(channels_label)
        
        # 各頻道的 Webhook URL 設定
        self.discord_channel_urls = {}
        channels = self.cfg.get("DISCORD_CHANNELS", {})
        
        for channel_name in ["嘎嘎", "斯拉", "毛", "樹", "棋"]:
            url_layout = QHBoxLayout()
            
            url_input = QLineEdit()
            url_input.setPlaceholderText(f"輸入 {channel_name} 頻道的 Webhook URL")
            url_input.setText(channels.get(channel_name, ""))
            self.discord_channel_urls[channel_name] = url_input
            
            test_btn = QPushButton("測試")
            test_btn.setMaximumWidth(60)
            test_btn.clicked.connect(lambda checked, name=channel_name: self._test_discord_webhook(name))
            
            url_layout.addWidget(url_input)
            url_layout.addWidget(test_btn)
            
            discord_layout.addRow(f"{channel_name}:", url_layout)
        
        # 添加說明
        discord_layout.addRow("", QLabel())
        help_label = QLabel("💡 提示：在 Discord 頻道設定中創建 Webhook，複製 URL 貼上即可")
        help_label.setStyleSheet("color: #666; font-size: 10px;")
        help_label.setWordWrap(True)
        discord_layout.addRow("", help_label)
        
        tabs.addTab(discord_tab, "Discord 通知")
        
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
        # 圓環檢測標籤初始化
        self._update_ring_white_v_label()
        self._update_ring_white_s_label()
        self._update_ring_consistency_label()
        self._update_ring_template_conf_label()
        # 圖標增強檢測標籤初始化
        self._update_icon_mask_alpha_label()
        self._update_icon_enhanced_conf_label()
        self._update_icon_ratio_threshold_label()
        
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
    
    def _update_ring_white_v_label(self):
        value = self.ring_white_v_slider.value()
        self.ring_white_v_label.setText(f"{value}")
    
    def _update_ring_white_s_label(self):
        value = self.ring_white_s_slider.value()
        self.ring_white_s_label.setText(f"{value}")
    
    def _update_ring_consistency_label(self):
        value = self.ring_consistency_slider.value()
        self.ring_consistency_label.setText(f"{value/100:.2f}")
    
    def _update_ring_template_conf_label(self):
        value = self.ring_template_conf_slider.value()
        self.ring_template_conf_label.setText(f"{value/100:.2f}")
    
    def _update_icon_mask_alpha_label(self):
        value = self.icon_mask_alpha_slider.value()
        self.icon_mask_alpha_label.setText(f"{value/100:.2f}")
    
    def _update_icon_enhanced_conf_label(self):
        value = self.icon_enhanced_conf_slider.value()
        self.icon_enhanced_conf_label.setText(f"{value/100:.2f}")
    
    def _update_icon_ratio_threshold_label(self):
        value = self.icon_ratio_threshold_slider.value()
        self.icon_ratio_threshold_label.setText(f"{value/100:.2f}")
        
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
        
        # 動態拖曳
        self.drag_min_time_spin.setValue(DEFAULT_CFG["DRAG_HOLD_MIN"])
        self.drag_max_time_spin.setValue(DEFAULT_CFG["DRAG_HOLD_MAX"])
        self.drag_feedback_interval_spin.setValue(DEFAULT_CFG["DRAG_FEEDBACK_INTERVAL"])
        self.drag_angle_tolerance_spin.setValue(DEFAULT_CFG["DRAG_ANGLE_TOLERANCE"])
        self.drag_min_dynamic_time_spin.setValue(DEFAULT_CFG["DRAG_MIN_TIME"])
        self.angle_ok_std_spin.setValue(DEFAULT_CFG["ANGLE_OK_STD"])
        self.angle_relock_std_spin.setValue(DEFAULT_CFG["ANGLE_RELOCK_STD"])
        
        # 呼吸式箭頭處理
        self.arrow_breathing_cycle_spin.setValue(DEFAULT_CFG["ARROW_BREATHING_CYCLE"])
        self.arrow_miss_tolerance_time_spin.setValue(DEFAULT_CFG["ARROW_MISS_TOLERANCE_TIME"])
        self.direction_change_threshold_spin.setValue(DEFAULT_CFG["DIRECTION_CHANGE_THRESHOLD"])
        
        # 高級設定
        self.arrow_poll_interval_spin.setValue(DEFAULT_CFG["ARROW_POLL_INTERVAL"])
        self.drag_button_combo.setText(DEFAULT_CFG["DRAG_BUTTON"])
        self.drag_session_max_spin.setValue(DEFAULT_CFG["DRAG_SESSION_MAX"])
        self.angle_abort_deg_spin.setValue(DEFAULT_CFG["ANGLE_ABORT_DEG"])
        self.angle_smooth_alpha_spin.setValue(DEFAULT_CFG["ANGLE_SMOOTH_ALPHA"])
        self.arrow_miss_tolerance_spin.setValue(DEFAULT_CFG["ARROW_MISS_TOLERANCE"])
        self.preventive_click_delay_spin.setValue(DEFAULT_CFG["PREVENTIVE_CLICK_DELAY"])
        self.post_move_delay_spin.setValue(DEFAULT_CFG["POST_MOVE_DELAY"])
        self.final_check_delay_spin.setValue(DEFAULT_CFG["FINAL_CHECK_DELAY"])
        
        # 日誌管理設定
        self.log_auto_cleanup_checkbox.setChecked(DEFAULT_CFG.get("LOG_AUTO_CLEANUP", True))
        self.log_max_lines_spin.setValue(DEFAULT_CFG.get("LOG_MAX_LINES", 500))
        self.log_cleanup_lines_spin.setValue(DEFAULT_CFG.get("LOG_CLEANUP_LINES", 100))
        
        # 視窗聚焦設定
        self.enable_window_focus_checkbox.setChecked(DEFAULT_CFG["ENABLE_WINDOW_FOCUS"])
        self.window_focus_on_detection_checkbox.setChecked(DEFAULT_CFG["WINDOW_FOCUS_ON_DETECTION"])
        
        # Discord 通知設定
        self.enable_discord_checkbox.setChecked(DEFAULT_CFG["ENABLE_DISCORD_WEBHOOK"])
        self.discord_timeout_spin.setValue(DEFAULT_CFG["DISCORD_NOTIFICATION_TIMEOUT"])
        self.discord_channel_combo.setCurrentText(DEFAULT_CFG["DISCORD_SELECTED_CHANNEL"])
        
        # Discord 頻道 URL
        default_channels = DEFAULT_CFG["DISCORD_CHANNELS"]
        for channel_name, url_input in self.discord_channel_urls.items():
            url_input.setText(default_channels.get(channel_name, ""))

    def _test_discord_webhook(self, channel_name):
        """測試 Discord Webhook"""
        try:
            url_input = self.discord_channel_urls[channel_name]
            webhook_url = url_input.text().strip()
            
            if not webhook_url:
                QMessageBox.warning(self, "測試失敗", f"請先設定 {channel_name} 頻道的 Webhook URL")
                return
            
            # 創建臨時的 Discord 通知器進行測試
            temp_cfg = {"DISCORD_CHANNELS": {channel_name: webhook_url}}
            notifier = DiscordNotifier(temp_cfg)
            
            success, message = notifier.send_test_notification(channel_name, webhook_url)
            
            if success:
                QMessageBox.information(self, "測試成功", f"{channel_name} 頻道: {message}")
            else:
                QMessageBox.warning(self, "測試失敗", f"{channel_name} 頻道: {message}")
                
        except Exception as e:
            QMessageBox.critical(self, "測試錯誤", f"測試 {channel_name} 頻道時發生錯誤: {e}")
        
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
        
        # 動態拖曳設置
        self.cfg["DRAG_HOLD_MIN"] = self.drag_min_time_spin.value()
        self.cfg["DRAG_HOLD_MAX"] = self.drag_max_time_spin.value()
        self.cfg["DRAG_FEEDBACK_INTERVAL"] = self.drag_feedback_interval_spin.value()
        self.cfg["DRAG_ANGLE_TOLERANCE"] = self.drag_angle_tolerance_spin.value()
        self.cfg["DRAG_MIN_TIME"] = self.drag_min_dynamic_time_spin.value()
        self.cfg["ANGLE_OK_STD"] = self.angle_ok_std_spin.value()
        self.cfg["ANGLE_RELOCK_STD"] = self.angle_relock_std_spin.value()
        
        # 呼吸式箭頭處理設置
        self.cfg["ARROW_BREATHING_CYCLE"] = self.arrow_breathing_cycle_spin.value()
        self.cfg["ARROW_MISS_TOLERANCE_TIME"] = self.arrow_miss_tolerance_time_spin.value()
        self.cfg["DIRECTION_CHANGE_THRESHOLD"] = self.direction_change_threshold_spin.value()
        
        # 高級設定
        self.cfg["ENABLE_WINDOW_FOCUS"] = self.enable_window_focus_checkbox.isChecked()
        self.cfg["WINDOW_FOCUS_ON_DETECTION"] = self.window_focus_on_detection_checkbox.isChecked()
        self.cfg["ARROW_POLL_INTERVAL"] = self.arrow_poll_interval_spin.value()
        self.cfg["DRAG_BUTTON"] = self.drag_button_combo.text()
        self.cfg["DRAG_SESSION_MAX"] = self.drag_session_max_spin.value()
        self.cfg["ANGLE_ABORT_DEG"] = self.angle_abort_deg_spin.value()
        self.cfg["ANGLE_SMOOTH_ALPHA"] = self.angle_smooth_alpha_spin.value()
        self.cfg["ARROW_MISS_TOLERANCE"] = self.arrow_miss_tolerance_spin.value()
        self.cfg["PREVENTIVE_CLICK_DELAY"] = self.preventive_click_delay_spin.value()
        self.cfg["POST_MOVE_DELAY"] = self.post_move_delay_spin.value()
        self.cfg["FINAL_CHECK_DELAY"] = self.final_check_delay_spin.value()
        
        # 日誌管理設定
        self.cfg["LOG_AUTO_CLEANUP"] = self.log_auto_cleanup_checkbox.isChecked()
        self.cfg["LOG_MAX_LINES"] = self.log_max_lines_spin.value()
        self.cfg["LOG_CLEANUP_LINES"] = self.log_cleanup_lines_spin.value()
        
        # Discord 通知設定
        self.cfg["ENABLE_DISCORD_WEBHOOK"] = self.enable_discord_checkbox.isChecked()
        self.cfg["DISCORD_NOTIFICATION_TIMEOUT"] = self.discord_timeout_spin.value()
        self.cfg["DISCORD_SELECTED_CHANNEL"] = self.discord_channel_combo.currentText()
        
        # 更新 Discord 頻道 URL
        discord_channels = {}
        for channel_name, url_input in self.discord_channel_urls.items():
            discord_channels[channel_name] = url_input.text().strip()
        self.cfg["DISCORD_CHANNELS"] = discord_channels
        
        # 圓環檢測設定
        self.cfg["RING_DETECTION_ENABLED"] = self.ring_detection_enabled_checkbox.isChecked()
        self.cfg["RING_CIRCLE_R_MIN"] = self.ring_r_min_spin.value()
        self.cfg["RING_CIRCLE_R_MAX"] = self.ring_r_max_spin.value()
        self.cfg["RING_WHITE_V_THRESH"] = self.ring_white_v_slider.value()
        self.cfg["RING_WHITE_S_MAX"] = self.ring_white_s_slider.value()
        self.cfg["RING_CONSISTENCY"] = self.ring_consistency_slider.value() / 100.0
        self.cfg["RING_REFINE_WINDOW"] = self.ring_refine_window_spin.value()
        self.cfg["RING_TEMPLATE_CONFIDENCE"] = self.ring_template_conf_slider.value() / 100.0
        
        # 圖標增強檢測設定
        self.cfg["ICON_ENHANCED_DETECTION"] = self.icon_enhanced_enabled_checkbox.isChecked()
        self.cfg["ICON_MASK_ALPHA"] = self.icon_mask_alpha_slider.value() / 100.0
        self.cfg["ICON_ENHANCED_CONFIDENCE"] = self.icon_enhanced_conf_slider.value() / 100.0
        self.cfg["ICON_RATIO_THRESHOLD"] = self.icon_ratio_threshold_slider.value() / 100.0
        
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

    def build_icon_masks(self, tmpl_bgr):
        """從模板自動產生 mask：保留白色對話框 + 青藍光圈；排除紅色驚嘆號"""
        tmpl_hsv = cv2.cvtColor(tmpl_bgr, cv2.COLOR_BGR2HSV)

        # 白色（對話框氣泡）
        white = cv2.inRange(tmpl_hsv, (0, 0, 200), (179, 40, 255))

        # 青藍（圖示底座與無線電波）
        cyan1 = cv2.inRange(tmpl_hsv, (85, 60, 120), (105, 255, 255))   # H 近似藍綠
        cyan2 = cv2.inRange(tmpl_hsv, (100, 40, 120), (125, 255, 255))  # 擴一點上界
        cyan = cv2.bitwise_or(cyan1, cyan2)

        # 排除紅色（右上驚嘆號）
        red1 = cv2.inRange(tmpl_hsv, (0, 80, 80), (10, 255, 255))
        red2 = cv2.inRange(tmpl_hsv, (170, 80, 80), (179, 255, 255))
        red = cv2.bitwise_or(red1, red2)

        keep = cv2.bitwise_or(white, cyan)
        keep = cv2.morphologyEx(keep, cv2.MORPH_CLOSE, np.ones((3,3), np.uint8), iterations=1)

        # 把紅色區域挖洞
        red = cv2.morphologyEx(red, cv2.MORPH_DILATE, np.ones((3,3), np.uint8), iterations=1)
        keep[red > 0] = 0

        return keep  # 單通道 8U，0=忽略，>0=納入比對

    def find_icon_enhanced(self, cfg=None, scale_range=None, scale_steps=None):
        """
        增強版圖標檢測：使用智能遮罩 + 多重比對融合
        回傳：(top_left_xy_global, best_scale, score) 或 (None, None, None)
        """
        if cfg is None:
            cfg = DEFAULT_CFG
            
        if scale_range is None:
            scale_range = self.scale_range
        if scale_steps is None:
            scale_steps = self.scale_steps
            
        # 從配置獲取參數
        alpha = cfg.get("ICON_MASK_ALPHA", 0.5)
        conf = cfg.get("ICON_ENHANCED_CONFIDENCE", 0.84)
        ratio_thresh = cfg.get("ICON_RATIO_THRESHOLD", 1.12)
            
        rx, ry, rw, rh = map(int, self.search_region)

        try:
            # 擷取搜尋區
            shot = pyautogui.screenshot(region=(rx, ry, rw, rh))
            img_rgb = np.array(shot)
            if img_rgb.size == 0:
                return None, None, None

            # 準備比對素材
            img_gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
            img_edge = cv2.Canny(img_gray, 50, 150)

            # 讀取彩色模板（用於遮罩生成）
            tmpl_bgr = cv2.imread(self.template_path, cv2.IMREAD_COLOR)
            if tmpl_bgr is None:
                # 回退到傳統方法
                return self.find_image_with_scaling_original()
                
            tmpl_gray = cv2.cvtColor(tmpl_bgr, cv2.COLOR_BGR2GRAY)
            tmpl_edge = cv2.Canny(tmpl_gray, 50, 150)
            mask0     = self.build_icon_masks(tmpl_bgr)

            th, tw = tmpl_gray.shape[:2]
            H, W   = img_gray.shape[:2]

            best_score = -1.0
            second_best = -1.0
            best_loc = None
            best_scale = None

            for s in np.linspace(scale_range[0], scale_range[1], scale_steps):
                w = max(1, int(round(tw * s)))
                h = max(1, int(round(th * s)))
                if h > H or w > W:
                    continue

                try:
                    t_gray = cv2.resize(tmpl_gray, (w, h), interpolation=cv2.INTER_AREA)
                    t_edge = cv2.resize(tmpl_edge, (w, h), interpolation=cv2.INTER_NEAREST)
                    t_mask = cv2.resize(mask0,     (w, h), interpolation=cv2.INTER_NEAREST)

                    # A) 灰階+遮罩
                    res1 = cv2.matchTemplate(img_gray, t_gray, cv2.TM_CCORR_NORMED, mask=t_mask)
                    _, s1, _, loc1 = cv2.minMaxLoc(res1)

                    # B) 邊緣
                    res2 = cv2.matchTemplate(img_edge, t_edge, cv2.TM_CCOEFF_NORMED)
                    _, s2, _, loc2 = cv2.minMaxLoc(res2)

                    # 融合
                    score = alpha * s1 + (1.0 - alpha) * s2
                    loc   = loc1 if s1 >= s2 else loc2

                    if score > best_score:
                        second_best = best_score
                        best_score  = score
                        best_loc    = (loc[0] + rx, loc[1] + ry)
                        best_scale  = s
                    elif score > second_best:
                        second_best = score
                        
                except cv2.error as e:
                    print(f"[警告] 圖標增強檢測比對失敗 (scale={s:.2f}): {e}")
                    continue

            if best_loc is None:
                return None, None, None

            # 置信度驗證
            ratio_ok = (best_score / max(1e-6, second_best)) >= ratio_thresh
            if best_score >= conf and ratio_ok:
                print(f"[增強圖標檢測] 成功：分數={best_score:.3f}, 比例={best_score/max(1e-6, second_best):.2f}")
                return best_loc, best_scale, best_score
                
            print(f"[增強圖標檢測] 未通過驗證：分數={best_score:.3f}, 比例={best_score/max(1e-6, second_best):.2f}")
            return None, None, None
            
        except Exception as e:
            print(f"[錯誤] 增強圖標檢測異常: {e}")
            return None, None, None

    def find_image_with_scaling_original(self):
        """改進的原始模板匹配方法，增加異常處理"""
        scale_steps = self.scale_steps
        scale_range = self.scale_range
        
        try:
            screenshot = pyautogui.screenshot(region=self.search_region)
            if screenshot is None:
                print("[警告] 截圖返回空值")
                return None, None
                
            screenshot_np = np.array(screenshot)
            if screenshot_np.size == 0:
                print("[警告] 截圖圖像為空")
                return None, None
                
            screenshot_gray = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2GRAY)
        except Exception as e:
            print(f"[警告] 圖標偵測截圖處理失敗: {e}")
            return None, None

        found_location = None
        max_corr = -1
        best_scale = None

        try:
            for scale in np.linspace(scale_range[0], scale_range[1], scale_steps):
                w, h = self.template_img.shape[::-1]
                try:
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
                except Exception as e:
                    print(f"[警告] 尺度 {scale:.2f} 處理失敗: {e}")
                    continue
        except Exception as e:
            print(f"[錯誤] 圖標偵測尺度循環失敗: {e}")
            return None, None

        if max_corr >= self.confidence:
            return found_location, best_scale
        else:
            return None, None

    def find_image_with_scaling(self, cfg=None, use_enhanced=None, fallback_to_original=True):
        """
        主要的圖標檢測方法：優先使用增強版檢測，失敗時可回退到傳統方法
        """
        if cfg is None:
            cfg = DEFAULT_CFG
            
        if use_enhanced is None:
            use_enhanced = cfg.get("ICON_ENHANCED_DETECTION", True)
            
        if use_enhanced:
            try:
                result = self.find_icon_enhanced(cfg)
                if result[0] is not None:
                    return result[0], result[1]  # 返回 (location, scale) 格式
                else:
                    print("[增強圖標檢測] 未找到結果")
            except Exception as e:
                print(f"[增強圖標檢測] 異常: {e}")
        
        # 增強檢測失敗，回退到傳統方法
        if fallback_to_original:
            print("[增強圖標檢測] 回退到傳統模板匹配")
            return self.find_image_with_scaling_original()
        
        return None, None

    def get_center_position(self, location, scale):
        if location and scale:
            center_x = location[0] + (self.template_width * scale) / 2
            center_y = location[1] + (self.template_height * scale) / 2
            return center_x, center_y
        return None, None

    def click_center(self, location, scale, cfg=None):
        """點擊目標中心位置，支持可配置的隨機偏移和多次點擊，增加異常處理"""
        try:
            cx, cy = self.get_center_position(location, scale)
            if not (cx and cy):
                print("[警告] 無法獲取中心位置")
                return False
                
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
                try:
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
                        
                except Exception as e:
                    print(f"[警告] 點擊操作 {i+1}/{click_count} 失敗: {e}")
                    continue
            
            return True
            
        except Exception as e:
            print(f"[錯誤] 點擊中心位置失敗: {e}")
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

    def find_ring_then_match(self, search_region=None, 
                           circle_r_min=18, circle_r_max=40,  # 依解析度調整
                           dp=1.2, minDist=25, param1=120, param2=18,
                           white_v_thresh=200, white_s_max=60,
                           ring_consistency=0.55,               # 圓周取樣有多少比例是「白」
                           refine_window=120,                    # 小窗大小（正方形）
                           confidence=0.82):
        """
        先用 HoughCircles 找白色圓環中心；可選擇在中心附近做模板比對做二次驗證。
        回傳：(center_xy, radius, score)；找不到回傳 (None, None, None)
        """
        if search_region is None:
            search_region = self.search_region
            
        rx, ry, rw, rh = map(int, search_region)

        try:
            shot = pyautogui.screenshot(region=(rx, ry, rw, rh))
        except Exception as e:
            print(f"[ring] 截圖失敗: {e}")
            return None, None, None

        img = np.array(shot)
        if img.size == 0:
            return None, None, None

        # ---- 預處理：強化白圈並壓背景 ----
        hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
        H, S, V = cv2.split(hsv)

        # 以「亮且不太飽和」挑白
        white = cv2.inRange(hsv, (0, 0, white_v_thresh), (179, white_s_max, 255))

        # 平滑 + 邊緣
        blur = cv2.GaussianBlur(white, (5,5), 0)
        edges = cv2.Canny(blur, 50, 150)

        # ---- Hough 圓偵測 ----
        circles = cv2.HoughCircles(edges, cv2.HOUGH_GRADIENT, dp=dp, minDist=minDist,
                                   param1=param1, param2=param2,
                                   minRadius=circle_r_min, maxRadius=circle_r_max)

        if circles is None:
            return None, None, None

        circles = np.round(circles[0, :]).astype(int)

        # ---- 針對每個候選做「白圈一致性」檢查，挑最佳 ----
        best = (None, None, -1.0)  # (center_xy_global, r, score)

        h, w = white.shape[:2]
        for (cx, cy, r) in circles:
            if not (0 <= cx < w and 0 <= cy < h):
                continue

            # 在圓周上取樣 N 個點，計算白色比例
            N = max(36, int(2 * math.pi * r / 8))  # 半徑越大取樣越多
            thetas = np.linspace(0, 2*np.pi, N, endpoint=False)
            xs = (cx + r * np.cos(thetas)).astype(int)
            ys = (cy + r * np.sin(thetas)).astype(int)
            xs = np.clip(xs, 0, w-1)
            ys = np.clip(ys, 0, h-1)

            ring_white_ratio = (white[ys, xs] > 0).mean()

            # 也檢查「中心附近不是白」（避免把亮點誤當實心圓）
            inner_r = max(2, int(r*0.45))
            mask_inner = np.zeros_like(white)
            cv2.circle(mask_inner, (cx, cy), inner_r, 255, -1)
            inner_white_ratio = (white[mask_inner > 0] > 0).mean()

            # 綜合分數：白圈比例高且中心白比例低
            score = ring_white_ratio - 0.4*inner_white_ratio

            if ring_white_ratio >= ring_consistency and score > best[2]:
                best = ((cx + rx, cy + ry), r, score)

        if best[0] is None:
            return None, None, None

        center_xy_global, r_best, score = best

        # ---- 可選：在白圈中心附近開小窗做模板二次驗證 ----
        if self.template_img is not None:
            cxg, cyg = center_xy_global
            half = refine_window // 2

            wx = max(rx, cxg - half)
            wy = max(ry, cyg - half)
            wx2 = min(rx + rw, cxg + half)
            wy2 = min(ry + rh, cyg + half)

            wW, wH = wx2 - wx, wy2 - wy
            if wW < 10 or wH < 10:
                # 小窗不合理就直接回傳白圈
                return center_xy_global, r_best, score

            # 取小窗並做模板比對
            try:
                win = np.array(pyautogui.screenshot(region=(wx, wy, wW, wH)))
                win_gray = cv2.cvtColor(win, cv2.COLOR_RGB2GRAY)

                tmpl = self.template_img.copy()
                if len(tmpl.shape) == 3:
                    tmpl = cv2.cvtColor(tmpl, cv2.COLOR_BGR2GRAY)

                # 尺度：模板若比小窗大就縮
                th, tw = tmpl.shape[:2]
                scale = min(wW / max(1, tw), wH / max(1, th), 1.0)
                if scale < 1.0:
                    tmpl = cv2.resize(tmpl, (int(tw*scale), int(th*scale)), interpolation=cv2.INTER_AREA)

                if tmpl.shape[0] <= win_gray.shape[0] and tmpl.shape[1] <= win_gray.shape[1]:
                    res = cv2.matchTemplate(win_gray, tmpl, cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, max_loc = cv2.minMaxLoc(res)

                    if max_val < confidence:
                        # 模板驗證沒過，仍可回傳「白圈中心」（通常已足夠做移動）
                        return center_xy_global, r_best, score
                    else:
                        # 模板驗證通過，回傳更高的分數
                        return center_xy_global, r_best, max_val
            except Exception as e:
                print(f"[警告] 模板二次驗證失敗: {e}")
                # 驗證失敗，回傳白圈結果
                return center_xy_global, r_best, score

        # 單純找白圈就夠用
        return center_xy_global, r_best, score

    def find_character_enhanced(self, cfg=None, use_ring_detection=True, fallback_to_template=True):
        """
        增強版人物檢測：優先使用圓環檢測，失敗時可回退到傳統模板匹配
        回傳：(location, scale) 或 (None, None)
        """
        if cfg is None:
            # 使用默認配置
            cfg = DEFAULT_CFG
            
        # 檢查是否啟用圓環檢測
        if use_ring_detection and cfg.get("RING_DETECTION_ENABLED", True):
            try:
                center_xy, radius, score = self.find_ring_then_match(
                    circle_r_min=cfg.get("RING_CIRCLE_R_MIN", 18),
                    circle_r_max=cfg.get("RING_CIRCLE_R_MAX", 40),
                    white_v_thresh=cfg.get("RING_WHITE_V_THRESH", 200),
                    white_s_max=cfg.get("RING_WHITE_S_MAX", 60),
                    ring_consistency=cfg.get("RING_CONSISTENCY", 0.55),
                    refine_window=cfg.get("RING_REFINE_WINDOW", 120),
                    confidence=cfg.get("RING_TEMPLATE_CONFIDENCE", 0.82)
                )
                if center_xy is not None:
                    # 將圓環中心轉換為兼容的 location, scale 格式
                    # 假設圓環中心就是角色的中心，計算對應的左上角位置
                    cx, cy = center_xy
                    # 使用平均尺度作為檢測到的尺度
                    estimated_scale = 1.0
                    
                    # 計算左上角位置（假設模板中心對應圓環中心）
                    half_w = (self.template_width * estimated_scale) / 2
                    half_h = (self.template_height * estimated_scale) / 2
                    location = (int(cx - half_w), int(cy - half_h))
                    
                    print(f"[增強檢測] 圓環檢測成功：中心({cx}, {cy})，分數={score:.3f}")
                    return location, estimated_scale
                else:
                    print("[增強檢測] 圓環檢測未找到結果")
            except Exception as e:
                print(f"[增強檢測] 圓環檢測異常: {e}")
        
        # 圓環檢測失敗，回退到傳統模板匹配
        if fallback_to_template:
            print("[增強檢測] 回退到傳統模板匹配")
            return self.find_character_original()
        
        return None, None

    def find_character_original(self):
        try:
            rx, ry, rw, rh = map(int, self.search_region)
            
            try:
                screenshot = pyautogui.screenshot(region=(rx, ry, rw, rh))
            except pyautogui.PyAutoGUIException as e:
                print(f"[警告] 人物偵測螢幕截圖失敗: {e}")
                return None, None
            except Exception as e:
                print(f"[警告] 人物偵測螢幕截圖異常: {e}")
                return None, None
                
            if screenshot is None:
                print("[警告] 人物偵測截圖返回空值")
                return None, None
                
            try:
                screenshot_np = np.array(screenshot)
                if screenshot_np.size == 0:
                    print("[警告] 人物偵測截圖圖像為空")
                    return None, None
                    
                screenshot_gray = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2GRAY)
            except Exception as e:
                print(f"[警告] 人物偵測圖像轉換失敗: {e}")
                return None, None

            found_location = None
            max_corr = -1.0
            best_scale = None
            th, tw = self.template_img.shape[:2]

            try:
                for scale in np.linspace(self.scale_range[0], self.scale_range[1], self.scale_steps):
                    w = max(1, int(round(tw * scale)))
                    h = max(1, int(round(th * scale)))
                    
                    try:
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
                    except Exception as e:
                        print(f"[警告] 人物模板匹配失敗 (scale={scale:.2f}): {e}")
                        continue
            except Exception as e:
                print(f"[警告] 人物偵測尺度循環失敗: {e}")
                return None, None

            if max_corr >= self.confidence and found_location is not None:
                return found_location, best_scale
            else:
                return None, None
                
        except Exception as e:
            print(f"[錯誤] 人物偵測整體異常: {e}")
            return None, None

    def find_character(self, cfg=None):
        """
        主要的人物檢測方法，使用增強版檢測（圓環+模板雙重驗證）
        """
        return self.find_character_enhanced(cfg)

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
        try:
            r = self.arrow_search_radius
            sx = int(round(search_center_x - r))
            sy = int(round(search_center_y - r))
            sw = sh = int(round(2*r))
            sx, sy, sw, sh = clamp_region_to_screen(sx, sy, sw, sh)

            try:
                pil_img = pyautogui.screenshot(region=(sx, sy, sw, sh))
            except pyautogui.PyAutoGUIException as e:
                print(f"[警告] 螢幕截圖失敗: {e}")
                return None, None, None
            except Exception as e:
                print(f"[警告] 螢幕截圖異常: {e}")
                return None, None, None

            if pil_img is None:
                print("[警告] 螢幕截圖返回空值")
                return None, None, None

            try:
                img = np.array(pil_img)[:, :, ::-1]  # to BGR
                if img.size == 0:
                    print("[警告] 截圖圖像為空")
                    return None, None, None
                    
                mask = self._preprocess_red_mask(img)
            except Exception as e:
                print(f"[警告] 圖像處理失敗: {e}")
                return None, None, None

            # 找候選
            try:
                cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            except Exception as e:
                print(f"[警告] 輪廓檢測失敗: {e}")
                return None, None, None

            best = (-1, None, None, False)  # (score, angle, top_left, tipflag)
            for c in cnts:
                try:
                    # 將局部座標換算為全域前，先用局部判斷
                    score, ang, tl, tip_ok = self._score_arrow_candidate(c, center_xy=(r, r))
                    if score > best[0]:
                        best = (score, ang, tl, tip_ok)
                except Exception as e:
                    print(f"[警告] 箭頭候選評分失敗: {e}")
                    continue

            if best[0] < 0 or best[1] is None:
                return None, None, None

            # 轉回全域 top-left
            try:
                tl_local = best[2]
                top_left_global = (int(tl_local[0] + sx), int(tl_local[1] + sy))
                return top_left_global, 1.0, float(best[1])
            except Exception as e:
                print(f"[警告] 座標轉換失敗: {e}")
                return None, None, None
                
        except Exception as e:
            print(f"[錯誤] 箭頭顏色偵測異常: {e}")
            return None, None, None

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

        try:
            while time.time() - t0 < self.timeout:
                try:
                    loc, _, ang = self.find_arrow_by_color(center_x, center_y)
                    if loc is not None and ang is not None:
                        angles.append(ang)
                        last_loc = loc

                        if len(angles) >= self.min_hits:
                            mean_deg, R, std_deg = self._circular_stats(angles)
                            # 集中度高（std 小）則提前返回
                            if std_deg is not None and std_deg <= early_stop_std_deg:
                                return last_loc, mean_deg, len(angles)
                except Exception as e:
                    print(f"[警告] 等待箭頭時偵測異常: {e}")
                    pass
                    
                time.sleep(self.poll)
        except Exception as e:
            print(f"[錯誤] 等待箭頭過程異常: {e}")

        if len(angles) >= self.min_hits:
            try:
                mean_deg, _, _ = self._circular_stats(angles)
                return last_loc, mean_deg, len(angles)
            except Exception as e:
                print(f"[錯誤] 箭頭角度統計異常: {e}")
                return None, None, 0
        return None, None, 0

    def drag_towards_arrow(self, center_x, center_y, angle_deg):
        try:
            sw, sh = pyautogui.size()
            rad = math.radians(angle_deg)
            dx = self.drag_distance * math.sin(rad)
            dy = -self.drag_distance * math.cos(rad)
            tx = max(0, min(sw - 1, center_x + dx))
            ty = max(0, min(sh - 1, center_y + dy))
            cx = int(round(center_x)); cy = int(round(center_y))
            tx = int(round(tx)); ty = int(round(ty))
            
            try:
                pyautogui.moveTo(cx, cy)
                pyautogui.mouseDown(button=self.drag_button)
                pyautogui.moveTo(tx, ty, duration=self.drag_seconds)
            except Exception as e:
                print(f"[警告] 箭頭拖曳操作失敗: {e}")
            finally:
                try:
                    pyautogui.mouseUp(button=self.drag_button)
                except Exception as e:
                    print(f"[警告] 箭頭拖曳滑鼠釋放失敗: {e}")
                    try:
                        pyautogui.mouseUp()
                    except Exception as e2:
                        print(f"[錯誤] 箭頭拖曳強制滑鼠釋放也失敗: {e2}")
        except Exception as e:
            print(f"[錯誤] 箭頭拖曳整體異常: {e}")
            # 確保滑鼠狀態正常
            try:
                pyautogui.mouseUp()
            except:
                pass     

    def _circular_stats(self, angles_deg):
        if not angles_deg:
            return None, 0.0, None
        ang = np.deg2rad(np.array(angles_deg, dtype=np.float64))
        C = np.cos(ang).sum(); S = np.sin(ang).sum()
        n = max(len(angles_deg), 1)
        R = np.sqrt(C*C + S*S) / n
        mean_deg = (math.degrees(math.atan2(S, C)) + 360) % 360
        R = max(min(R, 0.999999), 1e-6)
        std_deg = math.degrees(math.sqrt(-2.0 * math.log(R)))
        return mean_deg, R, std_deg

    def _sample_angle_window(self, cx, cy, window_time):
        t0 = time.time()
        angles = []; last_loc = None
        try:
            while time.time() - t0 < window_time:
                try:
                    loc, _, ang = self.find_arrow_by_color(cx, cy)
                    if loc is not None and ang is not None:
                        angles.append(ang); last_loc = loc
                except Exception as e:
                    # 箭頭偵測失敗，記錄錯誤但繼續嘗試
                    print(f"[警告] 箭頭偵測異常: {e}")
                    pass
                time.sleep(self.poll)
        except Exception as e:
            # 整個取樣窗口失敗
            print(f"[錯誤] 角度取樣窗口異常: {e}")
            return None, None, None, 0
            
        if not angles:
            return None, None, None, 0
        
        try:
            mean, _, std = self._circular_stats(angles)
            return last_loc, mean, std, len(angles)
        except Exception as e:
            print(f"[錯誤] 角度統計計算異常: {e}")
            return None, None, None, 0

    def _angle_diff(self, a, b):
        return abs((b - a + 180) % 360 - 180)

    def _dynamic_drag_with_feedback(self, cx, cy, initial_angle_deg, max_hold_seconds, cfg, log_fn=None):
        """
        動態拖曳：在拖曳過程中持續偵測箭頭方向並動態調整
        - 如果箭頭方向保持一致，繼續拖曳直到max_hold_seconds
        - 如果箭頭方向改變超過閾值，立即停止
        - 處理呼吸式箭頭：短暫消失不中斷，持續消失才停止
        """
        def log(msg):
            if log_fn:
                log_fn(msg)
        
        sw, sh = pyautogui.size()
        
        # 拖曳參數
        check_interval = float(cfg.get("DRAG_FEEDBACK_INTERVAL", 0.15))  # 每0.15秒檢查一次
        angle_tolerance = float(cfg.get("DRAG_ANGLE_TOLERANCE", 25.0))   # 角度變化容忍度
        min_drag_time = float(cfg.get("DRAG_MIN_TIME", 0.3))             # 最短拖曳時間
        
        # 呼吸式箭頭處理參數
        breathing_cycle = float(cfg.get("ARROW_BREATHING_CYCLE", 1.0))   # 呼吸週期（秒）
        miss_tolerance_time = float(cfg.get("ARROW_MISS_TOLERANCE_TIME", 0.5))  # 容忍消失時間
        direction_change_threshold = int(cfg.get("DIRECTION_CHANGE_THRESHOLD", 3))  # 方向改變確認次數
        
        # 計算初始目標位置
        rad = math.radians(initial_angle_deg)
        dx = self.drag_distance * math.sin(rad)
        dy = -self.drag_distance * math.cos(rad)
        tx = max(0, min(sw - 1, cx + dx))
        ty = max(0, min(sh - 1, cy + dy))
        
        cx = int(round(cx)); cy = int(round(cy))
        tx = int(round(tx)); ty = int(round(ty))
        
        log(f"[動態拖曳] 開始：角度{initial_angle_deg:.1f}°，最長{max_hold_seconds:.2f}s（處理呼吸式箭頭）")
        
        # 開始拖曳
        pyautogui.moveTo(cx, cy)
        pyautogui.mouseDown(button=self.drag_button)
        pyautogui.moveTo(tx, ty, duration=min(self.drag_seconds, 0.05))
        
        drag_start_time = time.time()
        last_check_time = drag_start_time
        total_corrections = 0
        
        # 呼吸式箭頭追蹤變數
        consecutive_misses = 0
        miss_start_time = None
        consecutive_direction_changes = 0
        last_valid_angle = initial_angle_deg
        angle_history = []  # 記錄最近的角度變化
        
        try:
            while True:
                current_time = time.time()
                elapsed = current_time - drag_start_time
                
                # 檢查是否達到最長時間
                if elapsed >= max_hold_seconds:
                    log(f"[動態拖曳] 達到最長時間{max_hold_seconds:.2f}s，結束")
                    break
                
                # 檢查是否到了檢查間隔
                if current_time - last_check_time >= check_interval and elapsed >= min_drag_time:
                    # 重新偵測箭頭方向
                    try:
                        updated_center_loc, updated_scale = self.find_character(cfg)
                        if updated_center_loc and updated_scale:
                            updated_cx = updated_center_loc[0] + (self.template_width * updated_scale) / 2
                            updated_cy = updated_center_loc[1] + (self.template_height * updated_scale) / 2
                        else:
                            updated_cx, updated_cy = cx, cy
                    except Exception as e:
                        print(f"[警告] 動態拖曳中人物偵測異常: {e}")
                        updated_cx, updated_cy = cx, cy
                    
                    # 快速檢測當前箭頭角度（短窗口）
                    try:
                        _, current_angle, current_std, hits = self._sample_angle_window(
                            updated_cx, updated_cy, window_time=max(self.poll*2, 0.1)
                        )
                    except Exception as e:
                        print(f"[警告] 動態拖曳中角度偵測異常: {e}")
                        # 偵測失敗，視為箭頭消失
                        current_angle, current_std, hits = None, None, 0
                    
                    if hits == 0:
                        # 箭頭未檢測到
                        consecutive_misses += 1
                        if miss_start_time is None:
                            miss_start_time = current_time
                        
                        miss_duration = current_time - miss_start_time
                        
                        # 檢查是否為呼吸式暫時消失
                        if miss_duration < miss_tolerance_time:
                            # 在容忍時間內，可能是呼吸式閃爍，繼續等待
                            if consecutive_misses == 1:  # 只在第一次記錄
                                log(f"[動態拖曳] 箭頭暫時消失，等待呼吸式恢復...")
                        else:
                            # 超過容忍時間，可能真的消失了
                            log(f"[動態拖曳] 箭頭持續消失{miss_duration:.2f}s，可能已到達目標，結束拖曳（已拖{elapsed:.2f}s）")
                            break
                    else:
                        # 檢測到箭頭，重置消失計數
                        if consecutive_misses > 0:
                            log(f"[動態拖曳] 箭頭恢復檢測，繼續拖曳")
                        consecutive_misses = 0
                        miss_start_time = None
                        
                        if current_angle is not None:
                            angle_diff = self._angle_diff(initial_angle_deg, current_angle)
                            
                            # 記錄角度歷史（最多保留最近5個）
                            angle_history.append(current_angle)
                            if len(angle_history) > 5:
                                angle_history.pop(0)
                            
                            # 檢查方向是否持續改變
                            significant_change = angle_diff > angle_tolerance
                            
                            if significant_change:
                                consecutive_direction_changes += 1
                                
                                # 需要多次確認才停止（避免呼吸式閃爍造成的誤判）
                                if consecutive_direction_changes >= direction_change_threshold:
                                    log(f"[動態拖曳] 方向持續改變{consecutive_direction_changes}次，"
                                        f"最終偏差{angle_diff:.1f}°>容忍{angle_tolerance}°，確認方向錯誤，停止拖曳（已拖{elapsed:.2f}s）")
                                    break
                                else:
                                    log(f"[動態拖曳] 檢測到方向改變{angle_diff:.1f}°（第{consecutive_direction_changes}/{direction_change_threshold}次），繼續確認...")
                            else:
                                # 方向正常，重置計數
                                consecutive_direction_changes = 0
                                
                                # 如果角度變化不大但有微調空間，可以調整目標位置
                                if 8.0 < angle_diff <= 15.0 and total_corrections < 2:  # 允許小幅修正
                                    # 重新計算目標位置
                                    new_rad = math.radians(current_angle)
                                    new_dx = self.drag_distance * math.sin(new_rad)
                                    new_dy = -self.drag_distance * math.cos(new_rad)
                                    new_tx = max(0, min(sw - 1, updated_cx + new_dx))
                                    new_ty = max(0, min(sh - 1, updated_cy + new_dy))
                                    
                                    # 平滑調整到新位置
                                    pyautogui.moveTo(int(new_tx), int(new_ty), duration=0.1)
                                    total_corrections += 1
                                    log(f"[動態拖曳] 微調方向：{initial_angle_deg:.1f}°→{current_angle:.1f}° (第{total_corrections}次)")
                                    initial_angle_deg = current_angle  # 更新基準角度
                            
                            last_valid_angle = current_angle
                    
                    last_check_time = current_time
                
                # 短暫休眠
                time.sleep(0.05)
                
        finally:
            try:
                pyautogui.mouseUp(button=self.drag_button)
            except Exception as e:
                print(f"[警告] 滑鼠釋放失敗: {e}")
                # 嘗試強制釋放滑鼠
                try:
                    pyautogui.mouseUp()
                except Exception as e2:
                    print(f"[錯誤] 強制滑鼠釋放也失敗: {e2}")
            
            try:
                final_elapsed = time.time() - drag_start_time
                log(f"[動態拖曳] 完成：實際拖曳{final_elapsed:.2f}s，微調{total_corrections}次，方向改變確認{consecutive_direction_changes}次")
            except Exception as e:
                print(f"[警告] 動態拖曳完成記錄失敗: {e}")

    def _hold_drag_seconds(self, cx, cy, angle_deg, hold_seconds):
        """
        固定速度場景：用「握住多久」決定走多遠
        流程：
          1) mouseDown 在人物中心
          2) 快速把游標丟到方向射線上固定距離（drag_distance）
          3) 停留 hold_seconds（保持 mouseDown）
          4) mouseUp
        """
        try:
            sw, sh = pyautogui.size()
            rad = math.radians(angle_deg)
            dx = self.drag_distance * math.sin(rad)
            dy = -self.drag_distance * math.cos(rad)
            tx = max(0, min(sw - 1, cx + dx))
            ty = max(0, min(sh - 1, cy + dy))
            cx = int(round(cx)); cy = int(round(cy))
            tx = int(round(tx)); ty = int(round(ty))

            try:
                pyautogui.moveTo(cx, cy)
                pyautogui.mouseDown(button=self.drag_button)
                # 游標快速定位到方向遠點，避免移動時間就是「握住時間」
                pyautogui.moveTo(tx, ty, duration=min(self.drag_seconds, 0.05))
                time.sleep(max(0.0, float(hold_seconds)))   # 真正的「握住秒數」
            except Exception as e:
                print(f"[警告] 固定拖曳操作失敗: {e}")
            finally:
                try:
                    pyautogui.mouseUp(button=self.drag_button)
                except Exception as e:
                    print(f"[警告] 固定拖曳滑鼠釋放失敗: {e}")
                    try:
                        pyautogui.mouseUp()
                    except Exception as e2:
                        print(f"[錯誤] 固定拖曳強制滑鼠釋放也失敗: {e2}")
        except Exception as e:
            print(f"[錯誤] 固定拖曳整體異常: {e}")
            # 確保滑鼠狀態正常
            try:
                pyautogui.mouseUp()
            except:
                pass

    def guide_towards_arrow(self, get_center_fn, cfg, log_fn=None):
        """
        閉迴路導航（以秒為主）：
        - 每回合先量測一個短窗角度（~0.25s），算出 std
        - 依 std 在 [DRAG_HOLD_MIN, DRAG_HOLD_MAX] 之間選擇握住秒數
          * std 越小 → hold 越長（更遠）
          * std 大於 ANGLE_RELOCK_STD → 不拖，先重鎖
        - 持續迴圈直到箭頭消失或達到 DRAG_SESSION_MAX
        """
        t0 = time.time()
        ema_angle = None
        miss = 0

        STD_LOW  = float(cfg.get("ANGLE_OK_STD", 12.0))
        STD_HIGH = float(cfg.get("ANGLE_RELOCK_STD", 25.0))
        HOLD_MIN = float(cfg.get("DRAG_HOLD_MIN", 0.15))
        HOLD_MAX = float(cfg.get("DRAG_HOLD_MAX", 1.20))
        SESSION_MAX = float(cfg.get("DRAG_SESSION_MAX", 6.0))

        def map_std_to_hold(std):
            if std is None:
                return HOLD_MIN * 0.7
            # 0..1：std 在 [LOW, HIGH] 的位置；越小越靠近 0
            t = (std - STD_LOW) / max(1e-6, (STD_HIGH - STD_LOW))
            t = min(1.0, max(0.0, t))
            # 低 std → 長握；高 std → 短握
            return HOLD_MIN + (1.0 - t) * (HOLD_MAX - HOLD_MIN)

        def log(msg):
            if log_fn:
                log_fn(msg)

        action_count = 0
        last_log_time = 0
        
        while time.time() - t0 < SESSION_MAX:
            # 重新找人物中心（避免被移動後偏差）
            try:
                center_loc, center_scale = self.find_character(cfg)
                if center_loc and center_scale:
                    cx = center_loc[0] + (self.template_width * center_scale) / 2
                    cy = center_loc[1] + (self.template_height * center_scale) / 2
                else:
                    cx, cy = get_center_fn()
            except Exception as e:
                print(f"[警告] 導航中人物偵測異常: {e}")
                try:
                    cx, cy = get_center_fn()
                except Exception as e2:
                    print(f"[錯誤] 無法獲取人物中心位置: {e2}")
                    log("[導航] 人物偵測失敗，結束導航")
                    return

            # 取短窗角度樣本
            try:
                _, mean, std, hits = self._sample_angle_window(cx, cy, window_time=max(self.poll*4, 0.25))
            except Exception as e:
                print(f"[警告] 導航中角度取樣異常: {e}")
                hits = 0
                mean = std = None
            if hits == 0:
                miss += 1
                # 只在第一次和每隔一段時間記錄，避免頻繁輸出
                current_time = time.time()
                if miss == 1 or (current_time - last_log_time) >= 2.0:
                    log(f"[導航] 找不到箭頭（{miss}/{cfg.get('ARROW_MISS_TOLERANCE',4)}）")
                    last_log_time = current_time
                    
                if miss >= int(cfg.get("ARROW_MISS_TOLERANCE", 4)):
                    log("[導航] 箭頭消失，結束導航")
                    return
                time.sleep(self.poll * 2)
                continue
            else:
                miss = 0

            # 角度發散就先不拖、再鎖定
            if std is not None and std > STD_HIGH:
                # 只在第一次記錄，避免重複輸出
                if action_count == 0:
                    log(f"[導航] 角度發散（std={std:.1f}°），暫停拖曳重新鎖定…")
                time.sleep(self.poll * 3)
                continue

            # 角度 EMA 平滑（環形處理）
            if ema_angle is None:
                ema_angle = mean
            else:
                alpha = float(cfg.get("ANGLE_SMOOTH_ALPHA", 0.35))
                delta = ((mean - ema_angle + 540) % 360) - 180
                ema_angle = (ema_angle + alpha * delta + 360) % 360

            # 大幅偏離保護
            if self._angle_diff(ema_angle, mean) > float(cfg.get("ANGLE_ABORT_DEG", 60.0)):
                log(f"[導航] 與瞬時角度差過大（ema={ema_angle:.1f}°, mean={mean:.1f}°），中止本輪")
                return

            hold_seconds = map_std_to_hold(std)
            # 根據穩定性選擇拖曳方式
            try:
                if std is not None and std <= STD_LOW:
                    # 角度很穩定，使用動態拖曳，可以走更遠
                    # 減少輸出頻率：每3次操作才記錄一次
                    if action_count % 3 == 0:
                        log(f"[導航] 穩定（std={std:.1f}°），動態拖曳最長{hold_seconds:.2f}s")
                    self._dynamic_drag_with_feedback(cx, cy, ema_angle, hold_seconds, cfg, log_fn)
                else:
                    # 角度不穩定，使用傳統固定時間拖曳，保守一點
                    shorter_hold = min(hold_seconds, HOLD_MIN * 2)  # 限制最長時間
                    if action_count % 3 == 0:
                        log(f"[導航] 不穩定（std={std:.1f}°），固定拖曳{shorter_hold:.2f}s")
                    self._hold_drag_seconds(cx, cy, ema_angle, shorter_hold)
            except Exception as e:
                print(f"[錯誤] 拖曳操作異常: {e}")
                log(f"[導航] 拖曳異常，結束導航: {e}")
                return
            
            action_count += 1
            # 握完立刻再量測（越快越能修正）
            time.sleep(max(self.poll, 0.05))

# ==========================
# Worker 執行緒（Start/Pause/Stop）
# ==========================
class WorkerSignals(QObject):
    log = Signal(str)
    finished = Signal()

class DetectorWorker(QThread):
    def __init__(self, cfg, main_window_ref=None):
        super().__init__()
        self.cfg = cfg
        self.main_window = main_window_ref
        self.signals = WorkerSignals()
        self._pause_ev = threading.Event()
        self._stop_ev = threading.Event()
        self._pause_ev.set()  # 預設可跑
        
        # 初始化 Discord 通知器
        self.discord_notifier = DiscordNotifier(cfg)

    def pause(self):
        self._pause_ev.clear()

    def resume(self):
        self._pause_ev.set()

    def stop(self):
        self._stop_ev.set()
        self._pause_ev.set()

    def _log(self, msg):
        """改進的線程安全日誌方法"""
        try:
            # 限制日誌訊息長度，避免極長訊息
            if len(str(msg)) > 500:
                msg = str(msg)[:497] + "..."
            
            self.signals.log.emit(str(msg))
        except Exception as e:
            # 如果日誌發送失敗，至少在 console 中輸出
            print(f"[LOG ERROR] {e}: {str(msg)[:200]}")
            # 嘗試發送簡化版本
            try:
                self.signals.log.emit(f"[日誌錯誤] 原訊息過長或格式錯誤")
            except:
                pass  # 如果連簡化版本都無法發送，就放棄

    def run(self):
        # 穩定性改進：添加循環計數器和記憶體監控
        loop_count = 0
        last_gc_time = time.time()
        gc_interval = 300  # 5分鐘強制GC一次
        
        try:
            icon = ImageDetector(
                template_path=config_file_path(self.cfg["TARGET_IMAGE_PATH"]),
                search_region=self.cfg["ICON_SEARCH_REGION"],
                confidence=self.cfg["ICON_CONFIDENCE"],
                scale_steps=self.cfg["ICON_SCALE_STEPS"],
                scale_range=tuple(self.cfg["ICON_SCALE_RANGE"])
            )
            arrow = ArrowDetector(
                character_template_path=config_file_path(self.cfg["CHARACTER_IMAGE_PATH"]),
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
        icon_lost_logged = False  # 避免重複記錄圖標消失

        self._log("=== 偵測開始 ===")
        while not self._stop_ev.is_set():
            # 暫停
            if not self._pause_ev.is_set():
                time.sleep(0.1)
                continue

            # 穩定性改進：定期垃圾回收和狀態檢查
            loop_count += 1
            current_time = time.time()
            
            # 每300秒（5分鐘）強制垃圾回收和記憶體檢查
            if current_time - last_gc_time > gc_interval:
                try:
                    # 記憶體監控
                    if PSUTIL_AVAILABLE:
                        process = psutil.Process()
                        memory_mb = process.memory_info().rss / 1024 / 1024
                        if memory_mb > 500:  # 超過500MB警告
                            self._log(f"[記憶體警告] 當前使用量: {memory_mb:.1f}MB")
                    
                    # 強制垃圾回收
                    gc.collect()
                    last_gc_time = current_time
                    if loop_count % 100 == 0:  # 減少日誌頻率
                        self._log(f"[穩定性] 已執行 {loop_count} 次循環，執行垃圾回收")
                except Exception as e:
                    print(f"[警告] 穩定性檢查失敗: {e}")
            
            # 每1000次循環記錄狀態
            if loop_count % 1000 == 0:
                if PSUTIL_AVAILABLE:
                    try:
                        process = psutil.Process()
                        memory_mb = process.memory_info().rss / 1024 / 1024
                        self._log(f"[穩定性] 運行狀態良好，已執行 {loop_count} 次循環，記憶體: {memory_mb:.1f}MB")
                    except:
                        self._log(f"[穩定性] 運行狀態良好，已執行 {loop_count} 次循環")
                else:
                    self._log(f"[穩定性] 運行狀態良好，已執行 {loop_count} 次循環")

            # 尋找目標圖標 - 添加異常處理
            try:
                location, scale = icon.find_image_with_scaling(self.cfg)
            except Exception as e:
                print(f"[警告] 圖標偵測異常: {e}")
                self._log(f"[警告] 圖標偵測異常，稍後重試: {e}")
                time.sleep(self.cfg["MAIN_SEARCH_INTERVAL"])
                continue
            if location and scale:
                # 更新 Discord 通知器的檢測時間
                self.discord_notifier.update_detection_time()
                
                if last_status != "found":
                    self._log(f"找到目標圖標：{location}")
                    last_status = "found"
                    icon_lost_logged = False  # 重置標記

                # 箭頭偵測迴圈
                attempts = 0
                while attempts < self.cfg["MAX_ARROW_ATTEMPTS"] and self._pause_ev.is_set() and not self._stop_ev.is_set():
                    # 圖標是否還在
                    current_location, current_scale = icon.find_image_with_scaling(self.cfg)
                    if not current_location:
                        if not icon_lost_logged:
                            self._log("目標圖標消失，回到搜尋。")
                            icon_lost_logged = True
                        last_status = None
                        break
                    else:
                        # 圖標仍然存在，更新檢測時間
                        self.discord_notifier.update_detection_time()

                    # 只在第一次嘗試時記錄，避免頻繁輸出
                    if attempts == 0:
                        self._log(f"[箭頭偵測 {attempts+1}] 點擊圖標(預防性)")
                    icon.click_center(current_location, current_scale, self.cfg)
                    time.sleep(self.cfg["PREVENTIVE_CLICK_DELAY"])

                    # 找人物
                    char_loc, char_scale = arrow.find_character(self.cfg)
                    if char_loc and char_scale:
                        cx = char_loc[0] + (arrow.template_width * char_scale) / 2
                        cy = char_loc[1] + (arrow.template_height * char_scale) / 2
                        if attempts == 0:  # 只在第一次記錄
                            self._log(f"人物座標：({cx:.1f}, {cy:.1f})，蒐集箭頭角度…")
                        # 箭頭偵測迴圈
                        attempts = 0
                        while attempts < self.cfg["MAX_ARROW_ATTEMPTS"] and self._pause_ev.is_set() and not self._stop_ev.is_set():
                            ok = self._follow_arrow_session(icon, arrow)
                            attempts += 1
                            time.sleep(self.cfg["ARROW_SEARCH_INTERVAL"])
                    else:
                        if attempts == 0:  # 只在第一次記錄
                            self._log("未找到人物")

                    attempts += 1
                    time.sleep(self.cfg["ARROW_SEARCH_INTERVAL"])
            else:
                if last_status != "searching":
                    self._log("搜尋目標圖標中…")
                    
                    # 在開始搜尋之前先嘗試聚焦目標視窗
                    if (self.cfg.get("ENABLE_WINDOW_FOCUS", False) and 
                        self.cfg.get("WINDOW_FOCUS_ON_DETECTION", False) and 
                        self.main_window):
                        try:
                            if self.main_window.focus_target_window():
                                self._log("[視窗聚焦] 已將目標視窗設為前景，開始搜尋")
                            else:
                                self._log("[視窗聚焦] 無法聚焦目標視窗，繼續搜尋")
                        except Exception as e:
                            self._log(f"[視窗聚焦錯誤] {e}")
                    
                    last_status = "searching"
                    search_t0 = time.time()
                    icon_lost_logged = False  # 重置標記
                else:
                    # 檢查是否需要發送 Discord 通知
                    self.discord_notifier.check_and_notify()
                    
                    # 只在超過30秒時記錄一次，避免頻繁輸出
                    if time.time() - search_t0 > 30:
                        self._log("持續搜尋中…(>30s)")
                        search_t0 = time.time()
                time.sleep(self.cfg["MAIN_SEARCH_INTERVAL"])

        self._log("=== 偵測結束 ===")
        self.signals.finished.emit()

    def _follow_arrow_session(self, icon: ImageDetector, arrow: ArrowDetector):
        """
        先點圖標→找人物→如果角度穩定就連續導航；導航結束後再點圖標確認。
        """
        try:
            # 圖標是否還在
            try:
                current_location, current_scale = icon.find_image_with_scaling(self.cfg)
            except Exception as e:
                print(f"[警告] 圖標偵測異常: {e}")
                return False
                
            if not current_location:
                # 避免與主循環重複記錄
                return False
            else:
                # 圖標仍然存在，更新檢測時間
                self.discord_notifier.update_detection_time()

            # 預防性點一下（喚醒/聚焦）
            try:
                icon.click_center(current_location, current_scale)
                time.sleep(self.cfg["PREVENTIVE_CLICK_DELAY"])
            except Exception as e:
                print(f"[警告] 預防性點擊失敗: {e}")
                # 點擊失敗不算致命錯誤，繼續執行

            # 找人物中心
            try:
                char_loc, char_scale = arrow.find_character(self.cfg)
            except Exception as e:
                print(f"[警告] 箭頭會話中人物偵測異常: {e}")
                return False
                
            if not (char_loc and char_scale):
                return False

            try:
                cx = char_loc[0] + (arrow.template_width * char_scale) / 2
                cy = char_loc[1] + (arrow.template_height * char_scale) / 2
                self._log(f"開始閉迴路導航…")

                # 連續導航直到箭頭消失或超時
                arrow.guide_towards_arrow(
                    get_center_fn=lambda: (cx, cy),
                    cfg=self.cfg,
                    log_fn=self._log
                )
            except Exception as e:
                print(f"[錯誤] 導航過程異常: {e}")
                self._log(f"導航異常: {e}")
                return False

            # 到站後再點圖標確認
            try:
                time.sleep(self.cfg["POST_MOVE_DELAY"])
                icon.click_center(current_location, current_scale)
                time.sleep(self.cfg["FINAL_CHECK_DELAY"])
            except Exception as e:
                print(f"[警告] 最終確認點擊失敗: {e}")
                # 最終點擊失敗不算致命錯誤
                
            return True
            
        except Exception as e:
            print(f"[錯誤] 箭頭會話整體異常: {e}")
            self._log(f"箭頭會話異常: {e}")
            return False        

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
        self.setWindowTitle("Librer - [V.1.2.2, 2025/09/04]")
        
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
        
        # 初始化視窗管理器
        self.window_manager = WindowManager(self.cfg.get("TARGET_TITLE_KEYWORD", ""))
        
        self._build_ui()
        self._load_cfg_to_ui()
        
        # 初始化視窗狀態
        self.refresh_window_status()

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
        # 當關鍵字改變時，更新視窗狀態
        self.le_title.textChanged.connect(self.on_title_keyword_changed)
        
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
        g1.addWidget(self.le_title, 0, 1, 1, 3)  # 增長輸入框佔用3個網格單位
        
        # 添加視窗狀態指示器
        self.window_status_label = QLabel("⬛")
        self.window_status_label.setStyleSheet("font-size: 14px; font-weight: bold; padding: 1px;")
        self.window_status_label.setToolTip("視窗狀態：未知")
        self.window_status_label.setFixedSize(20, 20)
        self.window_status_label.setAlignment(Qt.AlignCenter)
        
        btn_resize.clicked.connect(self.on_resize_window)
        
        g1.addWidget(btn_resize, 0, 4)
        g1.addWidget(self.window_status_label, 0, 5)  # 將狀態圖示放在按鈕右邊
        
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
        self.btn_start = QPushButton("▶ 開始")
        self.btn_stop = QPushButton("⏹ 停止")
        
        # 設定按鈕樣式和大小
        button_style = """
            QPushButton {
                font-size: 14px;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
                border: 2px solid;
                min-width: 80px;
            }
        """
        
        start_style = button_style + """
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-color: #45a049;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
                border-color: #999999;
            }
        """
        
        stop_style = button_style + """
            QPushButton {
                background-color: #f44336;
                color: white;
                border-color: #da190b;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:pressed {
                background-color: #c1160a;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
                border-color: #999999;
            }
        """
        
        self.btn_start.setStyleSheet(start_style)
        self.btn_stop.setStyleSheet(stop_style)
        
        self.btn_start.clicked.connect(self.on_start)
        self.btn_stop.clicked.connect(self.on_stop)
        
        control_layout.addWidget(self.btn_start)
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
        # 創建日誌區域容器
        log_container = QVBoxLayout()
        
        # 日誌控制按鈕
        log_controls = QHBoxLayout()
        
        # 自動置底切換按鈕
        self.btn_auto_scroll = QPushButton("🔽 自動置底")
        self.btn_auto_scroll.setCheckable(True)
        self.btn_auto_scroll.setChecked(True)  # 預設開啟
        self.btn_auto_scroll.setToolTip("開啟時自動滾動到最新日誌，關閉時保持當前位置")
        self.btn_auto_scroll.clicked.connect(self.toggle_auto_scroll)
        
        # 置底按鈕
        self.btn_scroll_bottom = QPushButton("⬇️ 置底")
        self.btn_scroll_bottom.setToolTip("立即滾動到最新日誌")
        self.btn_scroll_bottom.clicked.connect(self.scroll_to_bottom)
        
        # 置頂按鈕
        self.btn_scroll_top = QPushButton("⬆️ 置頂")
        self.btn_scroll_top.setToolTip("滾動到最早的日誌")
        self.btn_scroll_top.clicked.connect(self.scroll_to_top)
        
        # 清空日誌按鈕
        self.btn_clear_log = QPushButton("🗑️ 清空")
        self.btn_clear_log.setToolTip("清空所有日誌")
        self.btn_clear_log.clicked.connect(self.clear_log)
        
        log_controls.addWidget(self.btn_auto_scroll)
        log_controls.addWidget(self.btn_scroll_bottom)
        log_controls.addWidget(self.btn_scroll_top)
        log_controls.addWidget(self.btn_clear_log)
        log_controls.addStretch()  # 推到左邊
        
        # 日誌狀態標籤
        self.log_status = QLabel("自動置底：開啟")
        self.log_status.setStyleSheet("color: #0066cc; font-size: 11px;")
        log_controls.addWidget(self.log_status)
        
        # 主要日誌區域
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(180)
        
        # 連接滾動條事件，檢測用戶是否在查看歷史
        self.log_scrollbar = self.log.verticalScrollBar()
        self.log_scrollbar.valueChanged.connect(self.on_log_scroll)
        
        # 設定自動置底狀態（從配置載入）
        self.auto_scroll_enabled = self.cfg.get("LOG_AUTO_SCROLL", True)
        self.btn_auto_scroll.setChecked(self.auto_scroll_enabled)
        self.toggle_auto_scroll()  # 套用初始狀態
        
        self.user_is_browsing = False  # 用戶是否在瀏覽歷史
        self.last_scroll_position = 0
        
        log_container.addLayout(log_controls)
        log_container.addWidget(self.log)
        
        # 創建日誌群組
        grp_log = QGroupBox("日誌")
        grp_log.setLayout(log_container)

        layout.addWidget(grp_win)
        layout.addWidget(grp_region)
        layout.addWidget(grp_ctrl)
        layout.addWidget(grp_log)

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


    def toggle_auto_scroll(self):
        """切換自動置底模式"""
        self.auto_scroll_enabled = self.btn_auto_scroll.isChecked()
        
        if self.auto_scroll_enabled:
            self.btn_auto_scroll.setText("🔽 自動置底")
            self.log_status.setText("自動置底：開啟")
            self.log_status.setStyleSheet("color: #0066cc; font-size: 11px;")
            # 立即滾動到底部
            self.scroll_to_bottom()
        else:
            self.btn_auto_scroll.setText("⏸️ 手動模式")
            self.log_status.setText("自動置底：關閉")
            self.log_status.setStyleSheet("color: #ff6600; font-size: 11px;")
    
    def scroll_to_bottom(self):
        """滾動到日誌底部"""
        scrollbar = self.log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        self.user_is_browsing = False
    
    def scroll_to_top(self):
        """滾動到日誌頂部"""
        scrollbar = self.log.verticalScrollBar()
        scrollbar.setValue(scrollbar.minimum())
        self.user_is_browsing = True
        # 暫時停用自動置底
        if self.auto_scroll_enabled:
            self.btn_auto_scroll.setChecked(False)
            self.toggle_auto_scroll()
    
    def clear_log(self):
        """清空日誌"""
        reply = QMessageBox.question(
            self, "確認清空", 
            "確定要清空所有日誌嗎？\n此操作無法復原。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.log.clear()
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.log.append(f"[{timestamp}] [系統] 日誌已手動清空")
            # 重置計數器
            if hasattr(self, '_log_count'):
                self._log_count = 0
    
    def on_log_scroll(self, value):
        """處理日誌滾動事件"""
        scrollbar = self.log.verticalScrollBar()
        max_value = scrollbar.maximum()
        
        # 記錄滾動位置變化
        scroll_delta = value - self.last_scroll_position
        self.last_scroll_position = value
        
        # 檢測用戶是否在查看歷史記錄
        if max_value > 0:
            # 使用配置的滾動敏感度
            scroll_sensitivity = self.cfg.get("LOG_SCROLL_SENSITIVITY", 10)
            
            # 如果不在底部且是用戶主動滾動（不是程式滾動）
            if value < max_value - scroll_sensitivity:
                if not self.user_is_browsing:
                    self.user_is_browsing = True
                    # 顯示提示
                    self.log_status.setText("正在瀏覽歷史記錄")
                    self.log_status.setStyleSheet("color: #666666; font-size: 11px;")
            else:
                # 滾動到底部時
                if self.user_is_browsing:
                    self.user_is_browsing = False
                    # 恢復狀態顯示
                    if self.auto_scroll_enabled:
                        self.log_status.setText("自動置底：開啟")
                        self.log_status.setStyleSheet("color: #0066cc; font-size: 11px;")
                    else:
                        self.log_status.setText("自動置底：關閉")
                        self.log_status.setStyleSheet("color: #ff6600; font-size: 11px;")
    
    def _ui_to_cfg(self):
        """將 UI 元素的值更新到配置中"""
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

    def smart_scroll_to_bottom(self):
        """智能滾動到底部 - 只在自動模式且用戶未瀏覽時執行"""
        if self.auto_scroll_enabled and not self.user_is_browsing:
            self.scroll_to_bottom()
        # 更新配置
        self._ui_to_cfg()

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

    def refresh_window_status(self):
        """重新整理視窗狀態"""
        if not self.cfg.get("ENABLE_WINDOW_FOCUS", False):
            self.window_status_label.setText("⚪")
            self.window_status_label.setStyleSheet("font-size: 16px; font-weight: bold;")
            self.window_status_label.setToolTip("視窗聚焦功能已停用")
            return
            
        # 更新視窗管理器的關鍵字
        keyword = self.le_title.text().strip()
        self.window_manager.update_keyword(keyword)
        
        # 檢查視窗狀態
        status = self.window_manager.refresh_window_status()
        
        if status == "found":
            self.window_status_label.setText("🟩")
            self.window_status_label.setStyleSheet("font-size: 16px; font-weight: bold;")
            self.window_status_label.setToolTip(f"已找到目標視窗：{self.window_manager.target_window.title if self.window_manager.target_window else ''}")
            self.append_log(f"[視窗狀態] 已找到目標視窗")
        elif status == "not_found":
            self.window_status_label.setText("🟥")
            self.window_status_label.setStyleSheet("font-size: 16px; font-weight: bold;")
            self.window_status_label.setToolTip(f"未找到包含關鍵字 '{keyword}' 的視窗")
            self.append_log(f"[視窗狀態] 未找到目標視窗")
        else:
            self.window_status_label.setText("⬛")
            self.window_status_label.setStyleSheet("font-size: 16px; font-weight: bold;")
            self.window_status_label.setToolTip("視窗狀態：未知")

    def on_title_keyword_changed(self):
        """當目標視窗關鍵字改變時的處理"""
        # 延遲更新狀態，避免在快速打字時頻繁更新
        if hasattr(self, '_title_update_timer'):
            self._title_update_timer.stop()
        
        from PySide6.QtCore import QTimer
        self._title_update_timer = QTimer()
        self._title_update_timer.setSingleShot(True)
        self._title_update_timer.timeout.connect(self.refresh_window_status)
        self._title_update_timer.start(500)  # 500ms 延遲

    def focus_target_window(self):
        """聚焦目標視窗"""
        if not self.cfg.get("ENABLE_WINDOW_FOCUS", False):
            return False
            
        if self.window_manager.focus_window():
            self.append_log("[視窗聚焦] 成功聚焦目標視窗")
            return True
        else:
            self.append_log("[視窗聚焦] 無法聚焦目標視窗")
            return False

    def update_button_status(self, status):
        """
        status: "running", "stopped"
        """
        if status == "running":
            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(True)
            self.btn_start.setText("運行中...")
        elif status == "stopped":
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.btn_start.setText("開始")
            self.btn_stop.setText("停止")

    def on_start(self):
        self._ui_to_cfg(); save_cfg(self.cfg)
        
        # 更新視窗管理器的關鍵字
        self.window_manager.update_keyword(self.cfg["TARGET_TITLE_KEYWORD"])
        
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "提示", "已在執行中")
            return
        self.worker = DetectorWorker(self.cfg, self)  # 傳遞自己的參考
        self.worker.signals.log.connect(self.append_log)
        self.worker.signals.finished.connect(lambda: self.append_log("[Worker 結束]"))
        self.worker.signals.finished.connect(lambda: self.update_button_status("stopped"))
        self.worker.start()
        self.append_log("[Worker 啟動]")
        self.update_button_status("running")

    def on_stop(self):
        """改進的停止方法，增加超時保護"""
        if self.worker and self.worker.isRunning():
            try:
                self.worker.stop()
                # 增加超時保護，避免無限等待
                if not self.worker.wait(5000):  # 等待5秒
                    self.append_log("[警告] Worker停止超時，強制結束")
                    self.worker.terminate()
                    if not self.worker.wait(2000):  # 再等待2秒
                        self.append_log("[錯誤] Worker無法正常結束")
                self.append_log("[停止]")
                self.update_button_status("stopped")
            except Exception as e:
                self.append_log(f"[錯誤] 停止Worker時發生異常: {e}")
                # 強制重置狀態
                self.worker = None
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
                
                # 更新 worker 的 Discord 通知器（如果 worker 正在運行）
                if self.worker and self.worker.isRunning():
                    self.worker.discord_notifier = DiscordNotifier(self.cfg)
                    self.append_log("[設定] Discord 通知設定已更新")
                
                # 更新視窗狀態
                self.refresh_window_status()
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
        """改進的日誌添加方法，減少閃退風險"""
        try:
            # 檢查是否啟用安全模式
            if not self.cfg.get("LOG_SAFE_MODE", True):
                # 如果禁用安全模式，使用原始方法
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.log.append(f"[{timestamp}] {s}")
                return
            
            # 添加時間戳記
            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted_msg = f"[{timestamp}] {s}"
            
            # 限制單條日誌長度，避免極長日誌導致問題
            max_length = self.cfg.get("LOG_MAX_MSG_LENGTH", 500)
            if len(formatted_msg) > max_length:
                formatted_msg = formatted_msg[:max_length-3] + "..."
            
            # 添加到日誌區域
            self.log.append(formatted_msg)
            
            # 智能滾動到底部
            self.smart_scroll_to_bottom()
            
            # 改進的清理機制：降低觸發頻率
            if self.cfg.get("LOG_AUTO_CLEANUP", True):
                # 使用計數器減少檢查頻率
                if not hasattr(self, '_log_count'):
                    self._log_count = 0
                self._log_count += 1
                
                # 根據配置決定檢查頻率
                cleanup_freq = self.cfg.get("LOG_CLEANUP_FREQUENCY", 10)
                if self._log_count % cleanup_freq == 0:
                    self._safe_cleanup_log_if_needed()
                    
        except Exception as e:
            # 日誌處理失敗時的處理策略
            if self.cfg.get("LOG_DISABLE_ON_ERROR", True):
                # 禁用自動清理避免重複錯誤
                self.cfg["LOG_AUTO_CLEANUP"] = False
                print(f"[系統] 日誌處理發生錯誤，已禁用自動清理: {e}")
            
            # 嘗試記錄基本訊息
            try:
                # 嘗試簡單的日誌添加
                simple_msg = f"[{datetime.now().strftime('%H:%M:%S')}] {str(s)[:100]}..."
                self.log.append(simple_msg)
                # 嘗試智能滾動
                try:
                    self.smart_scroll_to_bottom()
                except:
                    pass  # 滾動失敗也不是致命問題
            except:
                # 如果還是失敗，只在控制台輸出
                print(f"[嚴重] 日誌系統無法運作: {e}")
                print(f"[訊息] {str(s)[:200]}")
                # 完全禁用日誌功能
                self.cfg["LOG_AUTO_CLEANUP"] = False
    
    def _safe_cleanup_log_if_needed(self):
        """安全的日誌清理方法，加強異常處理"""
        try:
            max_lines = self.cfg.get("LOG_MAX_LINES", 500)
            cleanup_lines = self.cfg.get("LOG_CLEANUP_LINES", 100)
            
            # 使用 QTextDocument 的行數檢查，比字串分割更有效率
            document = self.log.document()
            current_line_count = document.blockCount()
            
            if current_line_count > max_lines:
                # 使用更安全的方式清理日誌
                self._perform_safe_log_cleanup(cleanup_lines)
                
        except Exception as e:
            print(f"[警告] 日誌清理檢查失敗: {e}")
            # 清理失敗時禁用自動清理，避免重複錯誤
            self.cfg["LOG_AUTO_CLEANUP"] = False
    
    def _perform_safe_log_cleanup(self, keep_lines):
        """執行安全的日誌清理"""
        try:
            # 方法1：使用 QTextCursor 進行增量清理，避免全文操作
            cursor = self.log.textCursor()
            cursor.movePosition(cursor.Start)
            
            # 計算需要刪除的行數
            document = self.log.document()
            total_lines = document.blockCount()
            lines_to_delete = total_lines - keep_lines
            
            if lines_to_delete > 0:
                # 選擇並刪除前面的行
                for _ in range(lines_to_delete):
                    cursor.select(cursor.BlockUnderCursor)
                    cursor.removeSelectedText()
                    cursor.deleteChar()  # 刪除換行符
                
                # 添加清理標記
                cursor.movePosition(cursor.Start)
                timestamp = datetime.now().strftime("%H:%M:%S")
                cleanup_msg = f"[{timestamp}] [系統] 日誌已清理，保留最新 {keep_lines} 行記錄\n"
                cursor.insertText(cleanup_msg)
                
                # 捲動到底部
                cursor.movePosition(cursor.End)
                self.log.setTextCursor(cursor)
                
                # 使用智能滾動
                self.smart_scroll_to_bottom()
                
        except Exception as e:
            print(f"[錯誤] 日誌清理執行失敗: {e}")
            # 如果增量清理失敗，嘗試備用方案
            self._fallback_log_cleanup(keep_lines)
    
    def _fallback_log_cleanup(self, keep_lines):
        """備用的日誌清理方案"""
        try:
            # 備用方案：直接重置日誌區域
            timestamp = datetime.now().strftime("%H:%M:%S")
            fallback_msg = f"[{timestamp}] [系統] 日誌已重置（清理失敗時的備用方案）\n"
            self.log.setPlainText(fallback_msg)
            print("[系統] 使用備用日誌清理方案")
            
        except Exception as e:
            print(f"[嚴重錯誤] 備用日誌清理也失敗: {e}")
            # 最後手段：禁用日誌功能
            self.cfg["LOG_AUTO_CLEANUP"] = False

    def closeEvent(self, e):
        try:
            # 保存日誌UI偏好設定
            self.cfg["LOG_AUTO_SCROLL"] = self.auto_scroll_enabled
            
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
