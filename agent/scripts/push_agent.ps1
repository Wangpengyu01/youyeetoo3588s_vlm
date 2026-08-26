# Push agent scripts to board (Windows)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path "$Root\agent\scripts\llm_client.py")) {
    $Root = "C:\Users\wwff\Documents\youyeetoo3588s"
}
$Board = "/userdata/agent"

Write-Host "[push] $Root\agent -> $Board"

adb shell "mkdir -p $Board/bin $Board/scripts $Board/config $Board/logs $Board/run"

function Push-Lf($Local, $Remote) {
    $content = [System.IO.File]::ReadAllText($Local).Replace("`r`n", "`n")
    $tmp = [IO.Path]::GetTempFileName()
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($tmp, $content, $utf8)
    adb push $tmp $Remote | Out-Null
    Remove-Item $tmp -Force
}

Get-ChildItem "$Root\agent\scripts" -Filter "*.py" | ForEach-Object {
    Push-Lf $_.FullName "$Board/scripts/$($_.Name)"
}
Get-ChildItem "$Root\agent\scripts" -Filter "*.sh" | ForEach-Object {
    Push-Lf $_.FullName "$Board/scripts/$($_.Name)"
}
Push-Lf "$Root\agent\config\agent.yaml" "$Board/config/agent.yaml"

adb shell "chmod +x $Board/scripts/*.sh 2>/dev/null; chmod +x $Board/bin/* 2>/dev/null; ls -la $Board/scripts/"

if (Test-Path "$Root\agent\bin\llm_daemon") {
    adb push "$Root\agent\bin\llm_daemon" "$Board/bin/llm_daemon"
    adb shell "chmod +x $Board/bin/llm_daemon"
    Write-Host "[push] llm_daemon binary pushed"
} else {
    Write-Host "[push] no agent/bin/llm_daemon — compile on Linux VM first (agent/docs/BUILD_LINUX.md)"
}

Write-Host "[push] done. Test: adb shell bash $Board/scripts/phase_a_test.sh"
