#!/bin/bash
# Probe RTSP connectivity and codec
set -euo pipefail
source "$(dirname "$0")/p4_env.sh"

echo "=== P4 RTSP 探测 ==="
echo "URL: ${RTSP_URL}"
echo "R1 IP: $(ip -4 -br addr show eth0 | awk '{print $3}')"
echo

CAM_IP=$(echo "${RTSP_URL}" | sed -E 's|rtsp://([^:/]+).*|\1|')
ping -c 2 -W 2 "${CAM_IP}" && echo "[OK] ping ${CAM_IP}" || echo "[FAIL] ping ${CAM_IP}"

for codec in h264 h265; do
  echo
  echo "--- 试 ${codec} ---"
  RTSP_CODEC="${codec}" GRAB_TIMEOUT_SEC=10 \
    bash "${SCRIPTS}/rtsp_grab_once.sh" "/tmp/rtsp_probe_${codec}.jpg" && {
    echo "[OK] ${codec} 取帧成功 → /tmp/rtsp_probe_${codec}.jpg"
    file "/tmp/rtsp_probe_${codec}.jpg" 2>/dev/null || true
  } || echo "[FAIL] ${codec}"
done
