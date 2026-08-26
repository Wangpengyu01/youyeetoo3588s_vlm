#!/bin/bash
# One-shot voice chat launcher (Phase D)
set -euo pipefail
AGENT_ROOT="${AGENT_ROOT:-/userdata/agent}"
bash "${AGENT_ROOT}/scripts/start_llm_daemon.sh" 2>/dev/null || true
exec bash "${AGENT_ROOT}/scripts/start_orchestrator.sh"
