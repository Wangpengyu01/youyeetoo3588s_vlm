#!/bin/bash
# Start Phase B orchestrator (VAD + state machine) on board
set -euo pipefail

AGENT_ROOT="${AGENT_ROOT:-/userdata/agent}"
PIDFILE="${AGENT_ROOT}/run/orchestrator.pid"
LOG="${AGENT_ROOT}/logs/orchestrator.log"

source /userdata/voice/scripts/voice_hw_board.sh 2>/dev/null || true
export PYTHONPATH="${AGENT_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
export LD_LIBRARY_PATH="/userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"

mkdir -p "${AGENT_ROOT}/run" "${AGENT_ROOT}/logs"

if [[ -f "${PIDFILE}" ]] && kill -0 "$(cat "${PIDFILE}")" 2>/dev/null; then
  echo "[start] orchestrator already running pid=$(cat "${PIDFILE}")"
  exit 0
fi

if [[ ! -S /tmp/r1-llm.sock ]]; then
  echo "[start] llm_daemon not running — starting..."
  bash "${AGENT_ROOT}/scripts/start_llm_daemon.sh" || true
fi

nohup python3 -m orchestrator.main \
  --config "${AGENT_ROOT}/config/agent.yaml" \
  --agent-root "${AGENT_ROOT}" \
  >>"${LOG}" 2>&1 &

echo $! >"${PIDFILE}"
echo "[start] orchestrator pid=$(cat "${PIDFILE}") log=${LOG}"
echo "[start] speak to onboard mic; watch: tail -f ${LOG}"
