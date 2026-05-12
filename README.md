# 🧰 MyTools

**MyTools** ist ein persönliches Django-Dashboard für kleine Alltags-, Server- und Web-Tools.  
Das Projekt läuft lokal in der Entwicklung oder produktiv auf einem Server per Docker Compose mit Django/Gunicorn, PostgreSQL, Redis und Caddy.

Die Anwendung ist als private Tool-Zentrale gedacht: Startseite, eigene Schnellzugriffe, Wetter, OBS-Steuerung, Spritkosten, Notizen, Einheitenrechner und weitere kleine Tools können zentral über eine moderne Oberfläche genutzt werden.

---

## ✨ Features

### 🏠 Startseite mit Schnellzugriffen

Auf der Startseite können eigene Verknüpfungen gespeichert und sortiert werden.

- eigene Links mit Name, URL und Icon
- optionale eigene Bilder für Shortcuts
- Favoriten
- eigene Bereiche/Kategorien
- Drag & Drop Sortierung
- Bereiche ein- und ausklappen
- Dark Mode
- Suchleiste mit Vorschlägen

Beispiele für Shortcuts:

- CasaOS
- Nextcloud
- Crafty
- GitHub
- Django Docs
- eigene lokale Dienste

---

### 🌦️ Wetter

Die Wetterseite nutzt die OpenWeather API.

- aktuelles Wetter
- Temperatur und Beschreibung
- Wetter-Icons
- Tagesdaten
- Sonnenaufgang und Sonnenuntergang
- Fehlerhinweis, wenn der API-Key fehlt oder die API nicht erreichbar ist

Benötigter `.env` Wert:

```env
OPENWEATHER_API_KEY=dein_openweather_api_key
```

---

### 🎛️ OBS Dashboard

Das OBS Dashboard ist als lokale Steuerzentrale für OBS gedacht.

- Verbindung zu OBS WebSocket
- Szenen anzeigen und wechseln
- Quellen anzeigen und umschalten
- Audio-Mixer anzeigen
- Stream-/Aufnahme-Steuerung
- Offline-/Leerzustände, wenn keine Verbindung besteht

Die Seite eignet sich z. B. für ein Tablet als Wand- oder Stream-Controller.

---

### ⛽ Spritkostenrechner

Der Spritkostenrechner kann Tankstellen über die Tankerkönig API abfragen.

- Standortbasierte Tankstellenabfrage
- Preisübersicht
- API-Fehlermeldung, wenn der Key fehlt

Benötigter `.env` Wert:

```env
TANKERKOENIG_API_KEY=dein_tankerkoenig_api_key
```

---

### 🎵 Genius Search

Die Genius Search durchsucht Songs über die Genius API.

- Suche nach Songs/Künstlern
- Ergebnisliste mit Titel, Künstler, Cover und Link
- klare Fehlermeldung, wenn der API-Key fehlt

Benötigter `.env` Wert:

```env
GENIUS_API_KEY=dein_genius_api_key
```

---

### 📝 Notizen

Eine einfache Notizen-App direkt im Dashboard.

- Notizen erstellen
- Notizen bearbeiten
- Notizen löschen
- Notizen anpinnen
- Notizen archivieren/wiederherstellen
- Farben
- Tags

---

### 🧮 Einheitenrechner

Ein kleiner Rechner zum Umrechnen verschiedener Werte.

Aktuell enthalten:

- Speichergrößen
- Zeit
- Entfernung
- Geld-/Zeitraum-Werte

Die Labels sind über Django-Übersetzungen eingebunden.

---

### ⚡ Human Benchmark

Kleine Benchmark-/Reaktions-Tools im Browser.

---

### 🌊 Avatar Wiki

Ein kleines Avatar-Wiki mit Charakteren.

- Charaktere verwalten
- Nationen/Farben
- Bilder
- Detaildaten per API

---

### 🌍 Mehrsprachigkeit

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

ALLOWED_HOSTS=localhost,127.0.0.1,192.168.178.99
CSRF_TRUSTED_ORIGINS=http://192.168.178.99:8090

USE_SQLITE=False
USE_LOCAL_CACHE=False

DB_NAME=mytools
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=db
DB_PORT=5432

REDIS_URL=redis://redis:6379/0
DOMAIN=localhost

OPENWEATHER_API_KEY=
GENIUS_API_KEY=
TANKERKOENIG_API_KEY=
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

Auf dem Server ist MyTools über Caddy auf Port `8090` erreichbar:

```text
http://192.168.178.99:8090/
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
http://192.168.178.99:8090/admin/
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
| Einheitenrechner | `/einheitenrechner/` |
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

---

## 📄 Lizenz

Privates Projekt / eigenes Dashboard.
