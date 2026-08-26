#!/bin/bash
# Push agent/ to board (scripts only until binaries exist)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BOARD="${BOARD:-/userdata/agent}"

echo "[deploy] ${ROOT} -> ${BOARD}"
adb shell "mkdir -p ${BOARD}"
adb push "${ROOT}/README.md" "${BOARD}/"
adb push "${ROOT}/docs/" "${BOARD}/docs/"
adb push "${ROOT}/scripts/" "${BOARD}/scripts/" 2>/dev/null || true
echo "[deploy] done — binaries not yet built"
