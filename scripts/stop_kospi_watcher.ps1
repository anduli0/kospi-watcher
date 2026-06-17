# Stop KOSPI-WATCHER services (API 18080, web 3000, worker).
$ErrorActionPreference = "SilentlyContinue"

foreach ($port in 18080, 3000) {
  Get-NetTCPConnection -LocalPort $port -State Listen -EA SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique |
    ForEach-Object { Stop-Process -Id $_ -Force; Write-Host "stopped pid $_ (port $port)" }
}

Get-CimInstance Win32_Process -Filter "Name='python.exe'" -EA SilentlyContinue |
  Where-Object { $_.CommandLine -like '*worker*main.py*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Host "stopped worker pid $($_.ProcessId)" }

Write-Host "stopped."
