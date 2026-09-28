# Push InternVL models + rknn_InternVLM_demo to board (large ~3.3GB, one-time after userdata wipe)
param(
    [string]$ModelDir = "C:\Users\wwff\Documents\youyeetoo3588s\InternVL3_5-4B",
    [string]$RknnDemo = "C:\Users\wwff\Documents\youyeetoo3588s\rknn_InternVLM_demo"
)
$ErrorActionPreference = "Stop"
if (-not (Test-Path "$ModelDir\vision_InternVL3_5-4B.rknn")) {
    throw "Missing $ModelDir — set -ModelDir to InternVL3_5-4B folder"
}
adb devices | Select-String "device$" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "adb: no device" }

Write-Host "[models] -> /userdata/models/InternVL3_5-4B (several GB, be patient)"
adb shell "mkdir -p /userdata/models/InternVL3_5-4B /userdata/rknn_InternVLM_demo"
Get-ChildItem $ModelDir -File | ForEach-Object {
    Write-Host "  push $($_.Name) ($([math]::Round($_.Length/1MB,1)) MB)"
    adb push $_.FullName "/userdata/models/InternVL3_5-4B/$($_.Name)"
}

if (Test-Path $RknnDemo) {
    Write-Host "[rknn] -> /userdata/rknn_InternVLM_demo"
    adb push "$RknnDemo\lib" /userdata/rknn_InternVLM_demo/lib
    if (Test-Path "$RknnDemo\rknn_internvl3_demo") {
        adb push "$RknnDemo\rknn_internvl3_demo" /userdata/rknn_InternVLM_demo/rknn_internvl3_demo
        adb shell "chmod +x /userdata/rknn_InternVLM_demo/rknn_internvl3_demo"
    }
}

Write-Host "[models] verify:"
adb shell "ls -la /userdata/models/InternVL3_5-4B/ | head -10"
