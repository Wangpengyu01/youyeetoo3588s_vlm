#!/bin/bash
# Post-push start for demo recovery via adb (avoid 8min block + reset failed units).
if grep -q $'\r' "$0" 2>/dev/null; then
  sed -i 's/\r$//' "$0" 2>/dev/null || sed -i '' 's/\r$//' "$0" 2>/dev/null || true
  exec /bin/bash "$0" "$@"
fi
set -eu
AGENT="${AGENT_ROOT:-/userdata/agent}"
P4="${P4_ROOT:-/userdata/p4}"

echo "[recover-adb] reset failed / reload"
systemctl reset-failed 2>/dev/null || true
systemctl daemon-reload 2>/dev/null || true

install -d "${AGENT}/logs" "${AGENT}/run" "${P4}/config" "${P4}/logs"

if [[ ! -f "${P4}/config/rtsp.env" ]]; then
  if [[ -f "${P4}/config/rtsp.env.example" ]]; then
    cp "${P4}/config/rtsp.env.example" "${P4}/config/rtsp.env"
    echo "[recover-adb] created rtsp.env from example"
  else
    echo "RTSP_URL=rtsp://192.168.2.169:554/stream_2" >"${P4}/config/rtsp.env"
  fi
fi

chmod +x "${P4}/scripts/"*.sh "${AGENT}/scripts/"*.sh 2>/dev/null || true
sed -i 's/\r$//' "${P4}/scripts/"*.sh "${AGENT}/scripts/"*.sh 2>/dev/null || true

install -m 644 "${AGENT}/systemd/r1-orchestrator.service" /etc/systemd/system/ 2>/dev/null || true
install -m 644 "${AGENT}/systemd/r1-webui.service" /etc/systemd/system/ 2>/dev/null || true
install -m 644 "${AGENT}/systemd/r1-mediamtx-frame.service" /etc/systemd/system/ 2>/dev/null || true
install -m 644 "${AGENT}/systemd/r1-p4-eth.service" /etc/systemd/system/ 2>/dev/null || true
[[ -f "${AGENT}/systemd/r1-vlm-daemon.service" ]] && install -m 644 "${AGENT}/systemd/r1-vlm-daemon.service" /etc/systemd/system/
[[ -f "${P4}/systemd/r1-mediamtx.service" ]] && install -m 644 "${P4}/systemd/r1-mediamtx.service" /etc/systemd/system/
systemctl daemon-reload

if [[ -x "${P4}/bin/mediamtx" ]]; then
  bash "${P4}/scripts/mediamtx_gen_config.sh" || true
fi

start_unit() {
  u="$1"
  systemctl enable "$u" 2>/dev/null || true
  echo "[recover-adb] start $u ..."
  if timeout 28 systemctl start "$u" 2>/dev/null; then
    echo "[recover-adb] $u: $(systemctl is-active "$u" 2>/dev/null || echo ?)"
  else
    echo "[recover-adb] WARN: $u start slow/fail" >&2
    systemctl reset-failed "$u" 2>/dev/null || true
  fi
}

start_unit r1-p4-eth.service
sleep 2
start_unit r1-mediamtx.service
start_unit r1-mediamtx-frame.service

if [[ -x "${AGENT}/bin/vlm_daemon" ]] && [[ -s "${AGENT}/bin/vlm_daemon" ]]; then
  systemctl disable r1-llm-daemon.service 2>/dev/null || true
  if [[ ! -f /userdata/models/InternVL3_5-4B/vision_InternVL3_5-4B.rknn ]]; then
    echo "[recover-adb] WARN: InternVL models missing under /userdata/models/InternVL3_5-4B/" >&2
  fi
  start_unit r1-vlm-daemon.service
  echo "[recover-adb] waiting for /tmp/r1-vlm.sock (max 45s; use recover_nohup_adb.sh over adb)"
  i=0
  while [ "$i" -lt 45 ]; do
    [ -S /tmp/r1-vlm.sock ] && break
    i=$((i + 1))
    sleep 1
  done
  [ -S /tmp/r1-vlm.sock ] && chmod 777 /tmp/r1-vlm.sock 2>/dev/null || true
fi

if [ -S /tmp/r1-vlm.sock ] || [ -S /tmp/r1-llm.sock ]; then
  systemctl enable r1-orchestrator.service r1-webui.service 2>/dev/null || true
  echo "[recover-adb] start r1-orchestrator (--ignore-dependencies; vlm may be nohup not systemd active)"
  timeout 45 systemctl start --ignore-dependencies r1-orchestrator.service 2>/dev/null || true
  timeout 25 systemctl start r1-webui.service 2>/dev/null || \
    pgrep -f 'http.server.*8766' >/dev/null || \
    nohup python3 -m http.server 8766 --bind 0.0.0.0 --directory "${AGENT}/ui" >>"${AGENT}/logs/webui.log" 2>&1 &
else
  echo "[recover-adb] infer socket not ready — check vlm_daemon.log or reboot" >&2
fi

echo "[recover-adb] status:"
systemctl is-active r1-p4-eth r1-mediamtx r1-mediamtx-frame r1-vlm-daemon r1-orchestrator r1-webui 2>/dev/null || true
