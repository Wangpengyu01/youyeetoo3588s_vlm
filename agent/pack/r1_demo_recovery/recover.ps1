# Push bundled payload/ to /userdata/* and run install_autostart.sh
param(
    [switch]$PushOnly,
    [switch]$NoForward
)
$ErrorActionPreference = "Stop"
$PackRoot = $PSScriptRoot
$Payload = Join-Path $PackRoot "payload"
$BinDir = Join-Path $PackRoot "bin"
$CfgDir = Join-Path $PackRoot "config"

function Require-Path($p, $label) {
    if (-not (Test-Path $p)) {
        throw "Missing $label : $p — run build_recovery_zip.ps1 on dev PC first."
    }
}

function Push-Lf($Local, $Remote) {
    $content = [System.IO.File]::ReadAllText($Local).Replace("`r`n", "`n").Replace("`r", "`n")
    $tmp = [IO.Path]::GetTempFileName()
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($tmp, $content, $utf8)
    adb push $tmp $Remote | Out-Null
    Remove-Item $tmp -Force
}

function Push-PyTree($LocalDir, $RemoteDir) {
    if (-not (Test-Path $LocalDir)) { return }
    Get-ChildItem $LocalDir -Filter "*.py" -Recurse | ForEach-Object {
        $rel = $_.FullName.Substring($LocalDir.Length).TrimStart('\', '/')
        $remote = "$RemoteDir/$($rel -replace '\\', '/')"
        $parent = ($remote -replace '/[^/]+$', '')
        if ($parent) { adb shell "mkdir -p $parent" 2>$null | Out-Null }
        Push-Lf $_.FullName $remote
    }
}

function Push-AgentPayload($AgentLocal) {
    $Board = "/userdata/agent"
    Write-Host "[push] agent -> $Board"
    adb shell "mkdir -p $Board/bin $Board/scripts $Board/config $Board/logs $Board/run/tts $Board/asr $Board/orchestrator $Board/ui $Board/systemd $Board/xiaolan_cli $Board/api $Board/llm $Board/tts"
    Push-PyTree (Join-Path $AgentLocal "asr") "$Board/asr"
    Push-PyTree (Join-Path $AgentLocal "orchestrator") "$Board/orchestrator"
    Push-PyTree (Join-Path $AgentLocal "xiaolan_cli") "$Board/xiaolan_cli"
    Push-PyTree (Join-Path $AgentLocal "llm") "$Board/llm"
    Push-PyTree (Join-Path $AgentLocal "tts") "$Board/tts"
    Push-PyTree (Join-Path $AgentLocal "api") "$Board/api"
    Get-ChildItem (Join-Path $AgentLocal "scripts") -Filter "*.py" -ErrorAction SilentlyContinue | ForEach-Object {
        Push-Lf $_.FullName "$Board/scripts/$($_.Name)"
    }
    Get-ChildItem (Join-Path $AgentLocal "scripts") -Filter "*.sh" -ErrorAction SilentlyContinue | ForEach-Object {
        Push-Lf $_.FullName "$Board/scripts/$($_.Name)"
    }
    Push-Lf (Join-Path $AgentLocal "config\agent.yaml") "$Board/config/agent.yaml"
    Get-ChildItem (Join-Path $AgentLocal "ui") -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -ne "latest_frame.jpg" } | ForEach-Object {
            Push-Lf $_.FullName "$Board/ui/$($_.Name)"
        }
    Get-ChildItem (Join-Path $AgentLocal "systemd") -Filter "*.service" -ErrorAction SilentlyContinue | ForEach-Object {
        Push-Lf $_.FullName "$Board/systemd/$($_.Name)"
    }
    adb shell "find $Board/scripts -name '*.sh' -exec sed -i 's/\r$//' {} + 2>/dev/null; chmod +x $Board/scripts/*.sh 2>/dev/null; true"
}

