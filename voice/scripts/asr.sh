#!/bin/bash
set -euo pipefail
source /userdata/voice/scripts/voice_env.sh

WAV="${1:-/tmp/asr_input.wav}"
RAW="/tmp/asr_raw.wav"
SEC="${RECORD_SEC:-5}"
GAIN_STATE="/userdata/voice/.mic_gain"

if [ "${MIC_GAIN_LOCK:-0}" != "1" ] && [ -f "${GAIN_STATE}" ]; then
  MIC_CAPTURE_GAIN="$(cat "${GAIN_STATE}")"
  export MIC_CAPTURE_GAIN
fi

bash /userdata/voice/scripts/mic_setup.sh >/dev/null

echo "[ASR] 滴——请立即说话 (${SEC}s)..." >&2
bash /userdata/voice/scripts/beep.sh 2>/dev/null || true
bash /userdata/voice/scripts/mic_arm.sh || {
  echo "[ASR] mic_arm 失败，重试一次..." >&2
  sleep 0.2
  bash /userdata/voice/scripts/mic_arm.sh
}

# Stereo capture only when needed; main_board uses mono (matches mic_diag)
bash /userdata/voice/scripts/mic_record.sh "${RAW}" "${SEC}"
if [ "${RECORD_CHANNELS}" -eq 2 ]; then
  python3 /userdata/voice/scripts/pick_mono.py "${RAW}" "${WAV}" 2>&1 | sed 's/^/[ASR] /' >&2
else
  cp -f "${RAW}" "${WAV}"
fi
cp -f "${WAV}" /tmp/last_asr.wav

STATS=$(python3 /userdata/voice/scripts/analyze_wav.py "${WAV}")
PRE_STATS="${STATS}"
echo "${STATS}" >&2

python3 /userdata/voice/scripts/prep_asr_wav.py "${WAV}" 2>&1 | sed 's/^/[ASR] /' >&2 || true
cp -f "${WAV}" /tmp/last_asr_boost.wav

LEVEL=$(echo "${PRE_STATS}" | grep peak= | sed 's/.*peak=//;s/ .*//')

if [ -n "${LEVEL}" ] && [ "${LEVEL}" -ge 32000 ] 2>/dev/null; then
  if [ "${MIC_GAIN_LOCK:-0}" != "1" ]; then
    NEW_GAIN=$((MIC_CAPTURE_GAIN - 1))
    [ "${NEW_GAIN}" -lt 2 ] && NEW_GAIN=2
    echo "${NEW_GAIN}" > "${GAIN_STATE}"
    echo "[ASR] 警告: 削波 peak=${LEVEL}，下次增益 ${NEW_GAIN}" >&2
  else
    echo "[ASR] 警告: 削波 peak=${LEVEL}，冻结增益 ${MIC_CAPTURE_GAIN} 未自动下调" >&2
  fi
fi

# Mostly silence: use raw capture stats (before ASR boost)
PEAK=$(echo "${PRE_STATS}" | grep peak= | sed 's/.*peak=//;s/ .*//')
RMS=$(echo "${PRE_STATS}" | grep rms= | sed 's/.*rms=//;s/ .*//')
ACTIVE=$(echo "${PRE_STATS}" | grep above500= | sed 's/.*(//;s/%).*//')
if [ -n "${PEAK}" ] && [ -n "${RMS}" ] && [ -n "${ACTIVE}" ]; then
  awk -v peak="${PEAK}" -v rms="${RMS}" -v act="${ACTIVE}" 'BEGIN{
    if (peak >= 150) exit 0
    if (rms >= 25) exit 0
    if (peak >= 1500) exit 0
    if (rms >= 600 && act >= 2) exit 0
    if (peak < 100 && rms < 20) exit 1
    exit 0
  }' || {
    echo "[ASR] 录音几乎全是静音 (peak=${PEAK} rms=${RMS}, active=${ACTIVE}%)，咪头可能未接入此路由" >&2
    echo "[ASR] 请运行: python3 /userdata/voice/scripts/mic_probe.py" >&2
  }
fi
if [ -n "${PEAK}" ] && [ "${PEAK}" -lt 800 ] 2>/dev/null; then
  echo "[ASR] 提示: 原始电平偏低 peak=${PEAK}，已软件增益后再识别；请靠近板载麦说话" >&2
fi

echo "[ASR] ▶ 回放原始录音 (monitor 增益)..." >&2
bash /userdata/voice/scripts/play_wav.sh /tmp/last_asr.wav monitor

echo "[ASR] 识别中..." >&2
ASR_RAW=$("${SHERPA_BIN}/sherpa-onnx-offline" \
  --tokens="${ASR_MODEL}/tokens.txt" \
  --sense-voice-model="${ASR_MODEL}/model.int8.onnx" \
  --sense-voice-language=zh \
  --num-threads=2 \
  "${WAV}" 2>&1) || true

TEXT=$(echo "${ASR_RAW}" | python3 /userdata/voice/scripts/asr_parse.py 2>/dev/null) || true

if [ -z "${TEXT}" ]; then
  echo "[ASR] 未识别到语音" >&2
  echo "[ASR] sherpa 原始输出:" >&2
  echo "${ASR_RAW}" | grep -E '^\{|text|error|Error' | tail -5 >&2
  exit 1
fi

echo "[ASR] ${TEXT}" >&2
printf '%s\n' "${TEXT}"
