#!/bin/bash
set -u

IMAGE="${1:-/userdata/agent/run/latest_vlm.jpg}"
PROMPT="${2:-请用一句话详细描述画面中看到的物品}"

export P4_MAX_IDLE_MB=1500

# 1. Stop llm_daemon cooperatively (avoid D-state systemctl on RK3588)
AGENT_ROOT="${AGENT_ROOT:-/userdata/agent}"
bash "${AGENT_ROOT}/scripts/cooperative_stop_llm.sh" || true

# 2. Run board VLM as root
RESULT=""
if [ -f "/userdata/p4/scripts/vlm_see.sh" ]; then
    RESULT=$(sudo P4_MAX_IDLE_MB=1500 bash /userdata/p4/scripts/vlm_see.sh "${IMAGE}" "${PROMPT}" 2>/tmp/vlm_err.log || true)
fi

# 3. Restart llm_daemon (wait for socket in background-friendly way)
bash "${AGENT_ROOT}/scripts/cooperative_start_llm.sh" /tmp/r1-llm.sock 90 &

# 4. Extract clean caption
CLEAN_CAPTION=$(echo "${RESULT}" | grep -v '^\[' | sed '/^[[:space:]]*$/d' | tail -1)

if [ -n "${CLEAN_CAPTION}" ]; then
    echo "${CLEAN_CAPTION}"
else
    echo "画面中未识别到具体物品。"
fi