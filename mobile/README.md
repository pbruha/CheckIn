# CheckIn – mobilní aplikace (Capacitor)

Nativní obal, který v okně zobrazí běžící webovou aplikaci CheckIn. Stejný kód jako PWA, jen s ikonou
v telefonu a bez prohlížečového panelu. Aplikace sama o sobě neobsahuje data; potřebuje běžící server.

## Požadavky
- Node.js 22, Android Studio (Android) nebo Xcode na Macu (iOS).
- Běžící CheckIn (viz `docs/DEPLOY.md`), na Androidu typicky na počítači v LAN.

## Android – postup
```bash
cd mobile
npm install
npx cap add android                       # jen poprvé: vytvoří složku android/
CHECKIN_URL=http://192.168.1.20:8080 npm run sync:android   # IP počítače se stackem
npx cap open android                      # otevře Android Studio → Run
```

- Telefon a počítač musí být ve stejné síti. Adresu počítače zjistíte příkazem `ip addr` nebo `ipconfig`.
- Dev adresa je `http://` (bez HTTPS). Kamera (QR) a geolokace v WebView na takové adrese obvykle
  **nefungují** – ověří se jen přihlášení, přehled, omluvenky a upozornění. Pro plný test použijte HTTPS
  adresu serveru (`CHECKIN_URL=https://checkin.skola.cz`).

## iOS
Vyžaduje Mac s Xcode: `npx cap add ios`, potom stejný `sync` a `npx cap open ios`.

## Změna adresy
Kdykoli spusťte `CHECKIN_URL=... npm run sync:android`. Adresa se zapisuje do `capacitor.config.json`.
