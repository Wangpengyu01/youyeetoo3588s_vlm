param(
  [string]$Repo = "C:\Users\wwff\Documents\youyeetoo3588s_vlm_upstream"
)
$ErrorActionPreference = "Stop"
$files = @(
  @("$Repo\p4\scripts\install_rndis_usb0.sh", "/userdata/p4/scripts/install_rndis_usb0.sh"),
  @("$Repo\p4\scripts\boot_rndis_usb.sh", "/userdata/p4/scripts/boot_rndis_usb.sh"),
  @("$Repo\p4\systemd\r1-rndis-usb.service", "/userdata/p4/systemd/r1-rndis-usb.service"),
  @("$Repo\p4\scripts\mediamtx_gen_config.sh", "/userdata/p4/scripts/mediamtx_gen_config.sh"),
  @("$Repo\agent\scripts\setup_camera_lowlatency_env.sh", "/userdata/agent/scripts/setup_camera_lowlatency_env.sh"),
  @("$Repo\agent\scripts\mediamtx_rtsp_frame_daemon.sh", "/userdata/agent/scripts/mediamtx_rtsp_frame_daemon.sh"),
  @("$Repo\agent\scripts\benchmark_camera_grab.sh", "/userdata/agent/scripts/benchmark_camera_grab.sh"),
  @("$Repo\agent\scripts\install_mediamtx_webrtc_deps.sh", "/userdata/agent/scripts/install_mediamtx_webrtc_deps.sh"),
  @("$Repo\agent\orchestrator\mediamtx_camera.py", "/userdata/agent/orchestrator/mediamtx_camera.py"),
  @("$Repo\agent\orchestrator\whep_frame.py", "/userdata/agent/orchestrator/whep_frame.py"),
  @("$Repo\agent\config\agent.yaml", "/userdata/agent/config/agent.yaml")
)
foreach ($f in $files) {
  if ($f[0] -match '\.sh$') {
    $t = [IO.File]::ReadAllText($f[0]) -replace "`r`n", "`n"
    [IO.File]::WriteAllText($f[0], $t)
  }
  adb push $f[0] $f[1]
}
Write-Host "Run on board (SSH/serial if adb shell hangs):"
Write-Host "  sudo bash /userdata/agent/scripts/setup_camera_lowlatency_env.sh"
