#!/bin/bash
# Wait until RK1828 firmware is fully booted, DDR initialized, and device ready.
set -eu
TRIES="${1:-60}"

echo "[RKNN] waiting for RK1828 firmware boot and memory ready..." >&2

for i in $(seq 1 "${TRIES}"); do
  # 1. Make sure pcie_upgrade_tool is not actively flashing/resetting the chip
  if pgrep -f pcie_upgrade_tool >/dev/null 2>&1; then
    echo "[RKNN] pcie_upgrade_tool still running... (${i}/${TRIES})" >&2
    sleep 2
    continue
  fi

  # 2. Query rknn-smi
  INFO=$(rknn-smi info 2>&1 || true)

  # 3. Check for Online AND valid memory reporting (meaning NPU OS is running and queryable)
  if echo "${INFO}" | grep -q "Online"; then
    if echo "${INFO}" | grep -E "[0-9]+ */ *5120" >/dev/null 2>&1; then
      echo "[RKNN] ready (${i}) - RK1828 firmware and memory online"
      sleep 3
      exit 0
    fi
  fi

  echo "[RKNN] waiting for 1828 Online & Memory Init... (${i}/${TRIES})" >&2
  sleep 2
done

echo "[RKNN] timeout waiting for RK1828" >&2
exit 1
