@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 若 recover.bat 卡在 waiting vlm — 先 Ctrl+C，再运行本脚本
adb push "%~dp0recover_nohup_adb.sh" /userdata/agent/scripts/recover_nohup_adb.sh
adb shell "sed -i 's/\r$//' /userdata/agent/scripts/recover_nohup_adb.sh /userdata/agent/scripts/*.sh /userdata/p4/scripts/*.sh 2>/dev/null; chmod +x /userdata/agent/scripts/recover_nohup_adb.sh"
adb shell "pkill -f wait_vlm_sock || true; systemctl reset-failed 2>/dev/null || true"
adb shell "bash /userdata/agent/scripts/recover_nohup_adb.sh"
adb forward tcp:8765 tcp:8765
adb forward tcp:8766 tcp:8766
pause
