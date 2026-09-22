#!/bin/bash
# Recover RK1828 EP before P5b vlm_daemon (fixes ERROR_PIPE / rknn_init -10).
set -euo pipefail

AGENT="${AGENT_ROOT:-/userdata/agent}"

echo "[recover] stop vlm + llm on 1828..."
systemctl stop r1-vlm-daemon.service 2>/dev/null || true
systemctl stop r1-llm-daemon.service 2>/dev/null || true
pkill -9 -f '/userdata/agent/bin/vlm_daemon' 2>/dev/null || true
pkill -9 -f '/userdata/agent/bin/llm_daemon' 2>/dev/null || true
pkill -9 -f rknn_internvl3_demo 2>/dev/null || true
sleep 2

echo "[recover] restart rknn stack..."
systemctl restart rknn-mdns.service 2>/dev/null || true
systemctl restart rknn3.service
sleep 8

if ! bash "${AGENT}/scripts/wait_rknn_vlm.sh" 90; then
  echo "[recover] EP still bad — cold reboot recommended: adb reboot" >&2
  exit 1
fi

echo "[recover] start P5b vlm_daemon..."
systemctl reset-failed r1-vlm-daemon.service 2>/dev/null || true
systemctl start r1-vlm-daemon.service
bash "${AGENT}/scripts/wait_vlm_sock.sh" /tmp/r1-vlm.sock 240
echo "[recover] ok — ping:"
python3 "${AGENT}/scripts/llm_client.py" --socket /tmp/r1-vlm.sock --ping
