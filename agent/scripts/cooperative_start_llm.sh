#!/bin/bash
# Start llm_daemon after VLM — no systemctl (adb hang). Uses start_llm_daemon.sh only.
set -eu

SOCK="${1:-/tmp/r1-llm.sock}"
MAX_WAIT="${2:-90}"
AGENT_ROOT="${AGENT_ROOT:-/userdata/agent}"

if pgrep -f '/userdata/agent/bin/llm_daemon' >/dev/null 2>&1; then
  echo "[coop-start] already running"
  exit 0
fi

bash "${AGENT_ROOT}/scripts/start_llm_daemon.sh"

for i in $(seq 1 "${MAX_WAIT}"); do
  if [[ -S "${SOCK}" ]]; then
    echo "[coop-start] socket ready ${i}s"
    exit 0
  fi
  sleep 1
done

echo "[coop-start] WARN: socket not ready after ${MAX_WAIT}s" >&2
exit 1
