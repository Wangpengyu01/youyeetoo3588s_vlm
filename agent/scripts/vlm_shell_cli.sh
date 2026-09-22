#!/bin/bash
# M1 interactive CLI: text chat via llm_daemon socket; vision via RTSP grab + vlm_see (1828 handoff).
# Usage on board:
#   bash /userdata/agent/scripts/vlm_shell_cli.sh
# Requires: r1-llm-daemon or start_llm_daemon.sh; models under /userdata/models/...
set -eu

AGENT_ROOT="${AGENT_ROOT:-/userdata/agent}"
SOCK="${LLM_SOCK:-/tmp/r1-llm.sock}"
MAX_NEW="${VLM_CLI_MAX_NEW:-128}"

vision_intent() {
  local t="$1"
  case "${t}" in
    *查看*画面*|*看看*画面*|*描述*画面*|*当前画面*|*看一下*|*看图*|*瞧瞧*)
      return 0
      ;;
  esac
  return 1
}

echo "小揽 VLM shell CLI (M1)"
echo "  文字: 直接输入；看图: 「请查看当前画面」等"
echo "  命令: /quit /clear /ping"
echo ""

while true; do
  if ! IFS= read -r -p "小揽> " line; then
    echo
    break
  fi
  line="${line#"${line%%[![:space:]]*}"}"
  line="${line%"${line##*[![:space:]]}"}"
  [ -z "${line}" ] && continue

  case "${line}" in
    /quit|/exit|quit|exit)
      break
      ;;
    /clear)
      python3 "${AGENT_ROOT}/scripts/llm_client.py" --socket "${SOCK}" --clear
      continue
      ;;
    /ping)
      python3 "${AGENT_ROOT}/scripts/llm_client.py" --socket "${SOCK}" --ping
      continue
      ;;
  esac

  if vision_intent "${line}"; then
    echo "[cli] 抓取 RTSP 并运行 VLM…" >&2
    bash "${AGENT_ROOT}/scripts/cooperative_stop_llm.sh" || true
    CAP=$(bash "${AGENT_ROOT}/scripts/vlm_cli_see.sh" "${line}" 2>"${AGENT_ROOT}/logs/vlm_cli_see.err" || true)
    bash "${AGENT_ROOT}/scripts/cooperative_start_llm.sh" || true
    if [ -n "${CAP}" ]; then
      echo "${CAP}"
    else
      echo "[cli] 看图失败，见 ${AGENT_ROOT}/logs/vlm_cli_see.err" >&2
    fi
    continue
  fi

  python3 "${AGENT_ROOT}/scripts/llm_client.py" --socket "${SOCK}" --prompt "${line}" --max-new "${MAX_NEW}"
done

echo "再见。"
