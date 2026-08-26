#!/bin/bash
# Wait until rknn3 service and RK1828 report Online after boot
# Note: do NOT use pipefail here — rknn-smi may exit non-zero while still printing "Online"
set -eu

TRIES="${1:-45}"
for i in $(seq 1 "${TRIES}"); do
  if rknn-smi info 2>&1 | grep -q "Online"; then
    echo "[RKNN] ready (${i})"
    exit 0
  fi
  echo "[RKNN] 等待 1828 Online... (${i}/${TRIES})" >&2
  sleep 2
done
echo "[RKNN] timeout waiting for RK1828" >&2
exit 1
