# Otevře CheckIn v samostatném okně (Windows). Použití: $env:CHECKIN_URL="http://localhost:8080"; .\launch.ps1
$url = if ($env:CHECKIN_URL) { $env:CHECKIN_URL } else { "http://localhost:8080" }
$profile = Join-Path $env:LOCALAPPDATA "CheckIn-Desktop"
$candidates = @(
  "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
  "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
  "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
  "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
)
$browser = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $browser) { Write-Error "Nenalezen Chrome ani Edge."; exit 1 }
Start-Process -FilePath $browser -ArgumentList "--app=$url", "--user-data-dir=`"$profile`"", "--no-first-run", "--window-size=1200,820"
