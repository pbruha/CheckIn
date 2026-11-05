# CheckIn – frontend (React PWA)

Webová aplikace pro učitele i studenty. Běží na mobilu i počítači bez instalace; po nasazení na HTTPS ji lze přidat na plochu.

## Spuštění

Nejdřív spusťte backend (viz [../backend/README.md](../backend/README.md)) na portu 8000, pak:

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 – /api se přesměrovává na backend
```

## Skripty

| Příkaz | Co dělá |
|---|---|
| `npm run dev` | vývojový server s proxy na backend |
| `npm run build` | kontrola typů + produkční build do `dist/` |
| `npm test` | jednotkové testy (Vitest) |

## Nasazení

Produkční build je statický. Server musí na stejné doméně servovat `dist/` a přeposílat `/api/*` na backend
(bez prefixu `/api`). Kamera pro skenování QR kódů vyžaduje HTTPS nebo `localhost`.

## Obrazovky

- **Učitel**: přehled skupin a hodin, spuštění docházky, obrazovka s rotujícím QR kódem a číselným kódem,
  živý přehled s ručními úpravami, statistiky a export CSV, import studentů z CSV.
- **Student**: vlastní docházka a zbývající absence, zápis přes skenování QR kódu, nebo zadání číselného kódu.

Odkaz v QR kódu míří na `/student/checkin?s=<hodina>&t=<token>`; přihlášený student se zapíše automaticky.

## Poznámky

- Přihlašovací token je uložen v `localStorage` (a při chybě 401 se uživatel odhlásí).
- ID zařízení pro kontrolu „jedno zařízení = jeden student“ je také v `localStorage`.
- Service worker cachuje jen aplikační shell; API odpovědi se nikdy necachují.
