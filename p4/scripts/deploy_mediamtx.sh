#!/bin/bash
# Install MediaMTX binary + systemd on R1 (run on board as root).
set -euo pipefail
P4_ROOT="${P4_ROOT:-/userdata/p4}"
BIN="${P4_ROOT}/bin/mediamtx"
TARBALL="${1:-${P4_ROOT}/tmp/mediamtx_linux_arm64.tar.gz}"

mkdir -p "${P4_ROOT}/bin" "${P4_ROOT}/tmp" "${P4_ROOT}/logs"
chmod +x "${P4_ROOT}/scripts/mediamtx_gen_config.sh" "${P4_ROOT}/scripts/mediamtx_smoke.sh" 2>/dev/null || true

if [[ -f "${TARBALL}" ]]; then
  echo "[mediamtx] extracting ${TARBALL}..."
  tar -xzf "${TARBALL}" -C "${P4_ROOT}/tmp" mediamtx
  install -m 755 "${P4_ROOT}/tmp/mediamtx" "${BIN}"
  rm -f "${P4_ROOT}/tmp/mediamtx"
elif [[ ! -x "${BIN}" ]]; then
  echo "[mediamtx] missing tarball and ${BIN}" >&2
  exit 1
fi

"${P4_ROOT}/scripts/mediamtx_gen_config.sh"

if [[ -f "${P4_ROOT}/systemd/r1-mediamtx.service" ]]; then
  install -m 644 "${P4_ROOT}/systemd/r1-mediamtx.service" /etc/systemd/system/
  systemctl daemon-reload
  systemctl enable r1-mediamtx.service
  systemctl restart r1-mediamtx.service
  sleep 2
  systemctl is-active r1-mediamtx.service
  AGENT="${AGENT_ROOT:-/userdata/agent}"
  if [[ -f "${AGENT}/systemd/r1-mediamtx-frame.service" ]]; then
    install -m 644 "${AGENT}/systemd/r1-mediamtx-frame.service" /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable r1-mediamtx-frame.service
    systemctl restart r1-mediamtx-frame.service || true
    echo "[mediamtx] r1-mediamtx-frame.service enabled"
  fi
else
  pkill -x mediamtx 2>/dev/null || true
  sleep 1
  nohup "${BIN}" "${P4_ROOT}/config/mediamtx.yml" >>"${P4_ROOT}/logs/mediamtx.log" 2>&1 &
  sleep 2
fi

bash "${P4_ROOT}/scripts/mediamtx_smoke.sh"
