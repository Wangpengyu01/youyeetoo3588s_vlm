#!/bin/bash
# Copy of agent/scripts/recover_install_adb.sh — push with: adb push recover_install_adb.sh /userdata/agent/scripts/
if grep -q $'\r' "$0" 2>/dev/null; then
  sed -i 's/\r$//' "$0" 2>/dev/null || true
  exec /bin/bash "$0" "$@"
fi
set -eu
AGENT="${AGENT_ROOT:-/userdata/agent}"
P4="${P4_ROOT:-/userdata/p4}"

echo "[recover-adb] reset failed / reload"
systemctl reset-failed 2>/dev/null || true
systemctl daemon-reload 2>/dev/null || true

install -d "${AGENT}/logs" "${AGENT}/run" "${P4}/config" "${P4}/logs"

chmod +x "${P4}/scripts/"*.sh "${AGENT}/scripts/"*.sh 2>/dev/null || true
sed -i 's/\r$//' "${P4}/scripts/"*.sh "${AGENT}/scripts/"*.sh 2>/dev/null || true

install -m 644 "${AGENT}/systemd/r1-orchestrator.service" /etc/systemd/system/ 2>/dev/null || true
install -m 644 "${AGENT}/systemd/r1-webui.service" /etc/systemd/system/ 2>/dev/null || true
install -m 644 "${AGENT}/systemd/r1-mediamtx-frame.service" /etc/systemd/system/ 2>/dev/null || true
install -m 644 "${AGENT}/systemd/r1-p4-eth.service" /etc/systemd/system/ 2>/dev/null || true
[[ -f "${AGENT}/systemd/r1-vlm-daemon.service" ]] && install -m 644 "${AGENT}/systemd/r1-vlm-daemon.service" /etc/systemd/system/
[[ -f "${P4}/systemd/r1-mediamtx.service" ]] && install -m 644 "${P4}/systemd/r1-mediamtx.service" /etc/systemd/system/
systemctl daemon-reload

[[ -x "${P4}/bin/mediamtx" ]] && bash "${P4}/scripts/mediamtx_gen_config.sh" || true

start_unit() {
  u="$1"
  systemctl enable "$u" 2>/dev/null || true
  echo "[recover-adb] start $u ..."
  timeout 28 systemctl start "$u" 2>/dev/null || systemctl reset-failed "$u" 2>/dev/null || true
  echo "[recover-adb] $u: $(systemctl is-active "$u" 2>/dev/null || echo ?)"
}

start_unit r1-p4-eth.service
sleep 2
start_unit r1-mediamtx.service
start_unit r1-mediamtx-frame.service

if [[ -x "${AGENT}/bin/vlm_daemon" ]]; then
  systemctl disable r1-llm-daemon.service 2>/dev/null || true
  start_unit r1-vlm-daemon.service
  i=0
  while [ "$i" -lt 180 ]; do
    [ -S /tmp/r1-vlm.sock ] && break
    i=$((i + 1))
    sleep 1
  done
  [ -S /tmp/r1-vlm.sock ] && chmod 777 /tmp/r1-vlm.sock 2>/dev/null || true
fi

if [ -S /tmp/r1-vlm.sock ] || [ -S /tmp/r1-llm.sock ]; then
  start_unit r1-orchestrator.service
  start_unit r1-webui.service
fi

systemctl is-active r1-p4-eth r1-mediamtx r1-mediamtx-frame r1-vlm-daemon r1-orchestrator r1-webui 2>/dev/null || true
