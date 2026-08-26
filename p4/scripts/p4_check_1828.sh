#!/bin/bash
# Ensure RK1828 is idle enough for VLM (vision+llm). LLM-only / prior VLM leaves memory allocated.
set -eu

MAX_MB="${P4_MAX_IDLE_MB:-80}"

if ! rknn-smi info 2>&1 | grep -q "Online"; then
  echo "[P4] 1828 未 Online，请先 wait_rknn 或检查 rknn3.service" >&2
  exit 1
fi

USED=$(rknn-smi info 2>&1 | sed -n 's/.*| \([0-9][0-9]*\) *\/ 5120.*/\1/p' | head -1)
USED="${USED:-0}"

if [ "${USED}" -gt "${MAX_MB}" ] 2>/dev/null; then
  echo "[P4] 1828 显存已占用 ${USED}/5120 MB — 无法加载 VLM" >&2
  echo "[P4] 常见原因:" >&2
  echo "  · 刚跑过 voice_chat / llm_ask（LLM-only ~200–300MB）" >&2
  echo "  · 上一轮 VLM 崩溃或连续跑 p4_test（会话未释放）" >&2
  echo "[P4] 解决: 冷启动后再跑 P4（勿与语音 LLM 同 boot 混用）" >&2
  echo "  adb reboot && adb wait-for-device && sleep 45" >&2
  echo "  bash /userdata/p4/scripts/p4_test.sh" >&2
  exit 1
fi

echo "[P4] 1828 空闲 (${USED}/5120 MB) · 可加载 VLM"
