# -*- mode: python ; coding: utf-8 -*-

# 減少防毒誤報的配置
block_cipher = None

# 只內嵌必要的資源
internal_files = [
    ('gear_icon_24.png', '.'),
    ('gear_icon_32.png', '.'),
    ('zeny.ico', '.'),
    ('zeny.png', '.'),
]

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=internal_files,
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtWidgets', 
        'PySide6.QtGui',
        'cv2',
        'numpy',
        'pyautogui',
        'pygetwindow',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除不需要的模組減少檔案大小和誤報
        'tkinter',
        'matplotlib',
        'scipy',
        'pandas',
        'IPython',
        'jupyter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,  # 設為 True 可能減少誤報但會增加啟動時間
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Librer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # 關閉 UPX 壓縮，減少誤報
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='zeny.ico',
    version='version_info.txt',  # 添加版本資訊
)
