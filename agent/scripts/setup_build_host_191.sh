#!/bin/bash
# One-time on gp@192.168.100.191: unpack RK1828 SDK for vlm_daemon cross-build.
# Usage: bash setup_build_host_191.sh
set -eu

SDK_DIR="${HOME}/project/1828sdk"
TAR="${SDK_DIR}/RK1820_1828_RELEASE_V1.0.5B10.tar.gz"
OUT="${SDK_DIR}/extract"

if [ ! -f "${TAR}" ]; then
  echo "Missing ${TAR}" >&2
  exit 1
fi

mkdir -p "${OUT}"
if [ ! -f "${OUT}/.extracted" ]; then
  echo "[setup] extracting SDK (may take several minutes)..."
  tar -xzf "${TAR}" -C "${OUT}"
  touch "${OUT}/.extracted"
fi

echo "[setup] searching demos..."
find "${OUT}" -name 'rknn_internvl3_demo.cpp' -o -name 'rknn_internvl3_demo' 2>/dev/null | head -10
find "${OUT}" -name 'rknn3_session_test_demo' -type d 2>/dev/null | head -5

if ! command -v aarch64-linux-gnu-g++ >/dev/null 2>&1; then
  echo "[setup] install cross toolchain: sudo apt install -y gcc-aarch64-linux-gnu g++-aarch64-linux-gnu"
fi
