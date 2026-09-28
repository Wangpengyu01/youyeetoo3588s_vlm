#!/bin/bash
# Enable mediamtx + frame cache daemon at boot (fresh mediamtx_latest.jpg for VLM).
# adb-safe: never block on systemctl restart — use enable + timed start + nohup fallback.
# Run on board as root: bash /userdata/agent/scripts/install_mediamtx_frame_boot.sh
set -euo pipefail
AGENT="${AGENT_ROOT:-/userdata/agent}"
P4="${P4_ROOT:-/userdata/p4}"

if [[ ! -x "${P4}/bin/mediamtx" ]]; then
  echo "[frame-boot] missing ${P4}/bin/mediamtx — run p4/scripts/deploy_mediamtx.sh first" >&2
  exit 1
fi

chmod +x "${P4}/scripts/mediamtx_gen_config.sh" "${AGENT}/scripts/mediamtx_rtsp_frame_daemon.sh" 2>/dev/null || true
sed -i 's/\r$//' "${AGENT}/scripts/mediamtx_rtsp_frame_daemon.sh" 2>/dev/null || true
mkdir -p "${AGENT}/run" "${AGENT}/logs" "${P4}/logs"

bash "${P4}/scripts/mediamtx_gen_config.sh"

install -m 644 "${P4}/systemd/r1-mediamtx.service" /etc/systemd/system/
install -m 644 "${AGENT}/systemd/r1-mediamtx-frame.service" /etc/systemd/system/
systemctl daemon-reload

systemctl enable r1-p4-eth.service 2>/dev/null || true
systemctl enable r1-mediamtx.service r1-mediamtx-frame.service
echo "[frame-boot] systemd units enabled (survives reboot)"

# adb shell: systemctl start/restart often blocks 20s+ — use nohup for immediate bring-up.
# Reboot still uses enabled systemd units.
start_mediamtx_nohup() {
  if pgrep -x mediamtx >/dev/null; then
    echo "[frame-boot] mediamtx already running"
    return 0
  fi
  pkill -x mediamtx 2>/dev/null || true
  sleep 1
  nohup "${P4}/bin/mediamtx" "${P4}/config/mediamtx.yml" >>"${P4}/logs/mediamtx.log" 2>&1 &
  echo "[frame-boot] mediamtx nohup pid=$!"
}

start_frame_daemon_nohup() {
  if pgrep -f mediamtx_rtsp_frame_daemon.sh >/dev/null; then
    echo "[frame-boot] frame daemon already running"
    return 0
  fi
  pkill -f mediamtx_rtsp_frame_daemon.sh 2>/dev/null || true
  sleep 1
  nohup bash "${AGENT}/scripts/mediamtx_rtsp_frame_daemon.sh" >>"${AGENT}/logs/mediamtx_frame_daemon.log" 2>&1 &
  echo "[frame-boot] frame daemon nohup pid=$!"
}

if [[ "${USE_SYSTEMCTL_START:-0}" == "1" ]]; then
  timeout 8 systemctl start r1-p4-eth.service 2>/dev/null || true
  timeout 8 systemctl start r1-mediamtx.service 2>/dev/null || start_mediamtx_nohup
  sleep 2
  timeout 8 systemctl start r1-mediamtx-frame.service 2>/dev/null || start_frame_daemon_nohup
else
  echo "[frame-boot] nohup bring-up (set USE_SYSTEMCTL_START=1 on SSH to prefer systemd)"
  start_mediamtx_nohup
  sleep 2
  start_frame_daemon_nohup
fi
sleep 4

if [[ -f "${AGENT}/run/mediamtx_latest.jpg" ]]; then
  ls -la "${AGENT}/run/mediamtx_latest.jpg"
  file "${AGENT}/run/mediamtx_latest.jpg" 2>/dev/null || true
else
  echo "[frame-boot] WARN: cache not yet — tail ${AGENT}/logs/mediamtx_frame_daemon.log" >&2
  tail -5 "${AGENT}/logs/mediamtx_frame_daemon.log" 2>/dev/null || true
fi

echo "[frame-boot] active:" systemctl is-active r1-mediamtx.service r1-mediamtx-frame.service 2>/dev/null || true
pgrep -x mediamtx >/dev/null && echo "[frame-boot] mediamtx pid ok" || echo "[frame-boot] mediamtx not in pgrep"
pgrep -f mediamtx_rtsp_frame_daemon >/dev/null && echo "[frame-boot] frame daemon pid ok" || echo "[frame-boot] frame daemon not in pgrep"
echo "[frame-boot] done — reboot will auto-start via systemd enabled units"
