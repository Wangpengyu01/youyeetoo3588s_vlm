# Build r1_demo_recovery.zip for demo / ASHANGU PCs (run on dev machine with full repo)
param(
    [string]$RepoRoot = "",
    [string]$OutZip = ""
)
$ErrorActionPreference = "Stop"
$PackRoot = $PSScriptRoot
if (-not $RepoRoot) {
    $RepoRoot = (Resolve-Path (Join-Path $PackRoot "..\..\..")).Path
} else {
    $RepoRoot = (Resolve-Path $RepoRoot).Path
}
if (-not $OutZip) {
    $OutDir = Join-Path $RepoRoot "dist"
    New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
    $OutZip = Join-Path $OutDir "r1_demo_recovery.zip"
}

$Staging = Join-Path $env:TEMP "r1_demo_recovery_staging"
if (Test-Path $Staging) { Remove-Item $Staging -Recurse -Force }
New-Item -ItemType Directory -Force -Path $Staging | Out-Null

$DestPack = Join-Path $Staging "r1_demo_recovery"
New-Item -ItemType Directory -Force -Path $DestPack | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $DestPack "payload\agent") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $DestPack "payload\p4") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $DestPack "payload\voice") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $DestPack "bin") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $DestPack "config") | Out-Null
Copy-Item (Join-Path $PackRoot "recover.bat") $DestPack -Force
Copy-Item (Join-Path $PackRoot "recover.ps1") $DestPack -Force
Copy-Item (Join-Path $PackRoot "build_recovery_zip.ps1") $DestPack -Force
Copy-Item (Join-Path $PackRoot "bin\README.txt") (Join-Path $DestPack "bin\README.txt") -Force -ErrorAction SilentlyContinue
Copy-Item (Join-Path $PackRoot "config\rtsp.env.example") (Join-Path $DestPack "config\rtsp.env.example") -Force -ErrorAction SilentlyContinue

$ExcludeDir = @('__pycache__', '.git', 'tests', 'node_modules', '.venv', 'venv')
function Copy-Tree($Src, $Dst) {
    if (-not (Test-Path $Src)) { return }
    Get-ChildItem $Src -Recurse -Force | Where-Object {
        $rel = $_.FullName.Substring($Src.Length)
        -not ($ExcludeDir | Where-Object { $rel -match [regex]::Escape("\$_") -or $rel -match "/$_" })
    } | ForEach-Object {
        if ($_.PSIsContainer) { return }
        if ($_.Length -gt 200MB) { Write-Host "skip large: $($_.Name)"; return }
        $ext = $_.Extension.ToLower()
        $allow = @('.py', '.sh', '.yaml', '.yml', '.md', '.service', '.html', '.svg', '.desktop', '.xml', '.ps1', '.json', '.txt', '.example', '.env')
        if ($allow -notcontains $ext -and $_.DirectoryName -notmatch '\\bin\\') { return }
        $target = Join-Path $Dst ($_.FullName.Substring($Src.Length).TrimStart('\', '/'))
        $dir = Split-Path $target -Parent
        if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
        Copy-Item $_.FullName $target -Force
    }
}

Write-Host "[build] copy agent/p4/voice from $RepoRoot"
Copy-Tree (Join-Path $RepoRoot "agent") (Join-Path $DestPack "payload\agent")
Copy-Tree (Join-Path $RepoRoot "p4") (Join-Path $DestPack "payload\p4")
Copy-Tree (Join-Path $RepoRoot "voice") (Join-Path $DestPack "payload\voice")

$RtspEx = Join-Path $RepoRoot "p4\config\rtsp.env.example"
if (Test-Path $RtspEx) {
    Copy-Item $RtspEx (Join-Path $DestPack "config\rtsp.env.example")
    if (-not (Test-Path (Join-Path $DestPack "config\rtsp.env"))) {
        Copy-Item $RtspEx (Join-Path $DestPack "config\rtsp.env")
    }
}
$RtspReal = Join-Path $RepoRoot "p4\config\rtsp.env"
if (Test-Path $RtspReal) {
    Copy-Item $RtspReal (Join-Path $DestPack "config\rtsp.env")
    Write-Host "[build] included config/rtsp.env (camera credentials)"
}

foreach ($bin in @("vlm_daemon", "llm_daemon")) {
    $b = Join-Path $RepoRoot "agent\bin\$bin"
    if (Test-Path $b) {
        Copy-Item $b (Join-Path $DestPack "bin\$bin")
        Write-Host "[build] included bin/$bin"
    }
}
Get-ChildItem $RepoRoot -Filter "mediamtx*.tar.gz" -ErrorAction SilentlyContinue | ForEach-Object {
    Copy-Item $_.FullName (Join-Path $DestPack "bin\$($_.Name)")
    Write-Host "[build] included bin/$($_.Name)"
}
Get-ChildItem (Join-Path $RepoRoot "p4\tmp") -Filter "mediamtx*.tar.gz" -ErrorAction SilentlyContinue | ForEach-Object {
    Copy-Item $_.FullName (Join-Path $DestPack "bin\$($_.Name)")
}

$Readme = Join-Path $DestPack "README.txt"
@'
R1 userdata 一键恢复包
======================

1. 解压到任意目录（路径勿含中文空格亦可）
2. 可选：把 mediamtx_*_linux_arm64.tar.gz 放入 bin\
3. 可选：把 vlm_daemon、llm_daemon 放入 bin\（或 payload 已含则跳过）
4. 必须：config\rtsp.env（摄像头 RTSP，可从 rtsp.env.example 复制修改）
5. USB 连接板子，双击 recover.bat

仅 push 不装服务: recover.bat 同目录下执行
  powershell -ExecutionPolicy Bypass -File recover.ps1 -PushOnly

打包本 zip（开发机）:
  powershell -ExecutionPolicy Bypass -File build_recovery_zip.ps1

'@ | Set-Content $Readme -Encoding UTF8

if (Test-Path $OutZip) { Remove-Item $OutZip -Force }
Compress-Archive -Path (Join-Path $Staging "r1_demo_recovery") -DestinationPath $OutZip -CompressionLevel Optimal
Remove-Item $Staging -Recurse -Force

Write-Host ""
Write-Host "Created: $OutZip" -ForegroundColor Green
$size = [math]::Round((Get-Item $OutZip).Length / 1MB, 2)
Write-Host "Size: ${size} MB"
Write-Host "After unzip on demo PC, also run on dev PC (once per wiped board):"
Write-Host "  .\agent\scripts\push_models_adb.ps1"
Write-Host "  .\agent\scripts\push_voice_assets_adb.ps1"
Write-Host "Then recover.bat — or fix_after_stuck.bat if hung."
