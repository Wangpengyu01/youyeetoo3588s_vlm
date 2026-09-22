#!/bin/bash
# Wrapper for net_static.sh (sets static IP 192.168.2.100 on eth0 for RTSP camera connectivity)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "${SCRIPT_DIR}/net_static.sh" "$@"
