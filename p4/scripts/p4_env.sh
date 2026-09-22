#!/bin/bash
# P4 RTSP 1fps + InternVL short caption on R1 + RM1828

export P4_ROOT="${P4_ROOT:-/userdata/p4}"
export SCRIPTS="${P4_ROOT}/scripts"

# Network (R1 eth0)
export STATIC_IP="${STATIC_IP:-192.168.2.100}"
export STATIC_PREFIX="${STATIC_PREFIX:-24}"
export STATIC_GW="${STATIC_GW:-192.168.2.1}"
export STATIC_DNS="${STATIC_DNS:-192.168.2.1 8.8.8.8}"
export NM_CONN="${NM_CONN:-Wired connection 1}"

# RTSP camera
export RTSP_URL="${RTSP_URL:-rtsp://192.168.2.169:554/stream_2}"
export RTSP_PROTOCOLS="${RTSP_PROTOCOLS:-tcp}"
export RTSP_LATENCY_MS="${RTSP_LATENCY_MS:-200}"

# Stream / VLM
export STREAM_WIDTH="${STREAM_WIDTH:-640}"
export STREAM_HEIGHT="${STREAM_HEIGHT:-480}"
export VLM_SIZE="${VLM_SIZE:-448}"
export VLM_FPS="${VLM_FPS:-1}"
export VLM_PROMPT="${VLM_PROMPT:-用一句话描述当前画面。}"

export LATEST_FRAME="${LATEST_FRAME:-/tmp/rtsp_latest.jpg}"
export VLM_FRAME="${VLM_FRAME:-/tmp/vlm_frame.jpg}"
export RTSP_CODEC="${RTSP_CODEC:-h264}"

# Auto-detect VLM_DEMO path
if [ -z "${VLM_DEMO:-}" ] || [ ! -d "${VLM_DEMO}" ]; then
  for cand in /userdata/rknn_InternVLM_demo /userdata/agent/rknn_InternVLM_demo "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." 2>/dev/null && pwd)/rknn_InternVLM_demo"; do
    if [ -d "${cand}" ]; then
      VLM_DEMO="${cand}"
      break
    fi
  done
fi
export VLM_DEMO="${VLM_DEMO:-/userdata/rknn_InternVLM_demo}"
export VLM_BIN="${VLM_DEMO}/rknn_internvl3_demo"
export VLM_MODEL="${VLM_MODEL:-/userdata/models/InternVL3_5-4B}"
export VLM_LD_LIBRARY_PATH="${VLM_DEMO}/lib:${VLM_DEMO}:/usr/lib:/usr/local/lib"

# TTS after caption (3588 CPU; uses frozen voice_hw_board.sh)
export P4_TTS="${P4_TTS:-1}"
export VOICE_SCRIPTS="${VOICE_SCRIPTS:-/userdata/voice/scripts}"
