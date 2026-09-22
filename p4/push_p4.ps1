# Push P4 to board (Windows). Converts CRLF -> LF before push.
$ErrorActionPreference = "Stop"
$src = $PSScriptRoot
if (-not (Test-Path "$src\scripts\p4_env.sh")) {
    throw "Expected p4 scripts under $src"
}

Get-ChildItem -Recurse $src -Include *.sh,*.py,*.md,*.env,*.example | ForEach-Object {
    $c = [IO.File]::ReadAllText($_.FullName) -replace "`r`n", "`n"
    [IO.File]::WriteAllText($_.FullName, $c)
}
adb push $src /userdata/
adb shell "chmod +x /userdata/p4/scripts/*.sh /userdata/p4/scripts/*.py 2>/dev/null; true"
Write-Host "Pushed to /userdata/p4/"
