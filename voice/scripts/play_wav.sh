#!/bin/bash
# Play wav; optional monitor mode boosts quiet recordings for audition.
set -euo pipefail
WAV="${1:?usage: play_wav.sh file.wav [monitor]}"
MODE="${2:-}"

source /userdata/voice/scripts/voice_env.sh

# Route playback only — do NOT touch mic before aplay (codec switch eats first syllable)
bash /userdata/voice/scripts/speaker_setup.sh >/dev/null

WARMUP="${PLAYBACK_WARMUP_SEC:-0.12}"
if awk "BEGIN{exit !(${WARMUP} > 0)}"; then
  sleep "${WARMUP}"
fi

PLAY=/tmp/play_16k.wav
CHANNELS="${PLAYBACK_CHANNELS:-1}"
if [ "${PLAYBACK_MONO:-stereo}" = "stereo" ]; then
  CHANNELS=2
fi
export PLAYBACK_CHANNELS="${CHANNELS}"

if [ "${MODE}" = "monitor" ]; then
  PLAYBACK_MODE=monitor PLAYBACK_GAIN="${REPLAY_MONITOR_GAIN:-5.0}" \
    PLAYBACK_LEAD_MS="${PLAYBACK_LEAD_MS:-80}" \
    python3 /userdata/voice/scripts/wav_to_16k_mono.py "${WAV}" "${PLAY}" >&2
else
  python3 /userdata/voice/scripts/wav_to_16k_mono.py "${WAV}" "${PLAY}" >&2
fi

echo "[play] ▶ ${WAV} (${MODE:-normal})" >&2

APLAY_OPTS=()
if [ -n "${PLAYBACK_BUFFER_US:-80000}" ]; then
  APLAY_OPTS+=(--buffer-time="${PLAYBACK_BUFFER_US}")
fi

# PulseAudio can clear Headphone/Speaker switches during direct ALSA playback.
spk_route_guard() {
  while kill -0 "${APLAY_PID:-$$}" 2>/dev/null; do
    case "${PLAYBACK_ROUTE:-headphone}" in
      onboard|speaker|board)
        hp=$(amixer -c 0 cget numid=28 2>/dev/null | sed -n 's/^  : values=//p')
        spk=$(amixer -c 0 cget numid=29 2>/dev/null | sed -n 's/^  : values=//p')
        [ "${hp}" = "off" ] && [ "${spk}" = "on" ] || bash /userdata/voice/scripts/speaker_setup.sh >/dev/null 2>&1
        ;;
      *)
        hp=$(amixer -c 0 cget numid=28 2>/dev/null | sed -n 's/^  : values=//p')
        [ "${hp}" = "on" ] || bash /userdata/voice/scripts/speaker_setup.sh >/dev/null 2>&1
        ;;
    esac
    sleep 0.03
  done
}

APLAY_PID=$$
spk_route_guard &
GUARD_PID=$!

run_aplay() {
  if ! command -v pasuspender >/dev/null 2>&1; then
    aplay -D plughw:0,0 "${APLAY_OPTS[@]}" "${PLAY}"
  else
    pasuspender -- aplay -D plughw:0,0 "${APLAY_OPTS[@]}" "${PLAY}"
  fi
}

if ! run_aplay; then
  kill "${GUARD_PID}" 2>/dev/null || true
  wait "${GUARD_PID}" 2>/dev/null || true
  echo "[play] aplay failed" >&2
  exit 1
fi

kill "${GUARD_PID}" 2>/dev/null || true
wait "${GUARD_PID}" 2>/dev/null || true
bash /userdata/voice/scripts/speaker_setup.sh >/dev/null

if [ "${VOICE_RESTORE_MIC:-1}" = "1" ]; then
  bash /userdata/voice/scripts/mic_setup.sh >/dev/null 2>&1 || true
fi
echo "[play] 完成" >&2
