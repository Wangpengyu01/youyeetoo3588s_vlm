#!/bin/bash
# Test 3.5mm headset mic routes (TRRS plug with microphone).
set -euo pipefail
source /userdata/voice/scripts/voice_env.sh

export PLAYBACK_ROUTE="${PLAYBACK_ROUTE:-headphone}"
export MIC_CAPTURE_GAIN="${MIC_CAPTURE_GAIN:-6}"

echo "=== 3.5mm 耳机麦测试 ==="
echo "请插入带麦克风的 TRRS 耳机/耳麦（TRS 音响线无麦）"
echo "Headphone Jack: $(amixer -c 0 cget numid=26 2>/dev/null | sed -n 's/^  : values=//p' | head -1)"
echo "Headset Mic Jack: $(amixer -c 0 cget numid=27 2>/dev/null | sed -n 's/^  : values=//p' | head -1)"
echo

python3 /userdata/voice/scripts/mic_probe.py

echo
echo "--- 手动指定路由示例 ---"
echo "export MIC_ROUTE=headset_line2"
echo "export MIC_SOURCE=headset"
echo "export RECORD_CHANNELS=2"
echo "bash /userdata/voice/scripts/mic_diag.sh 5"
