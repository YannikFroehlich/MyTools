# 🧰 MyTools

**MyTools** ist ein persönliches Django-Dashboard für Alltag, Homelab, Medien, Streaming, kleine Web-Tools und Multiplayer-Mini-Games.

Die App bündelt eigene Startseiten-Verknüpfungen, Widgets, Profile, Freunde, Chats, Notizen, Datei-Share, Rechner, Konverter, API-Tools, Spiele, Roadmap, Achievements, Moderation und Admin-/Security-Funktionen in einer modernen Oberfläche mit **Dark Mode**, **Theme-Anpassung**, **PWA-Support** und **deutscher/englischer Oberfläche**.

Stand dieser README: **24.06.2026**

---

## ✅ Aktueller technischer Stand

| Bereich | Stand |
|---|---|
| Backend | Django **5.2.15** |
| Realtime | Django Channels + Daphne |
| Datenbank | PostgreSQL produktiv, SQLite optional lokal/Tests |
| Cache / WebSockets | Redis / channels-redis |
| Reverse Proxy | Caddy |
| Deployment | Docker Compose + optional Cloudflare Tunnel |
| CI/CD | GitHub Actions, Self-hosted Runner, Tests/Build/Deploy |
| Sprachen | Deutsch / Englisch über Django i18n |
| PWA | Manifest, Service Worker und Offline-Seite |

Produktiv läuft der Web-Container aktuell über **Daphne** (`MyTools.asgi:application`), damit normale Django-Views und WebSocket-/Realtime-Funktionen zusammen funktionieren.

---

## 🆕 Neueste größere Änderungen

- **Git-Changelog statt manueller Einträge**: Die Seite `/changelog/` zeigt nur noch Änderungen aus dem Git-Repository. Die JSON-Datei wird über `scripts/generate_git_changelog.py` erzeugt.
- **Changelog-Paginierung**: Git-Änderungen werden mit **20 Commits pro Seite** angezeigt. Die Seitennavigation sitzt unten im Changelog-Bereich und nicht im normalen Header.
- **Umlaut-/Mojibake-Fix**: Git-Commit-Texte werden beim Anzeigen bereinigt, damit kaputte Zeichen wie `Ã¼` nicht mehr sichtbar sind.
- **Shortcut-Farben**: Jede Home-Verknüpfung kann eine eigene Farbe bekommen, unabhängig von der Bereichsfarbe.
- **Erweiterte Home-Widgets**: Neben Wetter, Uhr, Notizen und Statistik gibt es Widgets für Chat, Freunde, Skribble, Tic Tac Toe, Stadt Land Fluss, Uno, Kniffel, Datei-Share, Budget, Favoriten, Roadmap, Inbox und Changelog.
- **Home-Onboarding**: Neue Nutzer können beim ersten Start eine Vorlage wählen, z. B. Alltag, Gaming oder Homelab.
- **Access-Control überarbeitet**: Tools und Spiele können als **Veröffentlicht**, **Unveröffentlicht** oder **Versteckt** markiert werden. `Niemand` bleibt nur noch als Legacy-Wert erhalten und wird intern wie unveröffentlicht behandelt.
- **Papierkorb**: Gelöschte unterstützte Inhalte werden erst in den Papierkorb verschoben und können wiederhergestellt oder endgültig gelöscht werden.
- **Neue/erweiterte Spiele**: Werwolf, Hangman, Uno, Kniffel, Pong, Cookie Cosmos V2 und Nebula Forge Tycoon sind in der Plattform integriert.
- **Deployment-Workflow**: Beim Deploy auf `main` wird der Git-Changelog erzeugt, danach werden Container neu gebaut/gestartet.

---

## ✨ Hauptfunktionen

### 🏠 Startseite & Shortcuts

Die Startseite ist die zentrale Oberfläche für eigene Links, lokale Dienste und kleine Status-Karten.

- eigene Shortcut-Bereiche/Kategorien
- eigene Verknüpfungen mit URL, FontAwesome-Icon oder Bild
- eigene Farbe pro Bereich und pro Shortcut
- Favoriten
- Drag-and-drop-Sortierung für Bereiche und Shortcuts
- einklappbare Bereiche
- Quick-Actions für Suche, Widgets, Favoriten, Design und Changelog
- Onboarding-Vorlagen für Alltag, Gaming und Homelab
- mobile Bottom-Navigation mit Header-Toggle
- globale Suche per Button oder `Ctrl + K`

