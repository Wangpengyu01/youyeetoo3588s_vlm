# One-shot R1 demo recovery when /userdata/agent and /userdata/p4 are missing
# but systemd units still exist. Run on Windows PC with adb + repo clone.
param(
    [string]$RepoRoot = "",
    [string]$MediamtxTarball = "",
    [string]$RtspEnv = ""
)
$ErrorActionPreference = "Stop"
if (-not $RepoRoot) {
    $RepoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
}
$RepoRoot = (Resolve-Path $RepoRoot).Path

Write-Host "=== R1 demo recover ===" -ForegroundColor Cyan
Write-Host "Repo: $RepoRoot"

adb devices | Select-String "device$" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "adb: no device — plug USB and run adb devices" }

adb shell "mkdir -p /userdata/agent /userdata/p4 /userdata/voice /userdata/agent/logs /userdata/agent/run"

Write-Host "[1/5] push agent ..."
& (Join-Path $RepoRoot "agent\scripts\push_agent.ps1")

Write-Host "[2/5] push p4 ..."
& (Join-Path $RepoRoot "p4\push_p4.ps1")

$VoicePush = Join-Path $RepoRoot "voice\scripts\push_voice.ps1"
if (Test-Path $VoicePush) {
    Write-Host "[3/5] push voice ..."
    & $VoicePush
} else {
    Write-Host "[3/5] skip voice (no push_voice.ps1)"
}

if (-not $MediamtxTarball) {
    $candidates = @(
        (Join-Path $RepoRoot "p4\tmp\mediamtx_linux_arm64.tar.gz"),
        (Join-Path $RepoRoot "mediamtx_v1.21.1_linux_arm64.tar.gz"),
        "C:\Users\wwff\Documents\youyeetoo3588s\mediamtx_v1.21.1_linux_arm64.tar.gz"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { $MediamtxTarball = $c; break }
    }
}
if ($MediamtxTarball -and (Test-Path $MediamtxTarball)) {
    Write-Host "[4/5] install mediamtx from $MediamtxTarball ..."
    adb shell "mkdir -p /userdata/p4/bin /userdata/p4/tmp /userdata/p4/logs"
    adb push $MediamtxTarball /userdata/p4/tmp/mediamtx_linux_arm64.tar.gz
    adb shell "bash /userdata/p4/scripts/deploy_mediamtx.sh /userdata/p4/tmp/mediamtx_linux_arm64.tar.gz"
} else {
    Write-Host "[4/5] WARN: no mediamtx tarball — copy mediamtx_*_linux_arm64.tar.gz and re-run with -MediamtxTarball" -ForegroundColor Yellow
}

if ($RtspEnv -and (Test-Path $RtspEnv)) {
    adb push $RtspEnv /userdata/p4/config/rtsp.env
    adb shell "bash /userdata/p4/scripts/mediamtx_gen_config.sh 2>/dev/null || true"
} elseif (-not (adb shell "test -f /userdata/p4/config/rtsp.env && echo yes" 2>$null).Contains("yes")) {
    $ex = Join-Path $RepoRoot "p4\config\rtsp.env.example"
    if (Test-Path $ex) {
        Write-Host "[rtsp] no rtsp.env — pushing example (EDIT camera URL on board!)" -ForegroundColor Yellow
        adb push $ex /userdata/p4/config/rtsp.env
    }
}

$Vlm = Join-Path $RepoRoot "agent\bin\vlm_daemon"
if (Test-Path $Vlm) {
    Write-Host "[bin] push vlm_daemon ..."
    adb push $Vlm /userdata/agent/bin/vlm_daemon
    adb shell "chmod +x /userdata/agent/bin/vlm_daemon"
} else {
    Write-Host "[bin] WARN: no agent\bin\vlm_daemon — copy from build machine or working board" -ForegroundColor Yellow
}

Write-Host "[5/5] install systemd + start (root, may take 1-3 min) ..."
adb shell "bash /userdata/agent/scripts/install_autostart.sh"

adb forward tcp:8765 tcp:8765
adb forward tcp:8766 tcp:8766

Write-Host ""
Write-Host "=== status ===" -ForegroundColor Cyan
adb shell "systemctl is-active r1-p4-eth r1-mediamtx r1-mediamtx-frame r1-vlm-daemon r1-orchestrator r1-webui 2>/dev/null || true"
adb shell "test -f /userdata/agent/scripts/adb_board_diag.sh && bash /userdata/agent/scripts/adb_board_diag.sh || echo diag_missing"
Write-Host "WebUI: http://127.0.0.1:8766/ (after forward)" -ForegroundColor Green
