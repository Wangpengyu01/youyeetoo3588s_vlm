#!/bin/bash
# Wait for /tmp/r1-vlm.sock after boot (P5b load is slow).
SOCK="${1:-/tmp/r1-vlm.sock}"
TRIES="${2:-240}"
for i in $(seq 1 "${TRIES}"); do
  if [[ -S "${SOCK}" ]]; then
    chmod 777 "${SOCK}" 2>/dev/null || true
    echo "[vlm-sock] ready (${i})"
    exit 0
  fi
  sleep 2
done
echo "[vlm-sock] timeout ${SOCK} — tail /userdata/agent/logs/vlm_daemon.log" >&2
exit 1
