#!/bin/bash
# Quick playback test for current PLAYBACK_ROUTE
set -euo pipefail
source /userdata/voice/scripts/voice_env.sh

echo "=== 喇叭测试 ==="
echo "PLAYBACK_ROUTE=${PLAYBACK_ROUTE:-headphone}"
echo "PLAYBACK_GAIN=${PLAYBACK_GAIN:-3.0}"
bash /userdata/voice/scripts/speaker_setup.sh

echo
echo "[1/3] 滴声..."
bash /userdata/voice/scripts/beep.sh

echo
echo "[2/3] TTS..."
bash /userdata/voice/scripts/tts.sh "你好，这是外接音响测试。"

echo
echo "[3/3] 路由状态:"
amixer -c 0 cget numid=28 2>/dev/null | grep -E 'numid|values' || true
amixer -c 0 cget numid=29 2>/dev/null | grep -E 'numid|values' || true
amixer -c 0 cget numid=35 2>/dev/null | grep -E 'numid|values' || true
echo "=== 完成 ==="
