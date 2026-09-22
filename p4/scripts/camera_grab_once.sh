#!/bin/bash
# Grab one JPEG frame from Network Camera (HTTP endpoint)
# Xiao Lan / Phase 4 Vision Pipeline
set -euo pipefail

source "$(dirname "$0")/p4_env.sh"

CAMERA_URL="${CAMERA_URL:-http://10.0.0.159:8080/shot.jpg}"
OUT="${1:-${LATEST_FRAME}}"
TMP="${OUT}.part"
TIMEOUT_SEC="${CAMERA_TIMEOUT_SEC:-3}"

echo "[Camera] 从网络摄像头拉取画面: ${CAMERA_URL} -> ${OUT}" >&2

if curl -s -f -m "${TIMEOUT_SEC}" "${CAMERA_URL}" -o "${TMP}"; then
  if [ -s "${TMP}" ]; then
    mv -f "${TMP}" "${OUT}"
    BYTES=$(wc -c < "${OUT}")
    echo "[Camera] 抓帧成功: ${OUT} (${BYTES} bytes)" >&2
    exit 0
  fi
fi

echo "[Camera] 抓帧失败: 无法从 ${CAMERA_URL} 获取有效 JPEG 画面" >&2
rm -f "${TMP}"
exit 1
