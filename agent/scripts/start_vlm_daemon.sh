#!/bin/bash
# Start vlm_daemon (M1: LLM session + /tmp/r1-vlm.sock). Replaces llm_daemon when P5b lands.
set -euo pipefail

AGENT_ROOT="${AGENT_ROOT:-/userdata/agent}"
BIN="${AGENT_ROOT}/bin/vlm_daemon"
SOCK="/tmp/r1-vlm.sock"
MODEL_DIR="${LLM_MODEL_DIR:-/userdata/models/InternVL3_5-4B}"
LOG="${AGENT_ROOT}/logs/vlm_daemon.log"
PIDFILE="${AGENT_ROOT}/run/vlm_daemon.pid"

mkdir -p "${AGENT_ROOT}/logs" "${AGENT_ROOT}/run"

if [[ ! -x "${BIN}" ]]; then
  echo "[start] missing ${BIN} — see agent/docs/BUILD_LINUX.md § vlm_daemon" >&2
  exit 1
fi

if [[ -f "${PIDFILE}" ]] && kill -0 "$(cat "${PIDFILE}")" 2>/dev/null; then
  echo "[start] already running pid=$(cat "${PIDFILE}")"
  exit 0
fi

rm -f "${SOCK}"

nohup "${BIN}" \
  "${MODEL_DIR}/llm_InternVL3_5-4B.rknn" \
  "${MODEL_DIR}/llm_InternVL3_5-4B.weight" \
  "${MODEL_DIR}/InternVL3_5-4B.tokenizer.gguf" \
  "${MODEL_DIR}/InternVL3_5-4B.embed.bin" \
  1024 64 0xff \
  >>"${LOG}" 2>&1 &

echo $! >"${PIDFILE}"
echo "[start] vlm_daemon pid=$(cat "${PIDFILE}") log=${LOG} sock=${SOCK}"
