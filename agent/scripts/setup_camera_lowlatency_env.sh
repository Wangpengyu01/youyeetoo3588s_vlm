#!/bin/bash
# One-shot on board (root): RNDIS + mediamtx + WebRTC deps + pick fastest grab mode.
set -euo pipefail
AGENT="${AGENT_ROOT:-/userdata/agent}"
P4="${P4_ROOT:-/userdata/p4}"

echo "=== [1/5] RNDIS usb0 (PC maintenance) ==="
if [ -d /sys/class/net/usb0 ]; then
  bash "${P4}/scripts/install_rndis_usb0.sh" || true
else
  echo "[skip] usb0 not present (USB gadget RNDIS may enable after replug)"
fi

echo "=== [2/5] mediamtx ==="
if [ -x "${P4}/bin/mediamtx" ]; then
  bash "${P4}/scripts/mediamtx_gen_config.sh" 2>/dev/null || true
  sed -i 's/\r$//' "${P4}/scripts/mediamtx_gen_config.sh" 2>/dev/null || true
  if ! pgrep -x mediamtx >/dev/null; then
    nohup "${P4}/bin/mediamtx" "${P4}/config/mediamtx.yml" >>"${P4}/logs/mediamtx.log" 2>&1 &
    sleep 3
  fi
else
  echo "[warn] ${P4}/bin/mediamtx missing — deploy tarball first"
fi

echo "=== [3/5] GStreamer WebRTC (WHEP) deps ==="
if ! gst-inspect-1.0 nice 2>/dev/null | head -1 | grep -q nice; then
  if [ "${SKIP_APT:-0}" = "1" ]; then
    echo "[skip] SKIP_APT=1 — WHEP needs: sudo bash ${AGENT}/scripts/install_mediamtx_webrtc_deps.sh (SSH, not adb)"
  elif [ "$(id -u)" -eq 0 ]; then
    timeout 90 bash "${AGENT}/scripts/install_mediamtx_webrtc_deps.sh" || echo "[warn] apt timeout/fail — use SSH for WebRTC deps"
  else
    echo "[warn] run on SSH: sudo bash ${AGENT}/scripts/install_mediamtx_webrtc_deps.sh"
  fi
fi

echo "=== [4/5] mediamtx RTSP frame daemon (low-latency cache) ==="
pkill -f mediamtx_rtsp_frame_daemon.sh 2>/dev/null || true
nohup bash "${AGENT}/scripts/mediamtx_rtsp_frame_daemon.sh" >>"${AGENT}/logs/mediamtx_frame_daemon.log" 2>&1 &
sleep 8

echo "=== [5/5] benchmark grab paths ==="
sed -i 's/\r$//' "${AGENT}/scripts/benchmark_camera_grab.sh" 2>/dev/null || true
bash "${AGENT}/scripts/benchmark_camera_grab.sh" | tee "${AGENT}/logs/camera_grab_benchmark.txt"

if [ -f "${AGENT}/config/agent.yaml" ] && grep -q '^  grab_backend:' "${AGENT}/config/agent.yaml"; then
  sed -i 's/^  grab_backend:.*/  grab_backend: mediamtx_rtsp/' "${AGENT}/config/agent.yaml"
  echo "[done] agent.yaml grab_backend=mediamtx_rtsp (daemon cache → local RTSP, no WHEP)"
fi
echo "[done] log: ${AGENT}/logs/camera_grab_benchmark.txt"
