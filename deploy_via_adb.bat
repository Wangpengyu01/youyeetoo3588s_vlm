@echo off
chcp 65001 >nul
title 小揽 · RK3588 ADB 一键安装与端口映射工具

echo ============================================================
echo       小揽 · RK3588 边缘端智能终端 ADB 一键部署工具
echo ============================================================
echo.

:: 1. 检查 ADB 是否可用
where adb >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 未在系统 PATH 中检测到 adb 命令！
    echo 请安装 Android SDK Platform-Tools 并将其加入系统环境变量。
    pause
    exit /b 1
)

:: 2. 检测设备连接状态
echo [1/5] 正在检测 RK3588 开发板连接状态...
adb devices
for /f "skip=1 tokens=1,2" %%A in ('adb devices') do (
    if "%%B"=="device" (
        set DEVICE_FOUND=1
    )
)

if not defined DEVICE_FOUND (
    echo.
    echo [提示] 当前未检测到已连接的 ADB 设备！
    echo 请确认：
    echo 1. USB Type-C 数据线已连接电脑与开发板的 OTG 调试口；
    echo 2. 开发板已正常通电开机；
    echo 3. 开发板已启用 adbd 服务。
    echo.
    set /p RETRY="是否重新检测？(Y/N): "
    if /i "%RETRY%"=="Y" goto :check_again
    pause
    exit /b 1
)

:check_again

:: 3. 创建板端目录并同步代码
echo.
echo [2/6] 正在推送 agent 核心中枢至板卡 /userdata/agent...
adb shell "mkdir -p /userdata/agent"
adb push "%~dp0agent\." /userdata/agent/
if %errorlevel% neq 0 (
    echo [错误] 推送 agent 失败，请检查 USB 连接与板卡磁盘空间。
    pause
    exit /b 1
)

echo.
echo [3/6] 正在推送 InternVL3.5-4B VLM Demo 至 /userdata/rknn_InternVLM_demo...
if exist "%~dp0rknn_InternVLM_demo" (
    adb shell "mkdir -p /userdata/rknn_InternVLM_demo"
    adb push "%~dp0rknn_InternVLM_demo\." /userdata/rknn_InternVLM_demo/
    adb shell "chmod +x /userdata/rknn_InternVLM_demo/rknn_internvl3_demo"
)

echo.
echo [4/6] 正在推送 P4 看图说话与 RTSP 脚本至 /userdata/p4...
if exist "%~dp0p4" (
    adb shell "mkdir -p /userdata/p4"
    adb push "%~dp0p4\." /userdata/p4/
    adb shell "chmod +x /userdata/p4/scripts/*.sh /userdata/p4/scripts/*.py"
)

:: 4. 授予脚本执行权限
echo.
echo [5/6] 正在赋予运行与启停脚本执行权限...
adb shell "chmod +x /userdata/agent/scripts/*.sh"

:: 5. 端口映射 (adb forward)
echo.
echo [4/5] 正在配置 USB 端口映射 (电脑直接访问板端 Web)...
adb forward tcp:8766 tcp:8766
adb forward tcp:8765 tcp:8765
echo • Web 控制台端口映射: localhost:8766 -^> 板端:8766 [成功]
echo • WebSocket 端口映射: localhost:8765 -^> 板端:8765 [成功]

:: 6. 引导启动服务
echo.
echo [5/5] 部署完成！
echo ============================================================
echo 您可以通过以下操作启动小揽服务：
echo.
echo 【方案 A】直接在本窗口启动板端服务：
echo   按 [1] 键启动服务并实时查看日志
echo.
echo 【方案 B】稍后手动启动：
echo   adb shell "bash /userdata/agent/scripts/quickstart_all.sh"
echo.
echo 启动后在电脑浏览器直接访问: http://127.0.0.1:8766
echo ============================================================
echo.

set /p CHOICE="请输入选项 [1 启动 / 其他键退出]: "
if "%CHOICE%"=="1" (
    echo.
    echo 正在启动小揽全套服务...
    adb shell "bash /userdata/agent/scripts/quickstart_all.sh"
    echo.
    echo 正在打开电脑浏览器...
    start http://127.0.0.1:8766
    echo.
    echo 正在监控实时日志 (按 Ctrl+C 退出日志监控，后台服务不受影响)...
    adb shell "tail -f /userdata/agent/logs/orchestrator.log"
)

pause
