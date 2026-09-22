#!/bin/bash
# ==============================================================================
# 小揽 · RK3588 边缘端多模态智能终端 一键启停管理脚本 (Quickstart Management)
# 支持: start | stop | restart | status
# ==============================================================================
set -euo pipefail

AGENT_ROOT="${AGENT_ROOT:-/userdata/agent}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export AGENT_ROOT

COLOR_GREEN="\033[1;32m"
COLOR_CYAN="\033[1;36m"
COLOR_YELLOW="\033[1;33m"
COLOR_RED="\033[1;31m"
COLOR_RESET="\033[0m"

get_board_ip() {
  local ip
  ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
  if [[ -z "${ip}" ]]; then
    ip="127.0.0.1"
  fi
  echo "${ip}"
}

do_status() {
  echo -e "${COLOR_CYAN}=== 小揽智能终端运行状态检测 (Xiao Lan Status) ===${COLOR_RESET}"
  local ip="$(get_board_ip)"

  # 1. LLM Daemon
  if [[ -S /tmp/r1-llm.sock ]] || pgrep -f "llm_daemon" >/dev/null 2>&1; then
    echo -e "• 端侧大模型 (LLM Daemon):   [${COLOR_GREEN}运行中 RUNNING${COLOR_RESET}] (socket: /tmp/r1-llm.sock)"
  else
    echo -e "• 端侧大模型 (LLM Daemon):   [${COLOR_YELLOW}未运行 STOPPED${COLOR_RESET}]"
  fi

  # 2. Orchestrator
  if pgrep -f "orchestrator.main" >/dev/null 2>&1; then
    echo -e "• 智能体中枢 (Orchestrator): [${COLOR_GREEN}运行中 RUNNING${COLOR_RESET}] (API: ws://${ip}:8765/ws)"
  else
    echo -e "• 智能体中枢 (Orchestrator): [${COLOR_YELLOW}未运行 STOPPED${COLOR_RESET}]"
  fi

  # 3. Web UI
  if pgrep -f "http.server.*8766" >/dev/null 2>&1; then
    echo -e "• Web 控制台 (Web UI):       [${COLOR_GREEN}运行中 RUNNING${COLOR_RESET}] (URL: http://${ip}:8766)"
  else
    echo -e "• Web 控制台 (Web UI):       [${COLOR_YELLOW}未运行 STOPPED${COLOR_RESET}]"
  fi
}

do_stop() {
  echo -e "${COLOR_YELLOW}正在停止小揽所有相关服务...${COLOR_RESET}"
  pkill -f "orchestrator.main" 2>/dev/null || true
  pkill -f "http.server.*8766" 2>/dev/null || true
  pkill -f "llm_daemon" 2>/dev/null || true
  rm -f "${AGENT_ROOT}/run/"*.pid 2>/dev/null || true
  rm -f /tmp/r1-llm.sock 2>/dev/null || true
  sleep 1
  echo -e "${COLOR_GREEN}已成功停止所有服务。${COLOR_RESET}"
}

do_start() {
  local ip="$(get_board_ip)"
  echo -e "${COLOR_CYAN}"
  echo "============================================================"
  echo "        小揽 · RK3588 边缘多模态智能终端 一键启动          "
  echo "============================================================"
  echo -e "${COLOR_RESET}"

  mkdir -p "${AGENT_ROOT}/run" "${AGENT_ROOT}/logs"
  rm -f /tmp/agent_tts_*.wav /tmp/tts_out*.wav 2>/dev/null || true

  # 1. Start LLM daemon if binary exists
  if [[ -x "${AGENT_ROOT}/bin/llm_daemon" ]]; then
    if [[ ! -S /tmp/r1-llm.sock ]]; then
      echo -e "${COLOR_YELLOW}[1/3] 正在启动端侧大模型进程 (LLM Daemon)...${COLOR_RESET}"
      bash "${SCRIPT_DIR}/start_llm_daemon.sh" || true
    else
      echo -e "${COLOR_GREEN}[1/3] 端侧大模型已处于运行状态。${COLOR_RESET}"
    fi
  else
    echo -e "${COLOR_YELLOW}[1/3] 未找到 ${AGENT_ROOT}/bin/llm_daemon，将使用云端/回退模式。${COLOR_RESET}"
  fi

  # 2. Start Orchestrator
  echo -e "${COLOR_YELLOW}[2/3] 正在启动小揽核心智能体 (VAD + ASR + TTS + RTSP 视觉中枢)...${COLOR_RESET}"
  bash "${SCRIPT_DIR}/start_orchestrator.sh"

  # 3. Start Web UI HTTP Server
  echo -e "${COLOR_YELLOW}[3/3] 正在启动 Web UI 控制台服务 (端口 8766)...${COLOR_RESET}"
  bash "${SCRIPT_DIR}/open_agent_gui.sh" || true

  echo ""
  echo -e "${COLOR_GREEN}============================================================${COLOR_RESET}"
  echo -e "${COLOR_GREEN}             小揽 智能终端全部服务启动成功！               ${COLOR_RESET}"
  echo -e "${COLOR_GREEN}============================================================${COLOR_RESET}"
  echo -e "• 浏览器控制台:  ${COLOR_CYAN}http://${ip}:8766${COLOR_RESET}"
  echo -e "• WebSocket API: ${COLOR_CYAN}ws://${ip}:8765/ws${COLOR_RESET}"
  echo -e "• 实时运行日志:  tail -f ${AGENT_ROOT}/logs/orchestrator.log"
  echo -e "• 查看运行状态:  bash ${SCRIPT_DIR}/quickstart_all.sh status"
  echo -e "• 停止所有服务:  bash ${SCRIPT_DIR}/quickstart_all.sh stop"
  echo -e "${COLOR_GREEN}============================================================${COLOR_RESET}"
}

ACTION="${1:-start}"
case "${ACTION}" in
  start)
    do_start
    ;;
  stop)
    do_stop
    ;;
  restart)
    do_stop
    sleep 1
    do_start
    ;;
  status)
    do_status
    ;;
  *)
    echo "用法: $0 {start|stop|restart|status}"
    exit 1
    ;;
esac
