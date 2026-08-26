#!/bin/bash
# arecord with mic route keeper (3.5mm playback + onboard mic).
set -euo pipefail
source /userdata/voice/scripts/voice_env.sh

OUT="${1:?usage: mic_record.sh out.wav [seconds]}"
SEC="${2:-${RECORD_SEC:-5}}"
KEEP="${MIC_KEEP:-1}"
STOP=/tmp/mic_keep.stop

bash /userdata/voice/scripts/mic_arm.sh

if [ "${KEEP}" = "1" ]; then
  rm -f "${STOP}"
  (
    while [ ! -f "${STOP}" ]; do
      bash /userdata/voice/scripts/mic_setup.sh >/dev/null 2>&1 || true
      sleep 0.08
    done
  ) &
  KEEP_PID=$!
fi

arecord -q -D plughw:0,0 -f S16_LE -r "${RECORD_RATE}" -c "${RECORD_CHANNELS}" -d "${SEC}" "${OUT}"
RC=$?

if [ "${KEEP}" = "1" ] && [ -n "${KEEP_PID:-}" ]; then
  touch "${STOP}"
  wait "${KEEP_PID}" 2>/dev/null || true
  rm -f "${STOP}"
fi

bash /userdata/voice/scripts/mic_setup.sh >/dev/null 2>&1 || true
exit "${RC}"