Typische Links:

- CasaOS
- Home Assistant
- Nextcloud
- Crafty
- GitHub / GitLab
- interne Homelab-Dienste
- Dokumentationen

---

### 🧩 Home-Widgets

Unterstützte Widget-Typen:

- Wetter
- Notizen
- Human Benchmark
- Schnellstatistiken
- Uhr
- Chats
- Freunde
- Skribble
- Tic Tac Toe
- Stadt Land Fluss
- Uno
- Kniffel
- Datei-Share
- Budget
- Favoriten
- Roadmap
- Inbox
- Changelog

Widgets können aktiviert/deaktiviert, sortiert und farblich angepasst werden. Uhr- und Wetter-Widgets besitzen zusätzlich eigene Design-/Layoutvarianten.

---

### 🔎 Globale Suche & Plattformfunktionen

- globale Suche über Tools, Notizen, Dateien, Nutzer und Roadmap-Ideen
- Favoriten-System für Tools und Spiele
- Inbox für System-/Plattformmeldungen
- Feedback-Seite
- Roadmap mit Feature-Ideen, Votes, Kommentaren und Admin-Status
- Achievement-Center mit XP, Leveln, Kategorien und Ranking
- automatische Benachrichtigungszähler
- HTTP-Fallback und Realtime-Infrastruktur über Channels

---

### 👤 Profile, Freunde & Community

- Profilseite mit Avatar, Bio, Status und Datenschutzoptionen
- öffentlicher Profilbereich
- Profilkarten-Designer mit Styles, Farben, Mustern, Glow, Shine, Badge und Avatar-Form
- Galerie-Upload im Profil
- Nutzerübersicht
- Freundschaftsanfragen
- Freundesliste
- Nutzer blockieren und melden
- Sichtbarkeit von Online-Status, Freunden, Highscores und Achievements steuerbar

---

### 💬 Chats

- Direktchats mit Freunden
- Gruppenchats
- Gruppeneinstellungen
- Mitgliederverwaltung
- Chat-Themes
- Nachrichten senden, bearbeiten, löschen und anpinnen
- Emoji-Reaktionen
- Typing-Status
- Attachments
- ungelesene Nachrichten und Benachrichtigungen

---

### 📝 Notizen

- Notizen erstellen, bearbeiten und löschen
- Pins
- Archiv
- Farben
- Tags
- Suche und Filter
- Erinnerungstermine
- nutzerbezogene Speicherung
- Papierkorb-Unterstützung

---

### 📤 Datei-Share

- Dateien mit Freunden teilen
- private Download-Links
- optionaler Passwortschutz
- Ablaufdatum
- Download-Limit
- Mehrfachupload
- Drag-and-drop-Upload
- Upload-Fortschritt
- Bild-/PDF-Vorschau
- Download-Zähler
- pro Nutzer konfigurierbare Upload-Limits im Adminbereich
- Papierkorb-Unterstützung

Standardlimit: **50 MB pro Datei**  
Optionale Limits: **100 MB**, **500 MB** oder **unbegrenzt**

---

## 🧰 Tools

### 🌦️ Wetter

Die Wetterseite nutzt die **OpenWeather API**.

- aktuelles Wetter
- Wetterbeschreibung und Icon
- Tagesdaten
- Vorhersage
- Sonnenaufgang und Sonnenuntergang
- Suche nach Städten
- gespeicherte Orte
- Wetter-Widget für die Startseite

Benötigter `.env`-Wert:

```env
OPENWEATHER_API_KEY=dein_openweather_api_key
```

---

### 🕒 Uhr, Timer & Weltuhr

- lokale Uhrzeit
- Weltuhr mit gespeicherten Orten
- Stoppuhr mit Runden
- Timer mit Vorlagen
- eigene Timer-Sounds
- Lautstärkeeinstellungen
- Weltkarten-Hintergrund über `app/static/app/img/worldmap.webp`

---

### 🧮 Wissenschaftlicher Rechner

