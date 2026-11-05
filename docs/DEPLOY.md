# Nasazení CheckIn přes Docker Compose

Tři služby: `db` (PostgreSQL 16), `backend` (FastAPI, při startu aplikuje migrace) a `frontend`
(nginx se statickou aplikací, který přeposílá `/api` včetně WebSocketů na backend).
Na veřejnou síť je vystavený jen `frontend`.

## 1. Požadavky

- Docker Engine 24+ a Docker Compose v2.
- Doména (např. `checkin.skola.cz`) s HTTPS. Kamera, geolokace a Web Push v prohlížeči vyžadují HTTPS.
- HTTPS zajistí reverzní proxy před nginx kontejnerem (Caddy, Traefik, nginx na hostiteli, …).

## 2. Konfigurace

```bash
cp .env.example .env
openssl rand -hex 16   # POSTGRES_PASSWORD
openssl rand -hex 32   # SECRET_KEY
```

V `.env` vyplňte aspoň `POSTGRES_PASSWORD`, `SECRET_KEY` a `FRONTEND_URL=https://checkin.skola.cz`.
Produkční režim (`ENVIRONMENT=production`, nastavený v image) při startu zkontroluje, že je
`SECRET_KEY` dostatečně dlouhý, že se nepoužívá SQLite a že `FRONTEND_URL` a `OIDC_REDIRECT_URI`
jsou HTTPS. Jinak se služba nespustí a v logu je důvod.

Volitelně:
- **Školní přihlášení (OIDC)**: vyplňte `OIDC_*` a `SSO_ALLOWED_DOMAIN`. Adresu
  `https://checkin.skola.cz/api/auth/sso/callback` nechte zaregistrovat u poskytovatele přesně takto.
- **Mobilní upozornění**: `docker compose run --rm backend python -m app.cli vapid-keys` a hodnoty
  zkopírujte do `.env`.

## 3. Spuštění

```bash
docker compose up -d --build
docker compose ps            # všechny služby mají být healthy
docker compose logs backend  # ověřte "Running upgrade" a "Application startup complete"
```

Aplikace běží na `http://<server>:8080` (port nastavuje `HTTP_PORT`). Před ním musí být HTTPS proxy.

### Příklad: Caddy jako HTTPS proxy na hostiteli

```
checkin.skola.cz {
    reverse_proxy 127.0.0.1:8080
}
```

Caddy si certifikát vyžádá sám. WebSocket funguje bez dalšího nastavení.

## 4. Účty

Účty studentů vznikají importem CSV v aplikaci nebo přihlášením školním účtem. Učitele a admina
zakládá CLI:

```bash
docker compose exec backend python -m app.cli create-user --email ucitel@skola.cz \
    --name "Jana Učitelová" --role teacher --password "<silné heslo>"
```

## 5. Údržba

- **Aktualizace**: `git pull && docker compose up -d --build`. Migrace se aplikují automaticky při startu.
- **Zálohy**: databáze `docker compose exec db pg_dump -U checkin checkin > zaloha.sql`
  a složka příloh (volume `uploads`, `/data/uploads` v kontejneru). Zálohy obsahují osobní údaje,
  chraňte je.
- **Mazání dat po akademickém roce** (cron na hostiteli, např. 1. února v 3:00):
  ```bash
  docker compose exec backend python -m app.cli purge --before 2027-02-01 --scrub-audit-days 90
  ```
- **Logy**: `docker compose logs -f backend frontend`.

## 6. Bezpečnostní poznámky

- Služby `db` a `backend` nejsou přístupné z venku; jediný vstup je nginx.
- Kontejnery běží bez root práv (backend jako uživatel `app`); nginx používá oficiální image.
- Nginx posílá CSP, `X-Frame-Options: DENY` a `Permissions-Policy` jen pro kamera a poloha ze stejného původu.
- IP adresy studentů v auditu se berou z `X-Forwarded-For` od nginx. Backend je proto bezpečný jen
  za tímto nginx (port 8000 se nepublikuje).
- Tajné hodnoty patří jen do `.env` (je v `.gitignore`), ne do repozitáře.
