# Návrh aplikace pro docházku – Základy programátorské praxe

## 1. Cíl aplikace

Rychle a spolehlivě zaznamenávat docházku studentů na hodiny předmětu *Základy programátorské praxe*, omezit podvádění a dát učiteli i studentům přehled o účasti.

## 2. Uživatelské role

| Role | Popis | Hlavní oprávnění |
|---|---|---|
| **Učitel / cvičící** | Spravuje předmět, skupiny a hodiny | Vytváření hodin, spuštění docházky, úpravy záznamů, schvalování omluvenek, export dat |
| **Student** | Účastník předmětu | Přihlášení na hodinu, vlastní přehled docházky, nahrání omluvenky |
| **Administrátor** | Správa systému | Správa účtů, import studentů ze školního systému, nastavení pravidel |

## 3. Funkční požadavky

### 3.1 Pro učitele
- Vytvoření předmětu, skupin (cvičení) a rozvrhu hodin.
- Import studentů z CSV nebo ze školního systému.
- Spuštění docházky jedním tlačítkem – zobrazí se **rotující QR kód** (mění se každých 10–15 s).
- Alternativa: krátký **číselný kód** platný 60 s, nebo **ruční zaškrtání** přítomných.
- Živý přehled přítomných během hodiny.
- Ruční úpravy záznamu: přítomen, nepřítomen, pozdní příchod, omluven.
- Schvalování omluvenek.
- Statistiky: účast po studentech i po hodinách, upozornění na studenty nad limitem absencí.
- Export do CSV / Excelu.

### 3.2 Pro studenty
- Přihlášení školním účtem (SSO).
- Naskenování QR kódu nebo zadání číselného kódu.
- Přehled vlastní docházky a zbývajících povolených absencí.
- Nahrání omluvenky (text + příloha).
- Notifikace při blížícím se limitu absencí.

### 3.3 Pro administrátora
- Správa účtů a rolí.
- Import studentů ze školního systému.
- Nastavení pravidel (limit absencí, hranice pozdního příchodu, …).

## 4. Ochrana proti podvádění

1. **Rotující QR kód** – token podepsaný HMAC s krátkou platností (10–15 s). Snímek obrazovky nebo fotka kódu od spolužáka tak po chvíli nefunguje.
2. **Ověření polohy** (volitelné) – geofence učebny, případně kontrola připojení na školní Wi-Fi.
3. **Jedno zařízení = jeden student na hodinu** – otisk zařízení (device fingerprint) se váže k záznamu; druhý student stejným zařízením se nezapíše.
4. **Audit** – u každého záznamu se ukládá čas a IP adresa.

> Poznámka: Otisk zařízení ani IP adresa nejsou stoprocentní ochrana (lze je obejít), jsou to ale přiměřená překážka pro běžné podvádění. Součástí řešení by měla být i kontrola nesrovnalostí učitelem.

## 5. Architektura

| Vrstva | Technologie | Poznámka |
|---|---|---|
| Frontend | **PWA** v Reactu nebo Vue | Funguje na mobilu i počítači bez instalace |
| Backend | **REST API** – FastAPI / Django (Python) nebo NestJS (Node.js) | Doporučení: FastAPI pro rychlý start a snadné testování |
| Databáze | **PostgreSQL** | |
| Real-time | **WebSockety** | Živý přehled přítomných během hodiny |
| Autentizace | **SSO školy** (OAuth2 / SAML), role-based přístup | Ve verzi MVP lokální účty pro vývoj |
| Nasazení | **Docker**, školní server nebo cloud | |

## 6. Datový model

```
User        (id, jméno, e-mail, role)                      role: student | ucitel | admin
Course      (id, název, semestr)
Group       (id, course_id, název, vyučující_id → User)   skupina / cvičení
Enrollment  (user_id → User, group_id → Group)             zápis studenta do skupiny
Session     (id, group_id → Group, datum, začátek, konec,
             stav)                                         stav: připravena | probíhá | uzavřena
Attendance  (session_id → Session, user_id → User,
             stav, čas_záznamu, způsob, zařízení)          stav: přítomen | nepřítomen | pozdě | omluven
                                                           způsob: qr | kód | ruční
                                                           PK (session_id, user_id)
Excuse      (id, user_id → User, session_id → Session,
             text, příloha, stav_schválení)                stav: čeká | schváleno | zamítnuto
```

Doplňující poznámky:
- `Attendance` má složený primární klíč `(session_id, user_id)`, takže jeden student nemůže mít v jedné hodině dva záznamy.
- Otisk zařízení a IP adresa jsou uloženy v `Attendance` jako audit a podléhají mazání podle sekce 9.
- Token QR kódu se neukládá do databáze; ověřuje se podpisem (HMAC) a časovým razítkem.

## 7. Hlavní obrazovky

1. **Přihlášení** – SSO, ve vývoji lokální přihlášení.
2. **Dashboard učitele** – dnešní hodiny, tlačítko *Spustit docházku*.
3. **Obrazovka s QR kódem** – rotující kód, alternativní číselný kód, živý počet přítomných.
4. **Detail hodiny** – seznam studentů a jejich stavů, ruční úpravy.
5. **Statistiky předmětu** – účast po studentech a hodinách, upozornění na limit.
6. **Dashboard studenta** – moje docházka, tlačítko *Skenovat*.
7. **Omluvenky** – přehled, nahrání nové, stav schválení.

## 8. Pravidla a nastavení

- **Limit povolených absencí** – např. 2 neomluvené absence; po překročení se zobrazí upozornění.
- **Hranice pro pozdní příchod** – např. 10 minut od začátku hodiny.
- **Automatické uzavření docházky** – po skončení hodiny se docházka sama uzavře.
- Pravidla nastavuje administrátor nebo učitel na úrovni předmětu.

## 9. Ochrana osobních údajů (GDPR)

- **Minimalizace dat** – ukládá se jen nezbytné minimum.
- **Poloha se neukládá trvale** – ověření geofence proběhne jen v okamžiku zápisu, výsledek se uloží jako booleovská hodnota.
- **Přístup k datům** – pouze vyučující daného předmětu a sám student k vlastním záznamům.
- **Mazání dat** – data (včetně IP adres a otisků zařízení) se smažou po skončení akademického roku.

## 10. Plán vývoje

1. **MVP (2–3 týdny)** – přihlášení, předměty, ruční docházka, QR kód, export.
2. **Verze 2** – omluvenky, statistiky, notifikace.
3. **Verze 3** – geofence, SSO integrace, mobilní notifikace.

## 11. Bonus pro výuku

Protože jde o předmět programátorské praxe, mohou studenti aplikaci sami rozvíjet jako **semestrální projekt**:
- práce s Gitem (větve, pull requesty),
- code review,
- automatizované testy,
- CI/CD pipeline nad reálným produktem.

## 12. Otevřené otázky

- Který školní systém a jaké SSO protokoly (OAuth2 / SAML) jsou k dispozici?
- Je k dispozici školní Wi-Fi nebo se použije jen geofence?
- Kdo má roli administrátora a kdo spravuje import studentů?
- Jaký je přesný limit absencí a pravidlo pro pozdní příchod v předmětu?
