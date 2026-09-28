#!/bin/bash
# Boot 小揽：P5b vlm_daemon 或 llm_daemon + orchestrator + WebUI.
set -euo pipefail

AGENT_ROOT="${AGENT_ROOT:-/userdata/agent}"

if ! command -v systemctl >/dev/null 2>&1; then
  echo "[xiaolan] no systemd — use start_vlm_daemon.sh or start_llm_daemon.sh" >&2
  exit 1
fi

systemctl start r1-p4-eth.service 2>/dev/null || true

SOCK="/tmp/r1-llm.sock"
if systemctl is-enabled --quiet r1-vlm-daemon.service 2>/dev/null; then
  systemctl disable r1-llm-daemon.service 2>/dev/null || true
  systemctl stop r1-llm-daemon.service 2>/dev/null || true
  systemctl start r1-vlm-daemon.service
  SOCK="/tmp/r1-vlm.sock"
  echo "[xiaolan] waiting for P5b vlm_daemon (six-tuple load, up to 8 min)..."
else
  systemctl start r1-llm-daemon.service
  echo "[xiaolan] waiting for llm_daemon socket..."
fi

if [[ "${SOCK}" == "/tmp/r1-vlm.sock" ]] && [[ -x "${AGENT_ROOT}/scripts/wait_vlm_sock.sh" ]]; then
  bash "${AGENT_ROOT}/scripts/wait_vlm_sock.sh" "${SOCK}" 240
else
  for _ in $(seq 1 240); do
    [[ -S "${SOCK}" ]] && break
    sleep 2
  done
fi

if [[ ! -S "${SOCK}" ]]; then
  echo "[xiaolan] WARN: ${SOCK} not ready — tail ${AGENT_ROOT}/logs/vlm_daemon.log or llm_daemon.log" >&2
  exit 1
fi

chmod 777 "${SOCK}" 2>/dev/null || true

P4="${P4_ROOT:-/userdata/p4}"
if [[ -x "${P4}/bin/mediamtx" ]]; then
  systemctl start r1-mediamtx.service 2>/dev/null || {
    bash "${P4}/scripts/mediamtx_gen_config.sh" 2>/dev/null || true
    pgrep -x mediamtx >/dev/null || nohup "${P4}/bin/mediamtx" "${P4}/config/mediamtx.yml" >>"${P4}/logs/mediamtx.log" 2>&1 &
    sleep 2
  }
  systemctl start r1-mediamtx-frame.service 2>/dev/null || {
    pkill -f mediamtx_rtsp_frame_daemon.sh 2>/dev/null || true
    nohup bash "${AGENT_ROOT}/scripts/mediamtx_rtsp_frame_daemon.sh" >>"${AGENT_ROOT}/logs/mediamtx_frame_daemon.log" 2>&1 &
  }
  sleep 3
fi

if ! timeout 45 systemctl start r1-orchestrator.service; then
  echo "[xiaolan] WARN: systemctl orchestrator failed — manual start:" >&2
  echo "  nohup python3 -m xiaolan_cli serve --config ${AGENT_ROOT}/config/agent.yaml --agent-root ${AGENT_ROOT}" >&2
  pkill -f 'xiaolan_cli serve' 2>/dev/null || true
  nohup python3 -m xiaolan_cli serve --config "${AGENT_ROOT}/config/agent.yaml" --agent-root "${AGENT_ROOT}" \
    >>"${AGENT_ROOT}/logs/orchestrator.log" 2>&1 &
fi
systemctl start r1-webui.service 2>/dev/null || true
systemctl --no-pager status r1-vlm-daemon r1-llm-daemon r1-orchestrator r1-webui --lines=2 2>/dev/null || true
echo "[xiaolan] socket=${SOCK}  WebUI http://127.0.0.1:8766  WS :8765"
