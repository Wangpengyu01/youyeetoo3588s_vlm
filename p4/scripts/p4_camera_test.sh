#!/bin/bash
# One-shot Camera VLM & TTS test (Xiao Lan / Phase 4)
set -euo pipefail
source "$(dirname "$0")/p4_env.sh"

export CAMERA_URL="${CAMERA_URL:-http://10.0.0.159:8080/shot.jpg}"

echo "=================================================="
echo "      小榄网络摄像头 (VLM + TTS) 联调测试"
echo "=================================================="

echo "[1/3] 检查 RKNN 与 NPU 状态..."
bash "${SCRIPTS}/wait_rknn.sh" || true
bash "${SCRIPTS}/p4_check_1828.sh" || true

echo "[2/3] 从网络摄像头抓帧 (${CAMERA_URL})..."
if ! bash "${SCRIPTS}/camera_grab_once.sh"; then
  echo "[Warn] 实时抓帧失败，尝试检查网络与摄像头状态..."
  exit 1
fi

echo "[3/3] VLM 场景理解与 TTS 播报..."
bash "${SCRIPTS}/vlm_see.sh"

echo "=================================================="
echo "                 联调完成"
echo "=================================================="
