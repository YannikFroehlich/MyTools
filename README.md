# 🧰 MyTools

**MyTools** ist ein persönliches Django-Dashboard für kleine Alltags-, Server-, Web- und Streaming-Tools.  
Die App bündelt Schnellzugriffe, Wetterdaten, Notizen, Rechner, kleine Browser-Spiele und API-basierte Helfer in einer modernen Oberfläche.

Das Projekt kann lokal in der Entwicklung laufen oder produktiv per Docker Compose mit **Django/Gunicorn**, **PostgreSQL**, **Redis** und **Caddy** betrieben werden.

---

## ✨ Aktueller Stand

MyTools ist inzwischen mehr als nur eine Startseite. Der aktuelle Stand enthält:

- Startseite mit eigenen Shortcut-Bereichen
- Schnellzugriffe mit FontAwesome-Icons oder eigenen Bildern
- Favoriten, Drag & Drop Sortierung und einklappbare Bereiche
- Wetterseite mit OpenWeather API und gespeicherten Orten
- OBS Dashboard für lokale OBS-WebSocket-Steuerung
- Spritkostenrechner mit Tankerkönig API
- Genius Search mit Genius API
- Notizen-App mit Pins, Archiv, Farben und Tags
- Einheitenrechner
- Human Benchmark
- Avatar Wiki mit Charakterverwaltung
- Drift Circuit Pro als browserbasiertes Racing-Game
- Google-Apps-Menü mit externen Links
- Theme-Editor mit Farbvorgaben und eigener Farbwahl
- Dark Mode
- Deutsch/Englisch über Django i18n
- Docker-Setup für produktiven Betrieb

---

## 🏠 Startseite & Shortcuts

Die Startseite ist die zentrale Oberfläche für eigene Links und lokale Dienste.

Funktionen:

- eigene Verknüpfungen mit Name, URL und Icon
- optional eigene Bilder für Shortcuts
- eigene Bereiche/Kategorien
- Bereiche farblich markieren
- Bereiche ein- und ausklappen
- Favoriten markieren
- Drag & Drop Sortierung für Shortcuts
- Drag & Drop Sortierung für Bereiche
- Suchleiste mit Vorschlägen
- Dark Mode und Theme-Anpassung

Beispiele für typische Shortcuts:

- CasaOS
- Nextcloud
- Crafty
- GitHub
- Django Docs
- lokale Serverdienste im Heimnetz

---

## 🌦️ Wetter

Die Wetterseite nutzt die **OpenWeather API**.

Funktionen:

- aktuelles Wetter
- Temperatur und Beschreibung
- Wetter-Icons
- Tagesdaten
- Vorhersage
- Sonnenaufgang und Sonnenuntergang
- Suche nach Städten
- Nutzung von Koordinaten über `lat` und `lon`
- gespeicherte Wetter-Orte über Django-Model
- kompakte Anzeige der gespeicherten Orte neben der Suche
- Fehlerhinweise, wenn API-Key, Stadt oder API-Antwort fehlerhaft sind

Benötigter `.env` Wert:

```env
OPENWEATHER_API_KEY=dein_openweather_api_key
```

---

## 🎛️ OBS Dashboard

Das OBS Dashboard ist als lokale Steuerzentrale für OBS gedacht.

Funktionen:

- Verbindung zu OBS WebSocket
- Szenen anzeigen und wechseln
- Quellen anzeigen und umschalten
- Audio-Mixer anzeigen
- Mute/Volume-Steuerung
- Stream-/Aufnahme-Steuerung
- Reload- und Vollbildfunktionen
- Offline-/Leerzustände, wenn keine Verbindung besteht

Die Seite eignet sich besonders gut für ein Tablet als lokales Stream-Control-Panel.

---

## ⛽ Spritkostenrechner

Der Spritkostenrechner nutzt die **Tankerkönig API**.

Funktionen:

- Tankstellenabfrage über Standortdaten
- Preisübersicht
- API-Endpunkt unter `/api/tankstellen/`
- Fehlermeldung, wenn der API-Key fehlt oder die API nicht erreichbar ist

