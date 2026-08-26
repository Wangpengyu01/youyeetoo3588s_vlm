# 在本机重建 Cursor Canvas 硬链接（clone 后执行一次）
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$RepoFile = Join-Path $Root "canvases\r1-vlm-agent-roadmap.canvas.tsx"
if (-not (Test-Path $RepoFile)) {
  Write-Error "Canvas not found: $RepoFile"
}

$Targets = @(
  "$env:USERPROFILE\.cursor\projects\c-Users-wwff-Documents-youyeetoo3588s\canvases\r1-vlm-agent-roadmap.canvas.tsx",
  "$env:USERPROFILE\.cursor\projects\empty-window\canvases\r1-vlm-agent-roadmap.canvas.tsx"
)

foreach ($Dst in $Targets) {
  $Dir = Split-Path -Parent $Dst
  New-Item -ItemType Directory -Force -Path $Dir | Out-Null
  if (Test-Path $Dst) {
    $item = Get-Item $Dst
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
      Remove-Item $Dst -Force
    } elseif ($item.Length -ne (Get-Item $RepoFile).Length) {
      Write-Warning "Skip (exists, not same file): $Dst"
      continue
    } else {
      continue
    }
  }
  cmd /c mklink /H "$Dst" "$RepoFile" | Out-Null
  Write-Host "Linked: $Dst"
}

Write-Host "Done. Edit canvases/r1-vlm-agent-roadmap.canvas.tsx in repo."
