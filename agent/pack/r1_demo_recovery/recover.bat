@echo off
setlocal
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo ============================================================
echo   R1 userdata 一键恢复 (adb push + systemd)
echo   解压目录: %~dp0
echo ============================================================
echo.

where adb >nul 2>&1
if errorlevel 1 (
  echo [ERROR] 未找到 adb.exe，请安装 Android platform-tools 并加入 PATH。
  pause
  exit /b 1
)

adb devices 2>nul | findstr /r "device$" >nul
if errorlevel 1 (
  echo [ERROR] 无 adb 设备。请 USB 连接板子后执行: adb devices
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0recover.ps1" %*
set ERR=%ERRORLEVEL%
echo.
if %ERR% neq 0 (
  echo [FAILED] exit code %ERR%
) else (
  echo [OK] 恢复流程结束。WebUI: http://127.0.0.1:8766/ （需 adb forward）
)
pause
exit /b %ERR%
