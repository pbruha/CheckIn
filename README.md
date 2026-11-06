# CheckIn – docházka pro cvičení

Webová aplikace pro evidenci docházky na cvičení předmětu **Základy programátorské praxe**.
Učitel spustí docházku a studenti se zapisují naskenováním rotujícího QR kódu nebo zadáním krátkého kódu.
Studenti vidí svou docházku a zbývající absence, omlouvají se přes aplikaci.

**Pravidlo absencí:** student může mít nejvýše **6 neomluvených absencí**. Omluvená absence se nepočítá.

Návrh a plán vývoje: [docs/NAVRH.md](docs/NAVRH.md). Uživatelská wiki: [docs/wiki](docs/wiki/Home.md).

## Funkce

- **Učitel**: skupiny a hodiny, import studentů z CSV, spuštění docházky (QR kód i číselný kód), živý přehled,
  ruční úpravy, statistiky s upozorněním na limit absencí, export CSV, schvalování omluvenek.
- **Student**: zápis docházky (QR kód, kód, volitelně ověření polohy v učebně), přehled absencí, omluvenky s přílohou.
- **Zabezpečení**: podepsané rotující QR kódy, jedno zařízení = jeden student na hodinu, přihlášení školním účtem (OIDC),
  audit (čas, IP), mazání dat po akademickém roce.
- **Klienty**: PWA (instalace na počítač i telefon), desktopový spouštěč, Capacitor obal pro Android.
- **Mobilní upozornění**: Web Push (volitelné, vyžaduje VAPID klíče).

## Struktura repozitáře

```
CheckIn/
├── backend/            FastAPI API, databáze, migrace, testy
│   ├── app/            aplikace: modely, routery, bezpečnost, push, SSO, CLI
│   │   ├── routers/    endpointy: auth, academics, attendance, excuses, push, sso
│   │   ├── cli.py      správa účtů, purge dat, generování VAPID klíčů
│   │   └── ...         config, db, models, security, services, retention, sso, push
│   ├── migrations/     Alembic migrace (versions/)
│   ├── tests/          pytest: API, omluvenky, WebSocket, SSO, push, migrace, nasazení
│   ├── Dockerfile      image backendu (neprivilegovaný uživatel, migrace při startu)
│   └── requirements.txt
├── frontend/           React + TypeScript + Vite (PWA)
│   ├── src/pages/      obrazovky učitele a studenta
│   ├── src/lib/        API klient, autentizace, QR URL, geolokace, push, formátování
│   ├── public/         manifest, service worker, ikony
│   ├── nginx.conf      servírování aplikace a proxy /api na backend (včetně WebSocketů)
│   └── Dockerfile      build + nginx image
├── mobile/             Capacitor obal pro Android (iOS na Macu)
├── desktop/            spouštěč aplikace v samostatném okně (Windows, macOS, Linux)
├── docs/
│   ├── NAVRH.md        původní návrh aplikace
│   ├── DEPLOY.md       nasazení přes Docker Compose
│   └── wiki/           stránky uživatelské wiki a obrázky (img/)
├── .github/workflows/  CI/CD pipeline (testy, build, smoke test, volitelný deploy)
├── docker-compose.yml  služby db (PostgreSQL), backend, frontend (nginx)
└── .env.example        šablona konfigurace (kopírovat do .env, nekomitovat)
```

## Rychlý start

### Lokálně, bez Dockeru (vývoj)

```bash
# backend (výchozí SQLite)
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python -m app.cli create-user --email ucitel@skola.cz --name "Jana" --role teacher --password "heslo"
uvicorn --factory app.main:create_app --reload          # http://127.0.0.1:8000/docs

# frontend (v druhém terminálu; /api se přeposílá na backend)
cd frontend
npm install
npm run dev                                              # http://localhost:5173
```

### Docker Compose

```bash
cp .env.example .env        # doplňte POSTGRES_PASSWORD a SECRET_KEY
docker compose up -d --build
```

Aplikace je na `http://localhost:8080`. Produkční nasazení za HTTPS viz [docs/DEPLOY.md](docs/DEPLOY.md).

## Testy a kontroly

| Co | Příkaz |
|---|---|
| Backend (včetně kontroly migrací) | `cd backend && python -m pytest -q` |
| Frontend: typy a build | `cd frontend && npm run build` |
| Frontend: unit testy | `cd frontend && npm test` |

CI na GitHub Actions spouští všechny kontroly a smoke test celého stacku při každém pushi.

## Dokumentace

- [docs/NAVRH.md](docs/NAVRH.md) – cíl, role, funkce, datový model, plán vývoje
- [docs/DEPLOY.md](docs/DEPLOY.md) – nasazení a údržba
- [backend/README.md](backend/README.md) – konfigurace, endpointy, bezpečnost, migrace
- [frontend/README.md](frontend/README.md) – spuštění, instalace jako PWA
- [mobile/README.md](mobile/README.md) – Android a iOS obal
- [desktop/README.md](desktop/README.md) – desktopový spouštěč
- [docs/wiki](docs/wiki/Home.md) – uživatelská příručka s ukázkami
