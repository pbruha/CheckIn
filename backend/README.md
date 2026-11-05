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
| `ABSENCE_LIMIT` | `2` | povolený počet neomluvených absencí |
| `TOKEN_TTL_HOURS` | `12` | platnost přihlášení |
| `UPLOAD_DIR` | `./uploads` | složka pro přílohy omluvenek (zálohovat, nepublikovat) |
| `MAX_UPLOAD_BYTES` | `5242880` | maximální velikost přílohy (5 MB) |

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

Omluvenka: schválená se u běžící hodiny promítne při uzavření, u uzavřené hodiny okamžitě.
Omluvená absence se nepočítá do limitu.

Zatím neimplementováno (plán verze 3): geofence, SSO, WebSockety
(živý přehled je zatím přes dotaz/polling), mazání dat po roce.
