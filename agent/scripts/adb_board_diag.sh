#!/bin/bash
# Quick hang diagnosis on R1 (run: adb shell "bash /userdata/agent/scripts/adb_board_diag.sh")
set -eu

echo "=== load / uptime ==="
cat /proc/loadavg
uptime

echo "=== D-state (first 15) ==="
ps -eo stat,pid,cmd | grep '^D' | head -15 || true
dc=$(ps -eo stat | grep -c '^D' || true)
echo "D_count=${dc}"

echo "=== RTSP competitors ==="
pgrep -af 'gst-launch|orchestrator.main|rtsp_grab|grab_camera' || echo "(none)"

echo "=== stuck ip/nmcli adb probes ==="
pgrep -af 'ip -.*addr show|nmcli -t' || echo "(none)"

echo "=== camera tcp554 ==="
CAM="${CAM_IP:-192.168.2.169}"
if timeout 2 bash -c "echo > /dev/tcp/${CAM}/554" 2>/dev/null; then
  echo "tcp ${CAM}:554 OK"
else
  echo "tcp ${CAM}:554 FAIL"
fi

echo "=== hint ==="
echo "If D_count>5 or adb hangs: kill competing gst, avoid parallel adb shells; reboot if NM/ip stay in D."
