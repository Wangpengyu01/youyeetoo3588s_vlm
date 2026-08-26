#!/bin/bash
# Wait until RK1828 reports Online (after rknn3.service).
set -eu
TRIES="${1:-45}"
for i in $(seq 1 "${TRIES}"); do
  if rknn-smi info 2>&1 | grep -q "Online"; then
    echo "[RKNN] ready (${i})"
    exit 0
  fi
  echo "[RKNN] waiting for 1828 Online... (${i}/${TRIES})" >&2
  sleep 2
done
echo "[RKNN] timeout waiting for RK1828" >&2
exit 1
