#!/bin/bash
# adb-safe: no apt/systemctl — mediamtx + frame cache + benchmark only.
export SKIP_APT=1
export AGENT_ROOT="${AGENT_ROOT:-/userdata/agent}"
export P4_ROOT="${P4_ROOT:-/userdata/p4}"
exec bash "${AGENT_ROOT}/scripts/setup_camera_lowlatency_env.sh"
