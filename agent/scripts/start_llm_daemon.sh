#!/bin/bash
# Start InternVL3.5-4B LLM-only daemon on board (Phase A)
set -euo pipefail

AGENT_ROOT="${AGENT_ROOT:-/userdata/agent}"
BIN="${AGENT_ROOT}/bin/llm_daemon"
SOCK="/tmp/r1-llm.sock"
MODEL_DIR="${LLM_MODEL_DIR:-/userdata/models/InternVL3_5-4B}"
LOG="${AGENT_ROOT}/logs/llm_daemon.log"
PIDFILE="${AGENT_ROOT}/run/llm_daemon.pid"

mkdir -p "${AGENT_ROOT}/logs" "${AGENT_ROOT}/run"

if [[ ! -x "${BIN}" ]]; then
  echo "[start] missing ${BIN} — compile on Linux VM per agent/docs/BUILD_LINUX.md" >&2
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
echo "[start] llm_daemon pid=$(cat "${PIDFILE}") log=${LOG} sock=${SOCK}"

for _ in $(seq 1 60); do
  if [[ -S "${SOCK}" ]]; then
    chmod 777 "${SOCK}" 2>/dev/null || true
    echo "[start] socket ready"
    exit 0
  fi
  sleep 1
done

echo "[start] timeout waiting for socket — check ${LOG}" >&2
exit 1
