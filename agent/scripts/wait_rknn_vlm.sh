#!/bin/bash
# Wait until RK1828 EP is ready for six-tuple VLM (stricter than wait_rknn.sh).
# Requires rknn-smi to show RK1828 + "used / 5120" memory line (not NA-only stub).
set -u

TRIES="${1:-120}"
STABLE="${2:-3}"
ready_streak=0

rknn_vlm_ready() {
  local out
  out="$(rknn-smi info 2>&1)" || true
  echo "${out}" | grep -q "Online" || return 1
  echo "${out}" | grep -qE 'RK1828|0003:31:00.0' || return 1
  echo "${out}" | grep -qE '/ 5120' || return 1
  echo "${out}" | grep -qE '\| [0-9]+ *\/ 5120' || return 1
  return 0
}

for i in $(seq 1 "${TRIES}"); do
  if rknn_vlm_ready; then
    ready_streak=$((ready_streak + 1))
    if [ "${ready_streak}" -ge "${STABLE}" ]; then
      echo "[RKNN-VLM] EP ready (${i}, stable ${STABLE}x)"
      sleep 5
      exit 0
    fi
  else
    ready_streak=0
  fi
  echo "[RKNN-VLM] waiting EP (RK1828 + /5120 mem)... (${i}/${TRIES})" >&2
  sleep 2
done

echo "[RKNN-VLM] EP not ready — try: systemctl restart rknn3.service && sleep 15" >&2
exit 1
