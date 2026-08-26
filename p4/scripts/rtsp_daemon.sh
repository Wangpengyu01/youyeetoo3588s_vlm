#!/bin/bash
# Background: keep overwriting latest RTSP frame (leaky decode)
set -euo pipefail
source "$(dirname "$0")/p4_env.sh"

PIDFILE=/tmp/rtsp_daemon.pid
LOG=/tmp/rtsp_daemon.log

stop_daemon() {
  if [ -f "${PIDFILE}" ]; then
    kill "$(cat "${PIDFILE}")" 2>/dev/null || true
    rm -f "${PIDFILE}"
  fi
  pkill -f "rtsp_daemon_loop" 2>/dev/null || true
}

case "${1:-start}" in
  stop)
    stop_daemon
    echo "[RTSP-D] stopped"
    exit 0
    ;;
  status)
    if [ -f "${PIDFILE}" ] && kill -0 "$(cat "${PIDFILE}")" 2>/dev/null; then
      echo "[RTSP-D] running pid=$(cat "${PIDFILE}")"
      ls -lh "${LATEST_FRAME}" 2>/dev/null || true
    else
      echo "[RTSP-D] not running"
    fi
    exit 0
    ;;
esac

stop_daemon

(
  echo $$ > "${PIDFILE}"
  while true; do
    RTSP_CODEC="${RTSP_CODEC}" bash "${SCRIPTS}/rtsp_grab_once.sh" "${LATEST_FRAME}" >>"${LOG}" 2>&1 || sleep 1
    sleep 0.2
  done
) &
disown
echo "[RTSP-D] started → ${LATEST_FRAME} (log ${LOG})"
