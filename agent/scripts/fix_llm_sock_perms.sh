#!/bin/bash
# Ensure youyeetoo orchestrator can connect to root-owned llm socket.
SOCK="${1:-/tmp/r1-llm.sock}"
TRIES="${2:-60}"
for _ in $(seq 1 "${TRIES}"); do
  if [[ -S "${SOCK}" ]]; then
    chmod 777 "${SOCK}"
    exit 0
  fi
  sleep 1
done
echo "[sock] timeout waiting for ${SOCK}" >&2
exit 1
