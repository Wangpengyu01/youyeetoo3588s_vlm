#!/bin/bash
# One-shot P4 smoke test: network + grab + caption
set -euo pipefail
source "$(dirname "$0")/p4_env.sh"

echo "=== P4 冒烟测试 ==="
echo "[P4] 1/4 网络..."
bash "${SCRIPTS}/net_static.sh"
echo "[P4] 2/4 等待 RKNN + 检查 1828 空闲..."
bash "${SCRIPTS}/wait_rknn.sh"
bash "${SCRIPTS}/p4_check_1828.sh"
echo "[P4] 3/4 RTSP 取帧..."
bash "${SCRIPTS}/rtsp_grab_once.sh"
echo "[P4] 4/4 VLM 看图 + TTS..."
bash "${SCRIPTS}/vlm_see.sh"
echo "=== P4 冒烟完成 ==="
