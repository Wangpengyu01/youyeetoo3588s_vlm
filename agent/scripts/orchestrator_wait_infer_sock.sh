#!/bin/bash
# ExecStartPre: wait for P5b vlm_daemon or legacy llm_daemon socket.
set -euo pipefail
AGENT_ROOT="${AGENT_ROOT:-/userdata/agent}"
if systemctl is-enabled --quiet r1-vlm-daemon.service 2>/dev/null; then
  exec /bin/bash "${AGENT_ROOT}/scripts/wait_vlm_sock.sh" /tmp/r1-vlm.sock 240
fi
exec /bin/bash "${AGENT_ROOT}/scripts/fix_llm_sock_perms.sh" /tmp/r1-llm.sock 90
