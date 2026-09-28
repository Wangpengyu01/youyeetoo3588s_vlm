#!/bin/bash
# Same as agent/scripts/recover_nohup_adb.sh — adb push to /userdata/agent/scripts/
if grep -q $'\r' "$0" 2>/dev/null; then sed -i 's/\r$//' "$0" 2>/dev/null || true; exec /bin/bash "$0" "$@"; fi
set -eu
AGENT="${AGENT_ROOT:-/userdata/agent}"
P4="${P4_ROOT:-/userdata/p4}"
export AGENT_ROOT="${AGENT}" P4_ROOT="${P4}" PYTHONPATH="${AGENT}"
sed -i 's/\r$//' "${AGENT}/scripts/"*.sh "${P4}/scripts/"*.sh 2>/dev/null || true
chmod +x "${AGENT}/scripts/"*.sh "${P4}/scripts/"*.sh 2>/dev/null || true
mkdir -p "${AGENT}/logs" "${AGENT}/run" "${P4}/logs"
bash "${P4}/scripts/boot_eth_static.sh" 2>&1 || true
bash "${P4}/scripts/mediamtx_gen_config.sh" 2>&1 || true
pkill -x mediamtx 2>/dev/null || true
pkill -f mediamtx_rtsp_frame_daemon.sh 2>/dev/null || true
sleep 1
[[ -x "${P4}/bin/mediamtx" ]] && nohup "${P4}/bin/mediamtx" "${P4}/config/mediamtx.yml" >>"${P4}/logs/mediamtx.log" 2>&1 &
sleep 2
[[ -f "${AGENT}/scripts/mediamtx_rtsp_frame_daemon.sh" ]] && \
  nohup bash "${AGENT}/scripts/mediamtx_rtsp_frame_daemon.sh" >>"${AGENT}/logs/mediamtx_frame_daemon.log" 2>&1 &
if [[ ! -S /tmp/r1-vlm.sock ]] && [[ -x "${AGENT}/bin/vlm_daemon" ]]; then
  bash "${AGENT}/scripts/start_vlm_daemon.sh" 2>&1 || true
fi
i=0; while [ "$i" -lt 90 ]; do [ -S /tmp/r1-vlm.sock ] && break; i=$((i+1)); sleep 1; done
[ -S /tmp/r1-vlm.sock ] && chmod 777 /tmp/r1-vlm.sock 2>/dev/null || true
pkill -f 'xiaolan_cli serve' 2>/dev/null || true
pkill -f 'http.server.*8766' 2>/dev/null || true
sleep 1
if [ -S /tmp/r1-vlm.sock ] || [ -S /tmp/r1-llm.sock ]; then
  export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-/userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/lib}"
  nohup python3 -m xiaolan_cli serve --config "${AGENT}/config/agent.yaml" --agent-root "${AGENT}" >>"${AGENT}/logs/orchestrator.log" 2>&1 &
  nohup python3 -m http.server 8766 --bind 0.0.0.0 --directory "${AGENT}/ui" >>"${AGENT}/logs/webui.log" 2>&1 &
fi
sleep 2
pgrep -af 'mediamtx|vlm_daemon|xiaolan_cli|8766' || true
ss -ltnp 2>/dev/null | grep -E '8554|8765|8766' || true
