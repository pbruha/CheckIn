# CheckIn – desktopový spouštěč

Otevře CheckIn v samostatném okně bez adresního řádku, jako běžnou desktopovou aplikaci.
Běží v Chrome nebo Edge, které už na počítači máte. Nic se neinstaluje a nic se nesestavuje.

- **Windows**: `$env:CHECKIN_URL="http://localhost:8080"; .\launch.ps1`
- **macOS / Linux**: `CHECKIN_URL=http://localhost:8080 ./launch.sh`

Adresu serveru měňte přes `CHECKIN_URL`. Na HTTPS adrese funguje i QR skener a geolokace.
Alternativa bez spouštěče: v Chrome nebo Edge otevřete aplikaci a nainstalujte ji přes ikonu v adresním řádku.
Pro plnohodnotný obal s vlastní ikonou a instalátorem by bylo potřeba Electron nebo Tauri, který se musí sestavit na vašem počítači.
