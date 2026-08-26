#!/bin/bash
# Grab one JPEG frame from RTSP (MPP hw decode, TCP)
set -euo pipefail
source "$(dirname "$0")/p4_env.sh"

OUT="${1:-${LATEST_FRAME}}"
TMP="${OUT}.part"
WAIT_LOOPS="${GRAB_WAIT_LOOPS:-40}"
TIMEOUT_SEC="${GRAB_TIMEOUT_SEC:-8}"

build_pipe() {
  local codec="$1"
  case "${codec}" in
    h265|hevc)
      echo "rtspsrc location=\"${RTSP_URL}\" protocols=${RTSP_PROTOCOLS} latency=${RTSP_LATENCY_MS} drop-on-latency=true ! rtph265depay ! h265parse ! mppvideodec ! videoconvert ! videoscale ! video/x-raw,width=${STREAM_WIDTH},height=${STREAM_HEIGHT} ! jpegenc quality=90 ! filesink location=\"${TMP}\" sync=false async=false"
      ;;
    h264|*)
      echo "rtspsrc location=\"${RTSP_URL}\" protocols=${RTSP_PROTOCOLS} latency=${RTSP_LATENCY_MS} drop-on-latency=true ! rtph264depay ! h264parse ! mppvideodec ! videoconvert ! videoscale ! video/x-raw,width=${STREAM_WIDTH},height=${STREAM_HEIGHT} ! jpegenc quality=90 ! filesink location=\"${TMP}\" sync=false async=false"
      ;;
  esac
}

grab_codec() {
  local codec="$1"
  rm -f "${TMP}"
  local pipe
  pipe=$(build_pipe "${codec}")
  echo "[RTSP] 取帧 ${RTSP_URL} (${codec} ${STREAM_WIDTH}x${STREAM_HEIGHT})" >&2

  timeout "${TIMEOUT_SEC}" bash -c "eval gst-launch-1.0 -e ${pipe}" >/tmp/rtsp_grab.log 2>&1 &
  local gpid=$!
  local i=0
  while [ "${i}" -lt "${WAIT_LOOPS}" ]; do
    if [ -s "${TMP}" ]; then
      sleep 0.25
      kill "${gpid}" 2>/dev/null || true
      wait "${gpid}" 2>/dev/null || true
      mv -f "${TMP}" "${OUT}"
      echo "[RTSP] 已保存 ${OUT} ($(wc -c < "${OUT}") bytes)" >&2
      return 0
    fi
    if ! kill -0 "${gpid}" 2>/dev/null; then
      break
    fi
    sleep 0.25
    i=$((i + 1))
  done
  kill "${gpid}" 2>/dev/null || true
  wait "${gpid}" 2>/dev/null || true
  tail -15 /tmp/rtsp_grab.log >&2 || true
  return 1
}

if grab_codec "${RTSP_CODEC}"; then
  exit 0
fi

if [ "${RTSP_CODEC}" = "h264" ]; then
  echo "[RTSP] h264 失败，尝试 h265..." >&2
  grab_codec h265
else
  exit 1
fi