Benötigter `.env` Wert:

```env
TANKERKOENIG_API_KEY=dein_tankerkoenig_api_key
```

---

## 🎵 Genius Search

Die Genius Search durchsucht Songs über die **Genius API**.

Funktionen:

- Suche nach Songs und Künstlern
- Ergebnisliste mit Titel, Künstler, Cover und Link
- API-Endpunkt unter `/api/genius/search/`
- saubere Fehlerausgabe bei fehlendem API-Key oder API-Problemen

Benötigter `.env` Wert:

```env
GENIUS_API_KEY=dein_genius_api_key
```

---

## 📝 Notizen

Eine einfache Notizen-App direkt im Dashboard.

Funktionen:

- Notizen erstellen
- Notizen bearbeiten
- Notizen löschen
- Notizen anpinnen
- Notizen archivieren und wiederherstellen
- Farben pro Notiz
- Tags pro Notiz
- Sortierung nach angepinnten und zuletzt aktualisierten Notizen

---

## 🧮 Einheitenrechner

Ein kleiner Rechner zum Umrechnen verschiedener Werte.

Aktuell enthalten:

- Speichergrößen
- Zeit
- Entfernung
- Geld-/Zeitraum-Werte

Die Oberfläche und Labels sind für Django-Übersetzungen vorbereitet.

---

## ⚡ Human Benchmark

Kleine Benchmark-/Reaktions-Tools im Browser.

Enthalten sind browserbasierte Mini-Tests, Sounds und eine moderne Oberfläche für schnelle Reaktions- und Eingabeübungen.

---

## 🌊 Avatar Wiki

Ein kleines Avatar-Wiki mit Charakteren.

Funktionen:

- Charaktere verwalten
- Nationen/Farben
- Bilder pro Charakter
- Reihenfolge über `order`
- API für Charakterliste
- API für Charakterdetails

API-Endpunkte:

```text
/api/avatar-characters/
/api/avatar-characters/<id>/
```

---

## 🏎️ Drift Circuit Pro

Ein browserbasiertes 2D-Racing-Game mit HTML5 Canvas.

Funktionen:

- große Maps
- Kamera folgt dem Auto
- mehrere Strecken
- Time Trial, Checkpoint Rush und freies Fahren
- Nitro
- Drift-Score
- Checkpoints
- Minimap
- Touch-Buttons für mobile Nutzung

Route:

```text
/drift-circuit/
```

---

## 🎚️ Stream Deck

Die Route für ein eigenes Stream-Deck-Tool ist bereits vorbereitet.

Aktueller Status:

- Template vorhanden
- CSS/JS-Dateien vorbereitet
- Route im Menü eingebunden
- Inhalt kann noch ausgebaut werden

Route:

```text
/stream-deck/
```

---

## 🎨 Design & Bedienung

MyTools besitzt eine moderne Oberfläche mit anpassbarem Look.

Funktionen:

- Light Mode
- Dark Mode
- Theme-Editor
- Presets für Blau, Grün, Rose und Graphit
- eigene Farben für Header, Hintergrund und Footer
- responsive Layouts
- Dropdown-Menüs für Tools, Spiele und Google-Apps
- externe Links werden in einem neuen Tab geöffnet

Für FontAwesome kann optional ein Kit-Key aus der `.env` genutzt werden:

```env
FONTAWESOME_KIT_KEY=dein_fontawesome_kit_key
```

---

## 🌍 Mehrsprachigkeit

Das Projekt nutzt Django i18n.

Aktuell vorbereitet:

- Deutsch
- Englisch

Übersetzungsdateien liegen unter:

```text
locale/de/LC_MESSAGES/django.po
locale/en/LC_MESSAGES/django.po
```

---

## 🧱 Tech Stack

- Python 3.12
- Django 6.0.4
- PostgreSQL 16
- Redis 7
- Gunicorn
- Caddy
- Docker Compose
- WhiteNoise
- django-redis
- python-dotenv
- requests
- Pillow

