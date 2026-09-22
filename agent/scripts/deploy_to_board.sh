#!/bin/bash
# Push agent/ to board (scripts only until binaries exist)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BOARD="${BOARD:-/userdata/agent}"

echo "[deploy] Pushing agent to ${BOARD}..."
adb shell "mkdir -p ${BOARD}"
adb push "${ROOT}/." "${BOARD}/"
adb shell "chmod +x ${BOARD}/scripts/*.sh"

REPO_ROOT="$(cd "${ROOT}/.." && pwd)"
if [[ -d "${REPO_ROOT}/rknn_InternVLM_demo" ]]; then
  echo "[deploy] Pushing rknn_InternVLM_demo to /userdata/rknn_InternVLM_demo..."
  adb shell "mkdir -p /userdata/rknn_InternVLM_demo"
  adb push "${REPO_ROOT}/rknn_InternVLM_demo/." /userdata/rknn_InternVLM_demo/
  adb shell "chmod +x /userdata/rknn_InternVLM_demo/rknn_internvl3_demo"
fi

if [[ -d "${REPO_ROOT}/p4" ]]; then
  echo "[deploy] Pushing p4 to /userdata/p4..."
  adb shell "mkdir -p /userdata/p4"
  adb push "${REPO_ROOT}/p4/." /userdata/p4/
  adb shell "chmod +x /userdata/p4/scripts/*.sh /userdata/p4/scripts/*.py"
fi

echo "[deploy] Port forwarding (8766 -> 8766, 8765 -> 8765)..."
adb forward tcp:8766 tcp:8766
adb forward tcp:8765 tcp:8765
echo "[deploy] Deployment complete! Access Web UI at http://127.0.0.1:8766"