- Grundrechenarten
- Klammern
- Wurzeln
- Potenzen
- Trigonometrie mit DEG/RAD
- Logarithmen
- `π`, `e`, `Ans`
- Speicherfunktionen
- Verlauf im Browser
- Tastaturbedienung

---

### 💸 Budget-Tracker

- Monatsbudget
- geplante Einnahmen
- Ausgabenlimit
- Sparziel
- Einnahmen/Ausgaben mit Kategorien
- wiederkehrende monatliche Einträge
- Monatsnavigation
- Summen, Restbudget und Fortschritt
- CSV-Export
- Budget-Widget auf der Startseite

---

### ⛽ Spritkostenrechner

Der Spritkostenrechner nutzt die **Tankerkönig API**.

- Standortabfrage über Browserfreigabe
- Stadtsuche
- Preisübersicht
- API-Endpunkt `/api/tankstellen/`

Benötigter `.env`-Wert:

```env
TANKERKOENIG_API_KEY=dein_tankerkoenig_api_key
```

---

### 🎵 Genius Search

Die Genius Search nutzt die **Genius API**.

- Suche nach Songs und Künstlern
- Ergebnisliste mit Titel, Künstler, Cover und externem Link
- API-Endpunkt `/api/genius/search/`

Benötigter `.env`-Wert:

```env
GENIUS_ACCESS_TOKEN=dein_genius_access_token
```

---

### 📐 Einheitenrechner

- Speichergrößen
- Zeitwerte
- Entfernungen
- weitere schnelle Umrechnungen direkt im Browser

---

### 🎲 Randomizer

- Zufallszahlen
- Listen-Auswahl
- Entscheidungshilfen
- kleine Zufallstools für Alltag und Spiele

---

### 📄 Datei-Konverter

Der Datei-Konverter verarbeitet Dateien serverseitig temporär und löscht sie danach wieder.

Unterstützt:

- DOC, DOCX, ODT, RTF und Text zu PDF
- XLS, XLSX und ODS zu PDF
- PPT, PPTX und ODP zu PDF
- PNG, JPG, WEBP, BMP und GIF zu PNG, JPG, WEBP oder PDF

Office-Dateien werden serverseitig über LibreOffice verarbeitet. Die nötigen Pakete sind im Dockerfile installiert.

---

### 🖼️ Bild Tools

- Bilder komprimieren
- Bildformate konvertieren
- optimierte Medien-Verarbeitung
- bessere Darstellung durch gemeinsame Tool-Styles

---

### 🎨 Color Palette Tool

- Farbauswahl per Standard-Farbpicker
- Bildschirm-Farbaufnahme über die Browser EyeDropper API, wenn unterstützt
- Bild hochladen und Pixel-Farbe im Canvas anklicken
- HEX, RGB und HSL kopieren
- lokale Palette per `localStorage`
- Kontrastprüfung für weißen und dunklen Text

---

### 🔳 QR-Code Tool

- QR-Codes für Text und URLs
- WLAN-QR-Codes
- Kontakt-/vCard-QR-Codes
- anpassbare Farben
- PNG-Download

---

### 📚 Avatar Wiki

- Avatar-Charaktere verwalten
- Name, Nation, Link, Beschreibung und Bild
- Suche und Übersicht
- API-Endpunkte für Charakterdaten
- Hintergrundbild über `app/static/app/img/Airtemple-island.webp`

---

### 🎛️ OBS Dashboard

- Verbindung zu OBS WebSocket
- Szenen anzeigen und wechseln
- Quellen umschalten
- Audio-Mixer
- Mute-/Volume-Steuerung
- Stream-/Aufnahme-Steuerung
- Reload- und Vollbildfunktionen

Geeignet als lokales Tablet-Control-Panel.

---

### 🎚️ Stream Deck

- Button-Dashboard für Spotify, Voicemod und eigene Aktionen
- Spotify-Anbindung
- Voicemod-Steuerung mit lokal gespeichertem API-Key
- Voicemod-Voices laden
- Voice-Auswahl aus der geladenen Voicemod-Liste
- Voice Changer, Hear Myself, Mikrofon-Mute und Zufalls-Voice
- eigene Buttons und Aktionen
- Toast-Hinweise bei fehlender Verbindung

---