---

## 📁 Projektstruktur

```text
MyTools/
├── app/
│   ├── migrations/
│   ├── static/app/
│   │   ├── css/
│   │   ├── js/
│   │   ├── data/
│   │   ├── icons/
│   │   └── img/
│   ├── templates/app/
│   ├── admin.py
│   ├── forms.py
│   ├── models.py
│   ├── urls.py
│   └── views.py
├── locale/
│   ├── de/LC_MESSAGES/
│   └── en/LC_MESSAGES/
├── media/
├── MyTools/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── Caddyfile
├── Dockerfile
├── docker-compose.yml
├── DOCKER.md
├── manage.py
├── requirements.txt
└── README.md
```

---

## ⚙️ Wichtige Umgebungsvariablen

Lege im Projektordner eine `.env` Datei an.

Beispiel:

```env
DEBUG=True
SECRET_KEY=bitte-einen-eigenen-secret-key-setzen

DOMAIN=tools.example.com
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=https://tools.example.com

USE_SQLITE=False
USE_LOCAL_CACHE=False

DB_NAME=mytools
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=db
DB_PORT=5432

REDIS_URL=redis://redis:6379/0

FONTAWESOME_KIT_KEY=
OPENWEATHER_API_KEY=
GENIUS_API_KEY=
TANKERKOENIG_API_KEY=
SPOTIFY_CLIENT_ID=
SPOTIFY_REDIRECT_URI=https://tools.example.com/stream-deck/
```

> Die echte `.env` sollte nicht ins Git-Repository committed werden.

---

## 🚀 Lokale Entwicklung ohne Docker

### 1. Virtuelle Umgebung erstellen

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Abhängigkeiten installieren

```bash
pip install -r requirements.txt
```

### 3. `.env` für lokale Entwicklung anlegen

Für lokale SQLite-Entwicklung kannst du z. B. setzen:

