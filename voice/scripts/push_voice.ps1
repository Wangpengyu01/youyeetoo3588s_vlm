# Push voice scripts to board with Unix LF (CRLF breaks mic_arm MIC_ARM_TRIES)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path "$Root\voice\scripts\mic_arm.sh")) {
    $Root = "C:\Users\wwff\Documents\youyeetoo3588s"
}
$Board = "/userdata/voice/scripts"

Write-Host "[push-voice] $Root\voice\scripts -> $Board"
adb shell "mkdir -p $Board"

function Push-Lf($Local, $Remote) {
    $content = [System.IO.File]::ReadAllText($Local).Replace("`r`n", "`n").Replace("`r", "`n")
    $tmp = [IO.Path]::GetTempFileName()
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($tmp, $content, $utf8)
    adb push $tmp $Remote | Out-Null
    Remove-Item $tmp -Force
}

Get-ChildItem "$Root\voice\scripts" -File | ForEach-Object {
    Push-Lf $_.FullName "$Board/$($_.Name)"
}

adb shell "chmod +x $Board/*.sh 2>/dev/null"
Write-Host "[push-voice] done"
