# CheckIn – backend (MVP)

REST API pro docházku podle [návrhu](../docs/NAVRH.md). Postaveno na FastAPI a SQLAlchemy;
ve vývoji běží na SQLite, v produkci se přepne na PostgreSQL změnou `DATABASE_URL`.

## Spuštění

```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

# vytvoření účtu vyučujícího (účty studentů vznikají importem z CSV)
python -m app.cli create-user --email ucitel@skola.cz --name "Jana Nováková" --role teacher --password tajne

uvicorn --factory app.main:create_app --reload
# API dokumentace: http://127.0.0.1:8000/docs
```

## Konfigurace (proměnné prostředí)

| Proměnná | Výchozí | Význam |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./checkin.db` | např. `postgresql+psycopg://user:pass@host/checkin` |
| `SECRET_KEY` | `dev-secret-change-me` | podpis tokenů a QR kódů – **v produkci nastavit!** |
| `QR_WINDOW_SECONDS` | `15` | perioda rotace QR kódu |
| `CODE_TTL_SECONDS` | `60` | platnost číselného kódu |
| `LATE_MINUTES` | `10` | hranice pro pozdní příchod |
| `ABSENCE_LIMIT` | `6` | povolený počet neomluvených absencí (omluvená se nepočítá) |
| `TOKEN_TTL_HOURS` | `12` | platnost přihlášení |
| `UPLOAD_DIR` | `./uploads` | složka pro přílohy omluvenek (zálohovat, nepublikovat) |
| `MAX_UPLOAD_BYTES` | `5242880` | maximální velikost přílohy (5 MB) |
| `OIDC_ISSUER` | – | adresa OpenID Connect poskytovatele; **nastavením se zapne přihlášení školním účtem** |
| `OIDC_CLIENT_ID` / `OIDC_CLIENT_SECRET` | – | registrace aplikace u poskytovatele (secret je volitelný u veřejného klienta) |
| `OIDC_REDIRECT_URI` | – | přesná adresa callbacku, např. `https://checkin.skola.cz/api/auth/sso/callback` (musí být registrována) |
| `OIDC_SCOPES` | `openid email profile` | požadované scope |
| `SSO_ALLOWED_DOMAIN` | – | volitelně omezí přihlášení na e-maily z této domény (např. `skola.cz`) |
| `SSO_PASSWORD_LOGIN` | `1` | `0` vypne přihlašování heslem, když je SSO zapnuté |
| `FRONTEND_URL` | `http://localhost:5173` | kam se přesměrovat po přihlášení (ve výrobě stejná doména) |

## Databáze a migrace

Produkce: `alembic upgrade head` (s `DATABASE_URL`). Test `tests/test_migrations.py` hlídá, že migrace
odpovídají modelům – při změně modelu přidejte revizi: `alembic revision --autogenerate -m "popis"`.

Mazání dat po akademickém roce (spouštět ručně nebo z cronu):

```bash
python -m app.cli purge --before 2027-02-01 --scrub-audit-days 90
```

Smaže hodiny před datem včetně docházky, omluvenek a příloh; u zbylých záznamů starších než N dní
vynuluje IP adresy a otisky zařízení. Účty studentů zůstávají (smazání účtu je samostatný krok).

## Mobilní upozornění (Web Push)

Klíče vytvoříte příkazem `python -m app.cli vapid-keys` (vypíše dvojici `VAPID_PRIVATE_KEY` a
`VAPID_PUBLIC_KEY`, které k sobě patří). Bez nich je funkce vypnutá a tlačítko se nezobrazí.
Upozornění chodí: učiteli při nové omluvence, studentovi při rozhodnutí o omluvence. Odběry se ukládají
per zařízení a neplatné (404/410 od push služby) se automaticky smažou.

Ověřeno: podepsání a šifrování požadavku (`tests/test_push_sender.py`) a registrace odběru v prohlížeči
v produkčním buildu. **Doručení na skutečné zařízení neověřeno** (v testovacím prostředí nejsou
push služby prohlížečů dosažitelné). Před nasazením otestujte na telefonu přes HTTPS.

