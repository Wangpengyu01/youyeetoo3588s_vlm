#!/bin/bash
# Switch board to P5b unified vlm_daemon (disable llm_daemon). Run as root on board.
set -euo pipefail

AGENT_ROOT="${AGENT_ROOT:-/userdata/agent}"
BIN="${AGENT_ROOT}/bin/vlm_daemon"

if [[ ! -x "${BIN}" ]]; then
  echo "[p5b] missing ${BIN} — build on 196: agent/scripts/build_vlm_daemon_196.sh" >&2
  exit 1
fi

install -m 644 "${AGENT_ROOT}/systemd/r1-vlm-daemon.service" /etc/systemd/system/
systemctl daemon-reload

pkill -f 'xiaolan_cli serve' 2>/dev/null || true
systemctl stop r1-orchestrator.service 2>/dev/null || true

if systemctl is-active --quiet r1-llm-daemon.service 2>/dev/null; then
  echo "[p5b] stopping r1-llm-daemon (pkill, no restart loop via adb)..."
  pkill -TERM -f '/userdata/agent/bin/llm_daemon' 2>/dev/null || true
  sleep 2
  pkill -KILL -f '/userdata/agent/bin/llm_daemon' 2>/dev/null || true
  systemctl disable r1-llm-daemon.service 2>/dev/null || true
  systemctl stop r1-llm-daemon.service 2>/dev/null || true
fi

rm -f /tmp/r1-llm.sock
systemctl enable r1-vlm-daemon.service
if ! [[ -s "${BIN}" ]]; then
  echo "[p5b] ${BIN} is missing or 0 bytes — adb push agent/bin/vlm_daemon first" >&2
  exit 1
fi
chmod 755 "${BIN}" 2>/dev/null || true

# Six-tuple load can take several minutes; do not block on systemctl start (ExecStartPost waits for sock).
systemctl start r1-vlm-daemon.service &
_start_pid=$!

for _ in $(seq 1 300); do
  [[ -S /tmp/r1-vlm.sock ]] && break
  if ! systemctl is-active --quiet r1-vlm-daemon.service 2>/dev/null; then
    if ! pgrep -f '/userdata/agent/bin/vlm_daemon' >/dev/null 2>&1; then
      echo "[p5b] vlm_daemon exited — tail ${AGENT_ROOT}/logs/vlm_daemon.log" >&2
      tail -30 "${AGENT_ROOT}/logs/vlm_daemon.log" 2>/dev/null || true
      wait "${_start_pid}" 2>/dev/null || true
      exit 1
    fi
  fi
  sleep 2
done
wait "${_start_pid}" 2>/dev/null || true

if [[ ! -S /tmp/r1-vlm.sock ]]; then
  echo "[p5b] socket timeout — check ${AGENT_ROOT}/logs/vlm_daemon.log" >&2
  exit 1
fi
chmod 777 /tmp/r1-vlm.sock 2>/dev/null || true

# Point orchestrator at unified socket
CFG="${AGENT_ROOT}/config/agent.yaml"
if grep -q '^socket_path:' "${CFG}"; then
  sed -i 's|^socket_path:.*|socket_path: /tmp/r1-vlm.sock|' "${CFG}"
fi
if grep -q '^inference:' "${CFG}"; then
  sed -i '/^inference:/,/^[^ #]/ s/^  backend:.*/  backend: vlm_daemon/' "${CFG}"
fi
bash "${AGENT_ROOT}/scripts/repair_agent_yaml_backends.sh" "${CFG}" 2>/dev/null || true

systemctl enable r1-orchestrator.service r1-webui.service 2>/dev/null || true
timeout 30 systemctl start r1-orchestrator.service || true
timeout 15 systemctl start r1-webui.service 2>/dev/null || true

echo "[p5b] active:"
systemctl is-active r1-vlm-daemon r1-orchestrator r1-webui || true
echo "[p5b] test: python3 ${AGENT_ROOT}/scripts/llm_client.py --socket /tmp/r1-vlm.sock --ping"