## 🎮 Spiele

MyTools enthält mehrere Singleplayer- und Multiplayer-Spiele. Multiplayer-Spiele nutzen private Räume/Lobbys, Codes/Links, Freundeseinladungen, Host-Rechte, Live-Status und serverseitig geprüfte Aktionen.

### Singleplayer / Highscore

- **Human Benchmark**: Reaktion, Aim Trainer, Typing und Visual Memory mit Highscores.
- **2048**: Highscore-Speicherung, Aktivitätsstatus und Leaderboard-Anbindung.
- **Cookie Cosmos**: Cookie-/Clicker-Spiel mit Highscore.
- **Cookie Cosmos V2**: neuer Save-State, Datenbank-Speichern, Import/Export und Leaderboard-Anbindung.
- **Nebula Forge Tycoon**: AFK-/Clicker-Tycoon mit Anlagen, Upgrades, Ereignissen, Erfolgen, DB-Save, Import/Export und i18n-Vorbereitung.
- **Snake Powerups**: Snake-Variante mit Powerups.
- **Drift Circuit Pro**: Canvas-Racing-Game mit Maps, Nitro, Drift-Score und Tastatursteuerung.

### Multiplayer

- **Skribble**: Zeichnen, Raten, Punkte, Runden und Lobby-System.
- **Tic Tac Toe**: 1v1 mit Räumen, Einladungen, Live-Status und serverseitiger Zugprüfung.
- **Vier gewinnt**: animiertes 1v1 mit Gewinnlinie, Reset und Live-Aktualisierung.
- **Schiffe versenken**: manuelle Flottenplatzierung, Treffer/Wasser/versenkt, Sounds und geprüfte Regeln.
- **Stadt Land Fluss**: gemeinsame Runden, Entwürfe, Stopp-Regel, Voting und Endplatzierung.
- **Hangman**: Lobby-Spiel mit Wort/Hinweis, Rate-Logik, Spielern, Punkten und Review.
- **Uno**: Lobby-Kartenspiel mit mehreren Spielern, Ziehen, Ablegen, UNO-Call, Sonderregeln und Runden-Reset.
- **Kniffel**: Multiplayer-Würfelspiel mit Würfen, Wertung und Rundenlogik.
- **Pong**: 1v1-Arcade-Spiel mit Canvas, Maus/Touch/Tastatur, serverseitiger Ballphysik und Profil-/Achievement-Anbindung.
- **Werwolf**: Lobby-Spiel mit Rollen, Tag-/Nachtphasen, Aktionen, Chat und Host-Steuerung.

### 🏆 Leaderboard

Die Leaderboard-Seite fasst verschiedene Highscores und Rekorde zusammen, unter anderem für:

- Human Benchmark
- 2048
- Cookie Cosmos / Cookie Cosmos V2
- Nebula Forge Tycoon
- Multiplayer-Siege je nach Spiel

---

## 🛡️ Sicherheit, Admin & Moderation

### Zwei-Faktor-Authentifizierung

- 2FA-Einrichtung über `/settings/security/2fa/`
- 2FA-Verifizierung beim Login
- Security-Events für Aktivierung/Deaktivierung und Logins

### Security-Dashboard

Unter `/security/`:

- 2FA-Status
- aktive Sessions
- erfolgreiche/fehlgeschlagene Login-Ereignisse
- andere Sitzungen beenden
- Security-Historie

### Moderation

Unter `/moderation/` für Staff-Nutzer:

- Login-/Registrierungs-Sperre
- Tool- und Spielzugriff steuern
- Status: **Veröffentlicht**, **Unveröffentlicht**, **Versteckt**
- Reports bearbeiten
- Feedback-Status pflegen
- File-Shares moderieren
- Nutzer verwarnen/sperren
- Medien optimieren
- Audit-Log

### Papierkorb

Unter `/trash/`:

- gelöschte unterstützte Inhalte ansehen
- wiederherstellen
- endgültig löschen
- Papierkorb leeren

Aktuell über den Papierkorb geführt werden unter anderem Shortcuts, Notizen, Datei-Shares und Home-Widgets.

---

## 🎨 Design & Oberfläche

