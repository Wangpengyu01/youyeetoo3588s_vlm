#!/bin/bash
# WebRTC/WHEP grab needs libnice for GStreamer webrtcbin (run on board as root).
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
timeout 45 apt-get update -qq || true
timeout 120 apt-get install -y --no-install-recommends \
  gstreamer1.0-nice \
  gstreamer1.0-plugins-bad \
  python3-gi \
  gir1.2-gst-1.0 \
  gir1.2-gstwebrtc-1.0
echo "[webrtc-deps] ok — verify: gst-inspect-1.0 nice src"
