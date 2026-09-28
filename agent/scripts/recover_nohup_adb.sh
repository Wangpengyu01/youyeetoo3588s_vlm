#!/bin/bash
# adb-safe stack start: no blocking systemctl (use after userdata recover push).
if grep -q $'\r' "$0" 2>/dev/null; then
  sed -i 's/\r$//' "$0" 2>/dev/null || true
  exec /bin/bash "$0" "$@"
fi
set -eu
AGENT="${AGENT_ROOT:-/userdata/agent}"
P4="${P4_ROOT:-/userdata/p4}"
export AGENT_ROOT="${AGENT}" P4_ROOT="${P4}" PYTHONPATH="${AGENT}"

echo "[nohup-adb] strip CRLF on scripts"
sed -i 's/\r$//' "${AGENT}/scripts/"*.sh "${P4}/scripts/"*.sh 2>/dev/null || true
chmod +x "${AGENT}/scripts/"*.sh "${P4}/scripts/"*.sh 2>/dev/null || true
mkdir -p "${AGENT}/logs" "${AGENT}/run" "${P4}/logs" "${AGENT}/ui"

echo "[nohup-adb] network + mediamtx config"
bash "${P4}/scripts/boot_eth_static.sh" 2>&1 || true
bash "${P4}/scripts/mediamtx_gen_config.sh" 2>&1 || true

pkill -x mediamtx 2>/dev/null || true
pkill -f mediamtx_rtsp_frame_daemon.sh 2>/dev/null || true
sleep 1

if [[ -x "${P4}/bin/mediamtx" ]]; then
  echo "[nohup-adb] mediamtx"
  nohup "${P4}/bin/mediamtx" "${P4}/config/mediamtx.yml" >>"${P4}/logs/mediamtx.log" 2>&1 &
  sleep 2
fi

if [[ -f "${AGENT}/scripts/mediamtx_rtsp_frame_daemon.sh" ]]; then
  echo "[nohup-adb] frame daemon"
  nohup bash "${AGENT}/scripts/mediamtx_rtsp_frame_daemon.sh" >>"${AGENT}/logs/mediamtx_frame_daemon.log" 2>&1 &
fi

if [[ ! -S /tmp/r1-vlm.sock ]] && [[ -x "${AGENT}/bin/vlm_daemon" ]]; then
  if [[ ! -f "${AGENT}/models/InternVL3_5-4B/vision_InternVL3_5-4B.rknn" ]] && \
     [[ ! -f /userdata/models/InternVL3_5-4B/vision_InternVL3_5-4B.rknn ]]; then
    echo "[nohup-adb] WARN: missing /userdata/models/InternVL3_5-4B/*.rknn" >&2
  fi
  echo "[nohup-adb] vlm_daemon (loads 2-5 min, do not Ctrl+C adb)"
  bash "${AGENT}/scripts/start_vlm_daemon.sh" 2>&1 || true
fi

echo "[nohup-adb] wait vlm sock up to 90s (then continue anyway)"
i=0
while [ "$i" -lt 90 ]; do
  if [ -S /tmp/r1-vlm.sock ]; then
    chmod 777 /tmp/r1-vlm.sock 2>/dev/null || true
    echo "[nohup-adb] vlm sock ready (${i}s)"
    break
  fi
  i=$((i + 1))
  sleep 1
done

pkill -f 'xiaolan_cli serve' 2>/dev/null || true
pkill -f 'http.server.*8766' 2>/dev/null || true
sleep 1

if [ -S /tmp/r1-vlm.sock ] || [ -S /tmp/r1-llm.sock ]; then
  echo "[nohup-adb] orchestrator + webui"
  if [ ! -f "${VOICE:-/userdata/voice}/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/lib/libsherpa-onnx-c-api.so" ]; then
    echo "[nohup-adb] WARN: voice/sherpa missing — push voice assets before orchestrator" >&2
  fi
  if ! grep -q 'backend: vits' "${AGENT}/config/agent.yaml" 2>/dev/null; then
    if [ -d /userdata/voice/vits-melo-tts-zh_en ] && ! [ -d /userdata/voice/matcha-icefall-zh-baker ]; then
      sed -i 's/backend: matcha/backend: vits/; s|matcha-icefall-zh-baker|vits-melo-tts-zh_en|' "${AGENT}/config/agent.yaml" 2>/dev/null || true
    fi
  fi
  nohup bash -c "export PYTHONPATH=${AGENT} LD_LIBRARY_PATH=/userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/lib; exec python3 -m xiaolan_cli serve --config ${AGENT}/config/agent.yaml --agent-root ${AGENT}" \
    >>"${AGENT}/logs/orchestrator.log" 2>&1 &
  if ! pgrep -f 'http.server.*8766' >/dev/null 2>&1; then
    nohup python3 -m http.server 8766 --bind 0.0.0.0 --directory "${AGENT}/ui" \
      >>"${AGENT}/logs/webui.log" 2>&1 &
  fi
else
  echo "[nohup-adb] skip orchestrator — no infer socket (tail ${AGENT}/logs/vlm_daemon.log)" >&2
fi

sleep 2
echo "[nohup-adb] processes:"
pgrep -af 'mediamtx|vlm_daemon|xiaolan_cli|http.server.*8766' || true
echo "[nohup-adb] ports:"
ss -ltnp 2>/dev/null | grep -E '8554|8765|8766' || netstat -ltn 2>/dev/null | grep -E '8554|8765|8766' || true