- Dark Mode
- Theme-Editor
- eigene Accent-Farben
- moderne Kartenlayouts
- Kontrastmodus
- reduzierte Animationen
- Hintergrundeffekte
- responsive Darstellung für Desktop, Tablet und Smartphone
- mobile Bottom-Navigation
- sticky Header
- überarbeiteter Footer
- Einheitliches Tool-Design über `app/static/app/css/tool_pages.css`
- linkslastige, kompakte UI-Ausrichtung

Gemeinsame Tool-Styles gelten unter anderem für:

- Datei-Konverter
- Bild Tools
- QR-Code Tool
- Einheitenrechner
- Spritkostenrechner
- Rechner
- Randomizer
- Notizen

---

## 🌍 Internationalisierung

MyTools nutzt Django i18n.

Unterstützte Sprachen:

- Deutsch
- Englisch

Nach Änderungen an übersetzbaren Texten:

```bash
python manage.py makemessages -l de
python manage.py makemessages -l en
python manage.py compilemessages
```

Unter Windows müssen dafür die GNU-gettext-Tools installiert sein.

Nebula Forge Tycoon und andere JavaScript-lastige Bereiche nutzen zusätzlich Template-/JSON-basierte Übersetzungsdaten, damit Texte von `makemessages` erkannt werden können.

---

## 📦 PWA

MyTools ist als installierbare Web-App vorbereitet.

- `manifest.webmanifest`
- `service-worker.js`
- Offline-Seite unter `/offline/`
- Caching statischer Dateien
- keine aggressive Vorab-Caches für private HTML-Seiten oder API-Antworten

Nach dem Deployment prüfen:

```text
https://deine-domain.de/manifest.webmanifest
https://deine-domain.de/service-worker.js
https://deine-domain.de/offline/
```

Für Installation und Service Worker wird produktiv HTTPS benötigt. Lokal funktioniert der Service Worker auch auf `localhost`.

---

## ⚙️ Wichtige `.env`-Werte

Beispiel:

```env
DEBUG=False
SECRET_KEY=dein_secret_key
DOMAIN=mytools.example.de
ALLOWED_HOSTS=localhost,127.0.0.1,mytools.example.de
CSRF_TRUSTED_ORIGINS=https://mytools.example.de

DB_NAME=mytools
DB_USER=mytools
DB_PASSWORD=dein_db_passwort
DB_HOST=db
DB_PORT=5432

REDIS_URL=redis://redis:6379/0

OPENWEATHER_API_KEY=dein_openweather_api_key
TANKERKOENIG_API_KEY=dein_tankerkoenig_api_key
GENIUS_ACCESS_TOKEN=dein_genius_access_token

FONTAWESOME_KIT_KEY=dein_fontawesome_kit_key
USE_FONTAWESOME_KIT=False

RECAPTCHA_PUBLIC_KEY=dein_recaptcha_public_key
RECAPTCHA_PRIVATE_KEY=dein_recaptcha_private_key

GOOGLE_ANALYTICS_ID=G-XXXXXXXXXX

EMAIL_BACKEND_MODE=smtp
EMAIL_HOST=smtp.example.de
EMAIL_PORT=465
EMAIL_USE_SSL=True
EMAIL_USE_TLS=False
EMAIL_HOST_USER=deine_mail@example.de
EMAIL_HOST_PASSWORD=dein_mail_passwort
DEFAULT_FROM_EMAIL=MyTools <deine_mail@example.de>
SERVER_EMAIL=MyTools <deine_mail@example.de>

CLOUDFLARE_TUNNEL_TOKEN=dein_cloudflare_tunnel_token
```

Hinweise:

- `GOOGLE_ANALYTICS_ID` muss eine **GA4 Measurement ID** sein und mit `G-` beginnen.
- In Tests werden bei fehlenden reCAPTCHA-Keys automatisch Googles Test-Keys verwendet.
- Secrets gehören nicht ins Repository.

---

## 🧑‍💻 Lokale Entwicklung

### 1. Virtuelle Umgebung erstellen

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Abhängigkeiten installieren

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. `.env` für lokale Entwicklung anlegen

Minimal lokal mit SQLite:

```env
DEBUG=True
SECRET_KEY=dev-only-change-me
USE_SQLITE=True
USE_LOCAL_CACHE=True
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=
OPENWEATHER_API_KEY=
```

