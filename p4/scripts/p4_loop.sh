#!/bin/bash
# P4 loop: RTSP grab + InternVL caption
# Note: stock rknn_internvl3_demo reloads models each call (~25-35s).
# True 1fps needs P5 persistent VLM daemon (later optimization).
set -euo pipefail
source "$(dirname "$0")/p4_env.sh"

COUNT="${1:-0}"

echo "=== P4 RTSP → InternVL 短描述 ==="
echo "RTSP: ${RTSP_URL}"
echo "R1:   ${STATIC_IP} · ${STREAM_WIDTH}x${STREAM_HEIGHT} → ${VLM_SIZE}²"
echo "提示: 每轮约 25-35s（含模型加载）；1828 勿与 voice_chat LLM 同时占用"
echo "Ctrl+C 退出"
echo

bash "${SCRIPTS}/net_static.sh" 2>/dev/null || true
bash "${SCRIPTS}/wait_rknn.sh"

N=0
while true; do
  N=$((N + 1))
  T0=$(date +%s%3N)
  echo "--- #${N} $(date '+%H:%M:%S') ---"

  bash "${SCRIPTS}/rtsp_grab_once.sh" "${LATEST_FRAME}" || {
    echo "[P4] 取帧失败"
    sleep 2
    continue
  }

  bash "${SCRIPTS}/vlm_see.sh" "${LATEST_FRAME}" || {
    echo "[P4] VLM 失败（若 MODEL_SETUP fail → adb reboot 冷启动）"
    sleep 5
    continue
  }

  T1=$(date +%s%3N)
  echo "[P4] 本轮 $((T1 - T0)) ms"
  if [ "${COUNT}" -gt 0 ] && [ "${N}" -ge "${COUNT}" ]; then
    break
  fi
done