function Push-P4Payload($P4Local) {
    Write-Host "[push] p4 -> /userdata/p4"
    adb shell "mkdir -p /userdata/p4/scripts /userdata/p4/systemd /userdata/p4/config /userdata/p4/bin /userdata/p4/logs /userdata/p4/tmp"
    Get-ChildItem $P4Local -Recurse -Include *.sh, *.py, *.yml, *.yaml, *.md, *.service, *.env, *.example -File -ErrorAction SilentlyContinue | ForEach-Object {
        $rel = $_.FullName.Substring($P4Local.Length).TrimStart('\', '/')
        $remote = "/userdata/p4/$($rel -replace '\\', '/')"
        $parent = ($remote -replace '/[^/]+$', '')
        if ($parent -and $parent -ne "/userdata/p4") { adb shell "mkdir -p $parent" 2>$null | Out-Null }
        if ($_.Name -match '\.(sh|py|yml|yaml|md|service|env|example)$') {
            Push-Lf $_.FullName $remote
        }
    }
    adb shell "chmod +x /userdata/p4/scripts/*.sh /userdata/p4/scripts/*.py 2>/dev/null; true"
}

function Push-VoicePayload($VoiceLocal) {
    $Board = "/userdata/voice/scripts"
    Write-Host "[push] voice scripts -> $Board"
    adb shell "mkdir -p $Board"
    Get-ChildItem (Join-Path $VoiceLocal "scripts") -File -ErrorAction SilentlyContinue | ForEach-Object {
        Push-Lf $_.FullName "$Board/$($_.Name)"
    }
    adb shell "chmod +x $Board/*.sh 2>/dev/null; true"
}

Write-Host "=== R1 demo recovery ===" -ForegroundColor Cyan
Require-Path $Payload "payload/"

$AgentP = Join-Path $Payload "agent"
$P4P = Join-Path $Payload "p4"
$VoiceP = Join-Path $Payload "voice"
Require-Path $AgentP "payload/agent"
Require-Path $P4P "payload/p4"

adb shell "mkdir -p /userdata/agent /userdata/p4 /userdata/voice"

Push-AgentPayload $AgentP
Push-P4Payload $P4P
if (Test-Path $VoiceP) { Push-VoicePayload $VoiceP }

foreach ($name in @("vlm_daemon", "llm_daemon")) {
    $local = Join-Path $BinDir $name
    if (Test-Path $local) {
        Write-Host "[bin] push $name"
        adb push $local "/userdata/agent/bin/$name"
        adb shell "chmod +x /userdata/agent/bin/$name"
    }
}

$mtxTar = Get-ChildItem $BinDir -Filter "mediamtx*.tar.gz" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($mtxTar) {
    Write-Host "[bin] install mediamtx from $($mtxTar.Name)"
    adb push $mtxTar.FullName /userdata/p4/tmp/mediamtx_linux_arm64.tar.gz
    adb shell "bash /userdata/p4/scripts/deploy_mediamtx.sh /userdata/p4/tmp/mediamtx_linux_arm64.tar.gz"
} else {
    Write-Host "[WARN] bin/mediamtx*.tar.gz not found — skip MediaMTX install" -ForegroundColor Yellow
}

$rtsp = Join-Path $CfgDir "rtsp.env"
$rtspEx = Join-Path $CfgDir "rtsp.env.example"
if (Test-Path $rtsp) {
    adb push $rtsp /userdata/p4/config/rtsp.env
} elseif (Test-Path $rtspEx) {
    Write-Host "[config] push rtsp.env from example (set camera password on board if needed)"
    adb push $rtspEx /userdata/p4/config/rtsp.env
} else {
    adb shell "mkdir -p /userdata/p4/config"
    adb shell "echo 'RTSP_URL=rtsp://192.168.2.169:554/stream_2' > /userdata/p4/config/rtsp.env"
    Write-Host "[WARN] using default rtsp.env — edit /userdata/p4/config/rtsp.env on board" -ForegroundColor Yellow
}
adb shell "bash /userdata/p4/scripts/mediamtx_gen_config.sh 2>/dev/null || true"

if ($PushOnly) {
    Write-Host "[PushOnly] skip service install"
    exit 0
}

Write-Host "[install] recover_nohup_adb.sh + orchestrator (ignore systemd deps) ..."
adb shell "bash /userdata/agent/scripts/recover_nohup_adb.sh"
adb shell "systemctl start --ignore-dependencies r1-orchestrator.service 2>/dev/null || true"

if (-not $NoForward) {
    adb forward tcp:8765 tcp:8765
    adb forward tcp:8766 tcp:8766
}

Write-Host ""
Write-Host "=== status ===" -ForegroundColor Cyan
adb shell "systemctl is-active r1-p4-eth r1-mediamtx r1-mediamtx-frame r1-vlm-daemon r1-orchestrator r1-webui 2>/dev/null || true"
if (Test-Path (Join-Path $AgentP "scripts\adb_board_diag.sh")) {
    adb shell "bash /userdata/agent/scripts/adb_board_diag.sh"
}
Write-Host "WebUI: http://127.0.0.1:8766/" -ForegroundColor Green
