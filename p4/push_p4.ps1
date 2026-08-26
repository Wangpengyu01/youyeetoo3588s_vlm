# Push P4 to board (Windows). Converts CRLF -> LF before push.

$src = "C:\Users\wwff\Documents\youyeetoo3588s\p4"
Get-ChildItem -Recurse $src -Include *.sh,*.py,*.md | ForEach-Object {
    $c = [IO.File]::ReadAllText($_.FullName) -replace "`r`n", "`n"
    [IO.File]::WriteAllText($_.FullName, $c)
}
adb push $src /userdata/
adb shell "chmod +x /userdata/p4/scripts/*.sh /userdata/p4/scripts/*.py"
Write-Host "Pushed to /userdata/p4/"
