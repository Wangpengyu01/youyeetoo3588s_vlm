# Push MediaMTX arm64 tarball from repo root and install on R1 via adb.
param(
  [string]$Tarball = "C:\Users\wwff\Documents\youyeetoo3588s\mediamtx_v1.21.1_linux_arm64.tar.gz"
)
$ErrorActionPreference = "Stop"
if (-not (Test-Path $Tarball)) {
  Write-Error "Missing $Tarball — download linux_arm64 from GitHub releases."
}
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Write-Host "[adb] push mediamtx + p4 scripts..."
adb shell "mkdir -p /userdata/p4/bin /userdata/p4/tmp /userdata/p4/systemd /userdata/p4/logs"
adb push $Tarball /userdata/p4/tmp/mediamtx_linux_arm64.tar.gz
adb push (Join-Path $root "p4\scripts\mediamtx_gen_config.sh") /userdata/p4/scripts/mediamtx_gen_config.sh
adb push (Join-Path $root "p4\scripts\mediamtx_smoke.sh") /userdata/p4/scripts/mediamtx_smoke.sh
adb push (Join-Path $root "p4\scripts\deploy_mediamtx.sh") /userdata/p4/scripts/deploy_mediamtx.sh
adb push (Join-Path $root "p4\systemd\r1-mediamtx.service") /userdata/p4/systemd/r1-mediamtx.service
adb shell "sed -i 's/\r$//' /userdata/p4/scripts/mediamtx_gen_config.sh /userdata/p4/scripts/mediamtx_smoke.sh /userdata/p4/scripts/deploy_mediamtx.sh 2>/dev/null; chmod +x /userdata/p4/scripts/mediamtx_*.sh /userdata/p4/scripts/deploy_mediamtx.sh; bash /userdata/p4/scripts/deploy_mediamtx.sh /userdata/p4/tmp/mediamtx_linux_arm64.tar.gz"
