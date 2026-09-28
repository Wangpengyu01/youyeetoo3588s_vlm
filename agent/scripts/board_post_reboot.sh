#!/bin/bash
# After hard reboot on board (run as root): full stack + fix bad cache + verify.
set -euo pipefail
AGENT="${AGENT_ROOT:-/userdata/agent}"
P4="${P4_ROOT:-/userdata/p4}"

rm -f "${AGENT}/run/mediamtx_latest.jpg"
echo "[post-reboot] removed stale mediamtx_latest.jpg if any"

cp -f "${AGENT}/systemd/r1-orchestrator.service" /etc/systemd/system/ 2>/dev/null || true
cp -f "${P4}/systemd/r1-mediamtx.service" /etc/systemd/system/ 2>/dev/null || true
cp -f "${AGENT}/systemd/r1-mediamtx-frame.service" /etc/systemd/system/ 2>/dev/null || true
systemctl daemon-reload
systemctl enable r1-mediamtx.service r1-mediamtx-frame.service 2>/dev/null || true

bash "${AGENT}/scripts/start_xiaolan_stack.sh"
export SKIP_APT=1
bash "${AGENT}/scripts/setup_camera_lowlatency_adb.sh"

echo "[post-reboot] cache file:"
ls -la "${AGENT}/run/mediamtx_latest.jpg" 2>/dev/null || echo "(not yet — wait frame daemon)"
echo "[post-reboot] orchestrator:"; systemctl is-active r1-orchestrator 2>/dev/null || pgrep -af xiaolan_cli
