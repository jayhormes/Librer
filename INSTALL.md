# 安裝說明

## 方法一：使用完整版 requirements.txt（推薦）

```bash
pip install -r requirements.txt
```

這個文件包含了具體的版本號，確保相容性。

## 方法二：使用最小版本

```bash
pip install -r requirements-minimal.txt
```

這個文件只包含主要套件，會自動安裝最新版本。

## 方法三：手動安裝主要套件

```bash
pip install opencv-python pyautogui numpy pygetwindow
```

## 系統需求

- Python 3.7 或更高版本
- Windows 作業系統（因為使用了 pygetwindow）

## 驗證安裝

安裝完成後，可以運行以下命令驗證：

```python
import cv2
import pyautogui
import numpy as np
import pygetwindow as gw
print("所有套件安裝成功！")
```

## 常見問題

### OpenCV 安裝問題
如果 opencv-python 安裝失敗，可以嘗試：
```bash
pip install opencv-python-headless
```

### PyAutoGUI 權限問題
在某些系統上可能需要管理員權限或額外設定。

### 虛擬環境（推薦）
建議使用虛擬環境避免套件衝突：
```bash
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```