## Živý přehled (WebSocket)

`WS /ws/sessions/{id}/attendance` – po připojení pošlete `{"token": "..."}`. Server posílá stav hodiny
při každé změně (kontrola každou sekundu). Běží v jednom procesu bez sdíleného stavu, takže
funguje i s více workery (každý spoj kontroluje DB sám).


Schéma se zatím vytváří přes `create_all`, který **nepřidává sloupce do existujících tabulek**.
Při změně modelu proto u vývojové databáze smažte soubor a vytvořte ji znovu. Před nasazením
(verze s reálnými daty) je nutné zavést migrace (Alembic).

## Testy

```bash
cd backend && python -m pytest -q
```

## Přehled endpointů

| Metoda a cesta | Kdo | Účel |
|---|---|---|
| `POST /auth/login` | všichni | přihlášení, vrací token |
| `GET /auth/me` | přihlášený | údaje o sobě |
| `POST /courses`, `GET /courses` | učitel / přihlášený | předměty |
| `POST /courses/{id}/groups` | učitel | skupina (cvičení) |
| `GET /me/groups` | přihlášený | skupiny, které vyučuje nebo do nich chodí |
| `POST /groups/{id}/students/import` | učitel | import CSV (`email,name`), text/csv v těle |
| `POST /groups/{id}/sessions`, `GET /groups/{id}/sessions` | učitel / přihlášený | hodiny |
| `POST /sessions/{id}/start` | učitel | spuštění docházky |
| `POST /sessions/{id}/close` | učitel | ruční uzavření (po konci hodiny se uzavře automaticky) |
| `GET /sessions/{id}/qr` | učitel | aktuální rotující QR token + číselný kód |
| `POST /attendance/checkin` | student | zápis přes QR token nebo číselný kód |
| `PUT /sessions/{id}/attendance/{user_id}` | učitel | ruční úprava stavu |
| `GET /sessions/{id}/attendance` | učitel | živý přehled hodiny |
| `GET /groups/{id}/export.csv` | učitel | export docházky skupiny |
| `GET /groups/{id}/stats` | učitel | účast po studentech i hodinách, limit absencí |

## Ochrana proti podvádění (co je implementováno)

- **Rotující QR token** – HMAC podpis `session_id + časové okno`, platí v aktuálním a předchozím okně (cca 15–30 s).
- **Číselný kód** – 6 míst, platnost 60 s, uložen jen do konce platnosti.
- **Jedno zařízení = jeden student na hodinu** – ukládá se HMAC otisku zařízení, nikoli jeho identifikátor.
- **Audit** – u každého zápisu čas, způsob a IP adresa.
- **Zápis jen zapsaným studentům** a jen v běžící hodině.
- **Geofence učebny** (volitelná) – učitel nastaví polohu a poloměr; při check-inu se ověří vzdálenost
  (haversine). Nepřesná poloha (přesnost horší než 100 m) se odmítne. Souřadnice studenta se
  neukládají, do databáze jde jen výsledek `geo_verified`. GPS neposkytuje absolutní jistotu, takže
  jde o překážku, ne o úplnou ochranu.

Omluvenka: schválená se u běžící hodiny promítne při uzavření, u uzavřené hodiny okamžitě.
Omluvená absence se nepočítá do limitu.

## Přihlášení školním účtem (SSO)

Implementováno jako **OpenID Connect** (authorization code + PKCE, ověření podpisu id_tokenu přes JWKS,
kontrola `iss`, `aud`, `exp` a `nonce`). Stav přihlášení je v podepsané, krátkodobé cookie.
Účet se najde podle e-mailu; nový uživatel vzniká jako student bez hesla. Role učitele se přiřazuje
ručně (CLI). **SAML zatím není podporováno.**

Test bez skutečného IdP: `tests/test_sso.py` (falešný poskytovatel s vlastním klíčem).

Zatím neimplementováno (plán verze 3): mobilní push notifikace
(živý přehled je zatím přes dotaz/polling), mazání dat po roce.