```env
USE_SQLITE=True
USE_LOCAL_CACHE=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

### 4. Migrationen ausführen

```bash
python manage.py migrate
```

### 5. Entwicklungsserver starten

```bash
python manage.py runserver
```

Danach ist die App erreichbar unter:

```text
http://127.0.0.1:8000/
```

---

## 🐳 Start mit Docker Compose

### 1. `.env` anlegen

Im Projektordner:

```bash
nano .env
```

Für Docker sollte PostgreSQL und Redis über die Service-Namen erreichbar sein:

```env
USE_SQLITE=False
USE_LOCAL_CACHE=False
DB_HOST=db
REDIS_URL=redis://redis:6379/0
DOMAIN=tools.example.com
CLOUDFLARE_TUNNEL_TOKEN=dein-cloudflare-token
SPOTIFY_REDIRECT_URI=https://tools.example.com/stream-deck/
```

### 2. Container bauen und starten

```bash
docker compose up -d --build
```

Beim Start führt der Web-Container automatisch aus:

```bash
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn MyTools.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 60
```

### 3. Logs anschauen

```bash
docker compose logs -f web
```

### 4. Status prüfen

```bash
docker compose ps
```

### 5. App öffnen

Mit Cloudflare Tunnel ist MyTools unter deiner Domain erreichbar:

```text
https://tools.example.com/
```

Lokal auf demselben Server kannst du testen mit:

```bash
curl -I http://localhost:8090
```

---

## 🧑‍💻 Django Admin

Superuser erstellen:

```bash
docker compose exec web python manage.py createsuperuser
```

Admin öffnen:

```text
https://tools.example.com/admin/
```

---

## 🔄 Änderungen auf dem Server deployen

Typischer Ablauf für deinen Server unter `/opt/mytools`:

```bash
cd /opt/mytools
git pull origin main
docker compose up -d --build
```

Wenn du neue Models geändert oder hinzugefügt hast:

```bash
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate
```

Wenn du statische Dateien geändert hast:

```bash
docker compose exec web python manage.py collectstatic --noinput
```

Wenn du nur `.env` geändert hast:

```bash
docker compose up -d --force-recreate web
```

Oder einmal komplett neu starten:

```bash
docker compose restart
```

---

## 🌐 Wichtige Routen

| Seite | URL |
|---|---|
| Startseite | `/` |
| Home | `/home/` |
| Über | `/about/` |
| Wetter | `/weather/` |
| OBS Dashboard | `/obs-dashboard/` |
| Spritkostenrechner | `/spritkostenrechner/` |
| Human Benchmark | `/human-benchmark/` |
| Genius Search | `/genius-search/` |
| Avatar Wiki | `/avatar-wiki/` |
| Notizen | `/notes/` |
| Neue Notiz | `/notes/new/` |
| Einheitenrechner | `/einheitenrechner/` |
| Drift Circuit Pro | `/drift-circuit/` |
| Stream Deck | `/stream-deck/` |
| Admin | `/admin/` |

---

## 🔌 API-Endpunkte

| API | URL |
|---|---|
| Genius Suche | `/api/genius/search/` |
| Tankstellen | `/api/tankstellen/` |
| Avatar Charaktere | `/api/avatar-characters/` |
| Avatar Charakter Detail | `/api/avatar-characters/<id>/` |

---

## 🌍 Übersetzungen bearbeiten

Texte aus Templates/Python sammeln:

```bash
python manage.py makemessages -l en
python manage.py makemessages -l de
```

Übersetzungen kompilieren:

```bash
python manage.py compilemessages
```

Unter Windows brauchst du dafür GNU gettext. Wenn `msguniq` fehlt, ist gettext nicht installiert oder nicht im `PATH`.

---

## 🛠️ Nützliche Befehle

### Container neubauen

```bash
docker compose up -d --build
```

### Logs anzeigen

```bash
docker compose logs -f
```

### Nur Web-Logs anzeigen

```bash
docker compose logs -f web
```

### Shell im Django-Container öffnen

```bash
docker compose exec web sh
```

### Migrationen ausführen

```bash
docker compose exec web python manage.py migrate
```

### Statische Dateien sammeln

```bash
docker compose exec web python manage.py collectstatic --noinput
```

### Container stoppen

```bash
docker compose down
```

### Container inklusive Volumes löschen

Achtung: Das löscht auch Datenbankdaten.

```bash
docker compose down -v
```

---

## 🧯 Troubleshooting

### Seite ist nicht erreichbar

Prüfen, ob Container laufen:

```bash
docker compose ps
```

Logs prüfen:

```bash
docker compose logs -f web
```

Port prüfen:

```bash
ss -tulpn | grep 8090
```

---

### Static-Dateien fehlen

```bash
docker compose exec web python manage.py collectstatic --noinput
docker compose restart caddy
```

---

### Datenbank ist nicht erreichbar

```bash
docker compose logs -f db
docker compose restart db web
```

---

### API-Key fehlt

Prüfe die `.env` Datei:

```bash
cat .env
```

Danach Container neu laden:

```bash
docker compose up -d --force-recreate web
```

---

## 🧭 Deployment-Kontext

Produktiv läuft MyTools typischerweise hier:

```text
Server: yfserver
IP: 192.168.178.99
Projektpfad: /opt/mytools
MyTools-Port: 8090
CasaOS-Port: 8080
```

---

## 📌 Hinweise

- Secrets gehören nur in die `.env`, nicht ins Git-Repository.
- Änderungen an `requirements.txt` brauchen einen neuen Docker Build.
- Änderungen an Models brauchen Migrationen.
- Änderungen an CSS/JS/Templates können je nach Browser Cache erst nach Cache-Leeren sichtbar sein.
- Für externe APIs müssen die jeweiligen API-Keys gesetzt sein.
- Nach neuen Übersetzungstexten müssen `makemessages` und `compilemessages` erneut laufen.

---

## 📄 Lizenz

Privates Projekt / eigenes Dashboard.
