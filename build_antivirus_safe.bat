@echo off
echo ================================================
echo Librer 防毒安全版本打包腳本
echo ================================================
echo.

echo 正在檢查 Python 環境...
if not exist "run\Scripts\python.exe" (
    echo 錯誤：找不到 Python 虛擬環境
    pause
    exit /b 1
)

echo 正在檢查 PyInstaller...
if not exist "run\Scripts\pyinstaller.exe" (
    echo 安裝 PyInstaller...
    run\Scripts\pip.exe install pyinstaller
)

echo.
echo 正在清理之前的打包結果...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

echo.
echo 🛡️ 使用防毒安全配置打包...
echo 配置: 關閉 UPX 壓縮，添加版本資訊
echo 排除: 不必要的模組以減少檔案大小
echo.

run\Scripts\pyinstaller.exe app_antivirus_safe.spec

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ================================================
    echo 打包失敗！
    echo ================================================
    pause
    exit /b 1
)

echo.
echo 正在複製配置文件和資源...
copy "config.json" "dist\" >nul 2>&1
echo ✅ 已複製 config.json

echo.
echo 正在創建 images 資料夾...
if not exist "dist\images" mkdir "dist\images"
copy "images\target.png" "dist\images\" >nul 2>&1
copy "images\character.png" "dist\images\" >nul 2>&1
copy "images\arrow.png" "dist\images\" >nul 2>&1
echo ✅ 已複製圖片資源

echo.
echo ================================================
echo 🎉 防毒安全版本打包完成！
echo ================================================
echo.
echo 執行檔: dist\Librer.exe
if exist "dist\Librer.exe" (
    for %%A in ("dist\Librer.exe") do echo 大小: %%~zA bytes
)
echo.
echo 🛡️ 減少誤報的措施:
echo   ✅ 關閉 UPX 壓縮
echo   ✅ 添加詳細版本資訊
echo   ✅ 排除不必要模組
echo   ✅ 使用標準打包配置
echo.
echo 📝 如果仍有誤報，請：
echo   1. 查看 CODE_SIGNING_GUIDE.md (程式碼簽名)
echo   2. 查看 ANTIVIRUS_WHITELIST.md (白名單提交)
echo   3. 建議用戶添加到防毒軟體排除清單
echo.

pause
