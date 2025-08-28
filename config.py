# 配置文件 - config.py
# 所有可調整的參數都在這裡

# ===== 窗口設定 =====
# 目標窗口標題關鍵字
TARGET_TITLE_KEYWORD = "[AFK1]"

# 窗口位置和尺寸
WINDOW_POSITION_X = 0
WINDOW_POSITION_Y = 0
WINDOW_WIDTH = 1080
WINDOW_HEIGHT = 1620

# ===== 圖標偵測設定 =====
# 目標圖標文件路徑
TARGET_IMAGE_PATH = 'target.png'

# 圖標搜尋區域 (x, y, width, height)
ICON_SEARCH_REGION = (800, 800, 300, 300)

# 圖標偵測信心度 (0.0 ~ 1.0)
ICON_CONFIDENCE = 0.85

# 圖標縮放搜尋範圍
ICON_SCALE_RANGE = (0.95, 1.05)

# 圖標縮放搜尋步數
ICON_SCALE_STEPS = 10

# ===== 人物偵測設定 =====
# 人物圖標文件路徑
CHARACTER_IMAGE_PATH = 'character.png'

# 人物搜尋區域 (x, y, width, height)
CHARACTER_SEARCH_REGION = (200, 700, 700, 400)

# 人物偵測信心度 (0.0 ~ 1.0)
CHARACTER_CONFIDENCE = 0.5

# 人物縮放搜尋範圍
CHARACTER_SCALE_RANGE = (0.7, 1.3)

# 人物縮放搜尋步數
CHARACTER_SCALE_STEPS = 10

# ===== 箭頭偵測設定 =====
# 箭頭搜尋半徑（以人物為中心）
ARROW_SEARCH_RADIUS = 100

# 箭頭最小面積
ARROW_MIN_AREA = 300

# 箭頭偵測超時時間（秒）
ARROW_DETECTION_TIMEOUT = 3.0

# 箭頭偵測輪詢間隔（秒）
ARROW_POLL_INTERVAL = 0.12

# 箭頭偵測最少命中次數
ARROW_MIN_HITS = 1

# ===== 移動控制設定 =====
# 拖曳距離（像素）
DRAG_DISTANCE = 100

# 拖曳持續時間（秒）
DRAG_HOLD_SECONDS = 2.0

# 拖曳按鈕
DRAG_BUTTON = 'left'

# ===== 循環控制設定 =====
# 主搜尋間隔（秒）
MAIN_SEARCH_INTERVAL = 1.0

# 箭頭偵測間隔（秒）
ARROW_SEARCH_INTERVAL = 0.5

# 最大箭頭偵測嘗試次數
MAX_ARROW_ATTEMPTS = 20

# ===== 點擊時間設定 =====
# 預防性點擊後等待時間（秒）
PREVENTIVE_CLICK_DELAY = 0.3

# 移動後點擊前等待時間（秒）
POST_MOVE_DELAY = 1.0

# 最終狀態檢查等待時間（秒）
FINAL_CHECK_DELAY = 0.5
