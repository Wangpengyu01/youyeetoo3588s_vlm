#!/bin/bash
# Phase A acceptance: llm_daemon vs llm_ask baseline
set -euo pipefail

AGENT_ROOT="${AGENT_ROOT:-/userdata/agent}"
CLIENT="python3 ${AGENT_ROOT}/scripts/llm_client.py"
SOCK="/tmp/r1-llm.sock"
BASELINE="python3 /userdata/voice/scripts/llm_ask.py"

echo "=== Phase A 板端验收 ==="

if [[ ! -S "${SOCK}" ]]; then
  echo "[1/4] daemon 未运行，尝试启动..."
  bash "${AGENT_ROOT}/scripts/start_llm_daemon.sh" || true
fi

if [[ ! -S "${SOCK}" ]]; then
  echo "SKIP daemon tests — ${SOCK} 不存在"
  echo "请先 VM 编译 llm_daemon 并 adb push 到 ${AGENT_ROOT}/bin/"
  echo ""
  echo "[baseline] llm_ask 单轮（对比用）..."
  time ${BASELINE} "用一句话介绍你自己" || true
  exit 0
fi

echo "[1/4] ping"
${CLIENT} --ping

echo ""
echo "[2/4] 单轮 chat + 流式"
${CLIENT} --prompt "你好，请用一句话介绍你自己。"

echo ""
echo "[3/4] 多轮 history"
${CLIENT} --prompt "我刚才问了什么？用中文简短回答。"
${CLIENT} --prompt "请把上一句回答再缩短成十个字以内。"

echo ""
echo "[4/4] clear_history"
${CLIENT} --clear

echo "=== Phase A 完成 ==="
