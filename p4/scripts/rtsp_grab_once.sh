#!/bin/bash
# Grab one JPEG frame from RTSP (MPP hw decode, TCP; soft decode fallback)
set -euo pipefail
source "$(dirname "$0")/p4_env.sh"

OUT="${1:-${LATEST_FRAME}}"
TMP="${OUT}.part"
WAIT_LOOPS="${GRAB_WAIT_LOOPS:-40}"
TIMEOUT_SEC="${GRAB_TIMEOUT_SEC:-15}"
GRAB_LOG="${RTSP_GRAB_LOG:-/userdata/agent/logs/rtsp_grab.log}"

mkdir -p "$(dirname "${OUT}")" "$(dirname "${GRAB_LOG}")" 2>/dev/null || true
if ! touch "${GRAB_LOG}" 2>/dev/null; then
  GRAB_LOG="/dev/null"
fi

run_gst_mpp() {
  local codec="$1"
  case "${codec}" in
    h265|hevc)
      timeout "${TIMEOUT_SEC}" gst-launch-1.0 -e \
        rtspsrc location="${RTSP_URL}" protocols="${RTSP_PROTOCOLS}" latency="${RTSP_LATENCY_MS}" drop-on-latency=true ! \
        rtph265depay ! h265parse ! mppvideodec ! videoconvert ! videoscale ! \
        "video/x-raw,width=${STREAM_WIDTH},height=${STREAM_HEIGHT}" ! \
        jpegenc quality=90 ! filesink location="${TMP}" sync=false async=false
      ;;
    h264|*)
      timeout "${TIMEOUT_SEC}" gst-launch-1.0 -e \
        rtspsrc location="${RTSP_URL}" protocols="${RTSP_PROTOCOLS}" latency="${RTSP_LATENCY_MS}" drop-on-latency=true ! \
        rtph264depay ! h264parse ! mppvideodec ! videoconvert ! videoscale ! \
        "video/x-raw,width=${STREAM_WIDTH},height=${STREAM_HEIGHT}" ! \
        jpegenc quality=90 ! filesink location="${TMP}" sync=false async=false
      ;;
  esac
}

run_gst_soft() {
  timeout "${TIMEOUT_SEC}" gst-launch-1.0 -e \
    rtspsrc location="${RTSP_URL}" protocols="${RTSP_PROTOCOLS}" latency="${RTSP_LATENCY_MS}" drop-on-latency=true ! \
    decodebin ! videoconvert ! videoscale ! \
    "video/x-raw,width=${STREAM_WIDTH},height=${STREAM_HEIGHT}" ! \
    jpegenc quality=90 ! filesink location="${TMP}" sync=false async=false
}

wait_for_jpeg() {
  local gpid="$1"
  local i=0
  while [ "${i}" -lt "${WAIT_LOOPS}" ]; do
    if [ -s "${TMP}" ]; then
      sleep 0.3
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
  return 1
}

grab_with() {
  local label="$1"
  shift
  rm -f "${TMP}"
  echo "[RTSP] 取帧 ${RTSP_URL} (${label} ${STREAM_WIDTH}x${STREAM_HEIGHT})" >&2
  ( "$@" ) >>"${GRAB_LOG}" 2>&1 &
  local gpid=$!
  if wait_for_jpeg "${gpid}"; then
    return 0
  fi
  tail -8 "${GRAB_LOG}" 2>/dev/null >&2 || true
  return 1
}

grab_codec() {
  local codec="$1"
  grab_with "mpp-${codec}" run_gst_mpp "${codec}"
}

if grab_codec "${RTSP_CODEC}"; then
  exit 0
fi

if [ "${RTSP_CODEC}" = "h264" ]; then
  echo "[RTSP] h264 失败，尝试 h265..." >&2
  if grab_codec h265; then
    exit 0
  fi
fi

echo "[RTSP] MPP 失败，尝试 decodebin..." >&2
if grab_with "soft-decodebin" run_gst_soft; then
  exit 0
fi

exit 1
