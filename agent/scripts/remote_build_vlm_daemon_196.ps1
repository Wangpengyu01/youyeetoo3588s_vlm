# Push P5b sources to gp@192.168.100.196 and run build_vlm_daemon_196.sh (interactive password).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Host196 = "gp@192.168.100.196"
$Remote = "/tmp/vlm_daemon_build"

Write-Host "[196] mkdir $Remote on build host"
ssh $Host196 "mkdir -p $Remote/src"

$Daemon = Join-Path $Root "agent\daemon"
foreach ($f in @(
  "vlm_daemon.cpp", "vlm_internvl_bridge.h", "vlm_internvl_bridge_stub.cpp",
  "Makefile.vlm_fragment", "llm_daemon.cpp"
)) {
  scp (Join-Path $Daemon $f) "${Host196}:${Remote}/src/"
}

scp (Join-Path $Root "agent\scripts\build_vlm_daemon_196.sh") "${Host196}:${Remote}/"
scp (Join-Path $Root "agent\scripts\setup_build_host_196.sh") "${Host196}:${Remote}/"

Write-Host "[196] setup + build (set SESSION_DEMO / INTERNVL_DEMO if find fails)"
ssh -t $Host196 @"
cd $Remote && bash setup_build_host_196.sh
export REPO=\$(find ~ -maxdepth 4 -type d -name 'youyeetoo3588s_vlm_upstream' 2>/dev/null | head -1)
export SESSION_DEMO=\${SESSION_DEMO:-\$HOME/project/R1_SDK/rknn/rknn3-runtime/examples/rknn3_session_test_demo}
export INTERNVL_DEMO=\${INTERNVL_DEMO:-}
bash build_vlm_daemon_196.sh
"@

Write-Host "[196] pull binary to agent/bin/"
scp "${Host196}:${Remote}/vlm_daemon" (Join-Path $Root "agent\bin\vlm_daemon") 2>$null
if (Test-Path (Join-Path $Root "agent\bin\vlm_daemon")) {
  adb push (Join-Path $Root "agent\bin\vlm_daemon") /userdata/agent/bin/vlm_daemon
  adb shell chmod +x /userdata/agent/bin/vlm_daemon
  Write-Host "[board] pushed /userdata/agent/bin/vlm_daemon"
}
