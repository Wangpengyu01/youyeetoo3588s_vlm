# Windows: set RNDIS USB adapter on same subnet as board (192.168.7.1 shared).
# Run in Admin PowerShell after board install_rndis_usb.sh
$ifDesc = "Remote NDIS Compatible Device", "RNDIS", "USB Ethernet", "Android"
$adapters = Get-NetAdapter | Where-Object { $d = $_.InterfaceDescription; $ifDesc | Where-Object { $d -like "*$_*" } }
if (-not $adapters) {
  Write-Host "No RNDIS adapter found. Check Device Manager after USB connect."
  exit 1
}
$nic = $adapters | Select-Object -First 1
Write-Host "Using $($nic.Name) — setting 192.168.7.2/24"
Remove-NetIPAddress -InterfaceAlias $nic.Name -Confirm:$false -ErrorAction SilentlyContinue
New-NetIPAddress -InterfaceAlias $nic.Name -IPAddress 192.168.7.2 -PrefixLength 24 -ErrorAction Stop
Write-Host "Test: ping 192.168.7.1"
ping -n 2 192.168.7.1
Write-Host "WebUI: http://192.168.7.1:8766"