### 4. Datenbank vorbereiten

```bash
python manage.py migrate
python manage.py createsuperuser
```

### 5. Server starten

```bash
python manage.py runserver 127.0.0.1:8090
```

Danach öffnen:

```text
http://127.0.0.1:8090/
```

---

## 🐳 Docker Deployment

Produktiv läuft MyTools typischerweise mit Docker Compose.

Container:

- `mytools_web` für Django/Daphne
- `mytools_db` für PostgreSQL
- `mytools_redis` für Cache/WebSocket-Backend
- `mytools_caddy` als Reverse Proxy
- `mytools_cloudflared` optional für Cloudflare Tunnel

Start/Rebuild:

```bash
docker compose up -d --build
```

Migrationen manuell ausführen:

```bash
docker compose exec web python manage.py migrate
```

Statische Dateien sammeln:

```bash
docker compose exec web python manage.py collectstatic --noinput
```

Logs ansehen:

```bash
docker compose logs -f web
```

Containerstatus:

```bash
docker compose ps
```

---

## 📰 Git-Changelog

Die Seite `/changelog/` liest die Datei:

```text
app/static/app/data/changelog_git.json
```

Diese Datei wird aus dem Git-Repository erzeugt:

```bash
python scripts/generate_git_changelog.py --limit 0
```

Alternativ über Django:

```bash
python manage.py generate_git_changelog --limit 0
```

Beim Deployment auf dem Server wird der Changelog im Workflow vor dem Docker-Start automatisch erzeugt.

Wenn lokal keine `.git`-Historie vorhanden ist, bleibt der Changelog leer und die Seite zeigt einen Hinweis an.

---

## 🧪 Tests & Qualitätschecks

Kompletter lokaler Qualitätslauf:

```bash
python scripts/verify.py
```

Nur Django-Tests:

```bash
python manage.py test app
```

Migrationen prüfen:

```bash
python manage.py makemigrations --check --dry-run
```

Statische Dateien testweise sammeln:

```bash
python manage.py collectstatic --noinput --dry-run
```

GitHub Actions:

- `quality.yml`: GitHub-Actions-Workflow läuft nur manuell über `workflow_dispatch`
- `deploy.yml`: Tests/Security-Scan für Feature-Branches, Build/Deploy bei Push/Merge auf `main`
- OSV-Scan blockiert den Workflow nicht, sondern gibt nur Hinweise aus

---

## 📁 Projektstruktur

```text
MyTools/
├── .github/workflows/
│   ├── deploy.yml
│   └── quality.yml
├── MyTools/
│   ├── asgi.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── app/
│   ├── templates/app/
│   ├── static/app/css/
│   ├── static/app/js/
│   ├── static/app/img/
│   ├── static/app/data/
│   ├── management/commands/
│   ├── migrations/
│   ├── forms/
│   │   ├── chat.py
│   │   ├── core.py
│   │   ├── platform.py
│   │   └── profile.py
│   ├── views/
│   │   ├── auth.py
│   │   ├── budget.py
│   │   ├── chat.py
│   │   ├── community.py
│   │   ├── core.py
│   │   ├── moderation.py
│   │   ├── performance_tools.py
│   │   ├── profile.py
│   │   ├── pwa.py
│   │   ├── security.py
│   │   └── ...
│   ├── access_control.py
│   ├── achievement_utils.py
│   ├── models.py
│   ├── urls.py
│   └── *_utils.py
├── locale/
├── media/
├── scripts/
│   ├── generate_git_changelog.py
│   └── verify.py
├── Caddyfile
├── Dockerfile
├── docker-compose.yml
├── DOCKER.md
├── manage.py
├── requirements.txt
└── README.md
```

---

## 🚀 Ziel des Projekts

MyTools soll eine persönliche, erweiterbare Web-Toolbox bleiben:

- schnell erreichbar
- gut für Homelab, Alltag, Medien und Streaming
- nutzerbezogen mit Profilen, Freunden und Chats
- modern und mobil bedienbar
- mit sinnvollen Admin-/Security-Funktionen
- leicht per Docker deploybar
- Schritt für Schritt um neue Tools und Spiele erweiterbar
