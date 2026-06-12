# 🧰 MyTools

**MyTools** ist ein persönliches Django-Dashboard für Alltag, Homelab, Medien, Streaming und kleine Web-Tools.

Die App bündelt eigene Schnellzugriffe, Startseiten-Widgets, Wetterdaten, Notizen, Profile, Freunde, Chats, Rechner, Timer, Mini-Games und API-basierte Helfer in einer modernen Oberfläche mit Dark Mode, Theme-Anpassung und deutscher/englischer Oberfläche.

Das Projekt kann lokal in der Entwicklung laufen oder produktiv per Docker Compose mit **Django/Gunicorn**, **PostgreSQL**, **Redis** und **Caddy** betrieben werden.

---

## ✨ Aktueller Stand

MyTools ist inzwischen mehr als nur eine Startseite. Aktuell enthalten sind unter anderem:

- personalisierbare Startseite mit Shortcut-Bereichen
- eigene Verknüpfungen mit FontAwesome-Icons oder hochgeladenen Bildern
- Favoriten, Drag & Drop Sortierung und einklappbare Bereiche
- Startseiten-Widgets, z. B. Uhr, Wetter, Notizen und Statistik-Karten
- Widget-Designs, Farbstile und Layout-Optionen
- Wetterseite mit OpenWeather API und gespeicherten Orten
- Uhr-Seite mit lokaler Uhrzeit, Weltuhr, Stoppuhr, gespeicherten Timern und eigenen Timer-Sounds
- dezenter Weltkarten-Hintergrund auf der Uhr-Seite über `app/static/app/img/worldmap.webp`
- Profilseite mit Avatar, Banner, Namen und öffentlicher Profilansicht
- Nutzerübersicht mit öffentlichen Profilen
- Freundschaftssystem mit Anfragen, Freundesliste und befreundet-seit Anzeige
- Chat-System mit Direktchats, Gruppenchats, Emoji-Reaktionen und Löschen eigener Nachrichten
- Datei-Share mit Freunden, privaten Links, Mehrfachupload, Fortschrittsanzeige und Admin-Limits pro Nutzer
- Skribble-Zeichenspiel mit Lobby, Einladungen, Zeichnen, Raten, Punktestand und Rundenübersicht
- Tic Tac Toe mit privaten Räumen, Freunde-Einladungen, Live-Übersicht und Host-/Löschlogik
- Vier gewinnt mit animiertem Spielfeld, privaten Räumen, Einladungen, Live-Zügen und Gewinn-Popup
- Schiffe versenken mit privaten Räumen, manueller Flottenplatzierung, Sounds, Effekten und serverseitig geprüften Spielregeln
- Stadt Land Fluss mit Live-Runden, Stopp-Regel, manueller Auswertung, Voting und Endplatzierungen
- Notizen-App mit Pins, Archiv, Farben und Tags
- Human Benchmark mit gespeicherten Ergebnissen, Highscores und Bestenliste pro Nutzer
- OBS Dashboard für lokale OBS-WebSocket-Steuerung
- Stream-Deck-Seite als Button-Dashboard für Medien, Spotify und eigene Aktionen
- Spritkostenrechner mit Tankerkönig API
- wissenschaftlicher Rechner mit Wurzeln, Potenzen, Trigonometrie, Logarithmen, Speicher und Verlauf
- Genius Search mit Genius API
- Einheitenrechner
- Avatar Wiki mit Charakterverwaltung
- Drift Circuit Pro als browserbasiertes Racing-Game
- Google-Apps-Menü mit externen Links
- Theme-Editor mit Farbvorgaben und eigener Farbwahl
- Dark Mode
- Deutsch/Englisch über Django i18n
- Docker-Setup für produktiven Betrieb

---

## 🏠 Startseite, Shortcuts & Widgets

Die Startseite ist die zentrale Oberfläche für eigene Links, lokale Dienste und kleine Widgets.

Funktionen:

- eigene Verknüpfungen mit Name, URL und Icon
- optional eigene Bilder für Shortcuts
- transparente Shortcut-Bilder behalten ihre Transparenz in Thumbnails und nutzen die Bereichsfarbe als Hintergrund
- eigene Bereiche/Kategorien
- Bereiche farblich markieren
- Bereiche ein- und ausklappen
- Favoriten markieren
- Drag & Drop Sortierung für Shortcuts
- Drag & Drop Sortierung für Bereiche
- Suchleiste mit Vorschlägen
- Startseiten-Widgets hinzufügen, bearbeiten und löschen
- Widget-Farbstile und Layouts
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
- Wetter-Widget auf der Startseite mit eigenen Designs und Layouts
- Fehlerhinweise, wenn API-Key, Stadt oder API-Antwort fehlerhaft sind

Benötigter `.env` Wert:

```env
OPENWEATHER_API_KEY=dein_openweather_api_key
```

---

## 🕒 Uhr, Timer & Weltuhr

Die Uhr-Seite ist als kleine Zeit-Zentrale gedacht.

Funktionen:

- lokale Uhrzeit
- Weltuhr mit gespeicherten Orten
- Stoppuhr mit Runden
- Timer mit Stunden, Minuten und Sekunden
- Timer-Vorlagen speichern und löschen
- eigene Timer-Sounds
- Einstellungsdialog für Timer-Sounds und Lautstärke
- dezenter Weltkarten-Hintergrund im Hero-Bereich

Das lokale Weltkartenbild liegt hier:

```text
app/static/app/img/worldmap.webp
```

---

## 🧮 Wissenschaftlicher Rechner

Der Rechner ist als eigenes Tool unter `/rechner/` eingebaut und orientiert sich an einem klassischen wissenschaftlichen Taschenrechner.

Funktionen:

- Grundrechenarten mit Klammern und Live-Vorschau
- Wurzelrechnung über `sqrt(16)`, `cbrt(27)` und `root(27,3)`
- Hochrechnung über `^`, `x²` und `x³`
- Trigonometrie mit umschaltbarem DEG/RAD-Modus
- `log`, `ln`, `abs`, Fakultät, Prozent, `π`, `e` und `Ans`
- Speicherfunktionen `MC`, `MR`, `M+` und `M-`
- Verlauf der letzten Rechnungen lokal im Browser
- Tastaturbedienung mit Enter, Escape und Backspace
- eigene Styles unter `app/static/app/css/calculator.css` und Logik unter `app/static/app/js/calculator.js`

---

## 👤 Profile, Nutzer & Freunde

MyTools enthält Profil- und Community-Funktionen für registrierte Nutzer.

Funktionen:

- eigene Profilseite
- Vorname und Nachname speichern
- Profilbild/Avatar mit Vorschau und Zuschnitt
- Profilbanner
- öffentliche Profilansicht
- Nutzerübersicht
- Freundschaftsanfragen senden, annehmen und ablehnen
- Freundesliste mit Anzeige, seit wann man befreundet ist
- Schnellzugriff auf Freunde und Freundschaftsanfragen im Profilmenü
- Account-Informationen wie Mitglied seit und letzte Aktivität
- Profil-Statistiken, z. B. Freunde, Chats und Highscores
- Datei-Share Upload-Limit pro Nutzer im Admin einstellbar: 50 MB, 100 MB, 500 MB oder unbegrenzt

---

## 💬 Chats

Das Chat-System ist für direkte Unterhaltungen und kleine Gruppen innerhalb von MyTools gedacht.

Funktionen:

- Direktchats mit befreundeten Nutzern
- Gruppenchats mit mehreren Freunden
- Chatliste mit Direktchat-Startbereich
- Nachrichten senden per Enter
- neue Zeile per Shift + Enter
- automatische Aktualisierung über Polling
- ungelesene Chat-Anzahl im Profilmenü
- eigene Nachrichten löschen
- auf empfangene Nachrichten mit Emojis reagieren
- Reaktionen erneut anklicken, um sie wieder zu entfernen

---

## 📤 Datei-Share

Der Datei-Share erlaubt private Dateifreigaben innerhalb von MyTools.

Funktionen:

- Dateien mit Freunden teilen
- privaten Link für einzelne Freigaben erstellen
- mehrere Dateien auf einmal auswählen oder per Drag & Drop ablegen
- ausgewählte Dateien mit Name, Typ und Größe anzeigen
- Upload-Fortschritt mit Prozentanzeige
- pro Nutzer konfigurierbares Upload-Limit im Django-Admin
- Standardlimit 50 MB pro Datei
- optionale Limits 100 MB, 500 MB oder unbegrenzt
- Speicherung als Datei im Media-Verzeichnis statt als Datenbank-Blob

---

## 🎨 Skribble

Skribble ist ein kleines Zeichen- und Ratespiel innerhalb von MyTools.

Funktionen:

- Lobbys erstellen und teilen
- Freunde einladen
- Spieler können Lobbys verlassen
- Lobby-Ersteller können Lobbys löschen
- Runden starten und neu starten
- Wörter auswählen
- Zeichnen im Browser
- Chat-/Ratebereich für Antworten
- Punktestand und Spielstatus
- Punkteübersicht nach jeder Runde, bevor der Host die nächste Runde startet
- dezenter eigener Hintergrund und Logo

---

## 🎮 Tic Tac Toe

Tic Tac Toe ist ein schnelles 1v1-Spiel für Freunde.

Funktionen:

- Räume erstellen und per Code oder Link teilen
- Freunde einladen
- offene Einladungen auf der Tic-Tac-Toe-Übersicht
- Live-Aktualisierung der Raum- und Einladungsliste ohne Neuladen
- maximal zwei Spieler pro Raum
- automatische Sperre weiterer Einladungen, sobald der Raum voll ist
- Spieler können Räume verlassen
- leere Räume werden automatisch gelöscht
- nur der Host kann Räume löschen
- gelöschte Räume leiten offene Clients automatisch zurück zur Übersicht
- serverseitig geprüfte Züge, Gewinnerkennung und neue Runden

---

## ⚓ Schiffe versenken

Schiffe versenken ist ein taktisches 1v1-Spiel mit privaten Räumen und eigener Spieloberfläche.

Funktionen:

- Räume erstellen und per Code oder Link teilen
- Freunde einladen
- offene Einladungen und eigene Räume mit Live-Aktualisierung
- maximal zwei Spieler pro Raum
- keine weiteren Einladungen, sobald ein zweiter Spieler im Raum ist
- manuelle Flottenplatzierung auf einem 8x8-Feld
- Schiffsauswahl, horizontale/vertikale Ausrichtung, Zufallsplatzierung und Leeren
- serverseitige Validierung der Flotte: richtige Schiffe, keine Überlappung, zusammenhängend und innerhalb des Spielfelds
- abwechselndes Schießen mit Treffer/Wasser/versenkt-Anzeige
- Treffer erlauben einen weiteren Schuss
- Gewinnmeldung als Overlay
- nur der Host kann eine neue Runde starten
- Soundeffekte und Treffer-/Wasser-Effekte im Browser
- gelöschte Räume leiten offene Clients automatisch zurück zur Übersicht

---

## 🔴 Vier gewinnt

Vier gewinnt ist ein animiertes 1v1-Spiel mit privaten Räumen und Live-Aktualisierung.

Funktionen:

- Räume erstellen und per Code oder Link teilen
- Freunde einladen
- offene Einladungen und eigene Räume mit Live-Aktualisierung
- maximal zwei Spieler pro Raum
- rote und gelbe Spielsteine mit klarer Spielerzuordnung
- serverseitig geprüfte Spalten, Züge, Gewinnerkennung und Unentschieden
- Fallanimation für neue Spielsteine
- hervorgehobene Gewinnlinie
- Gewinn- und Unentschieden-Meldung als Overlay
- neue Runde direkt aus dem Ergebnis-Popup starten
- Spieler können Räume verlassen
- nur der Host kann Räume löschen
- gelöschte Räume leiten offene Clients automatisch zurück zur Übersicht

---

## 🧠 Stadt Land Fluss

Stadt Land Fluss ist als gemeinsames Live-Spiel mit echten Runden und manueller Auswertung umgesetzt.

Funktionen:

- Lobbys erstellen und per Code oder Link teilen
- Freunde einladen
- offene Einladungen und eigene Lobbys mit Live-Aktualisierung
- mehrere Spieler pro Lobby
- Kategorien und Rundenzahl beim Erstellen festlegen
- pro Runde zufälliger Buchstabe
- Antwortentwürfe werden zwischengespeichert
- sobald ein Spieler abgibt, ist die Runde für alle beendet
- Auswertung nach Kategorien untereinander
- Spieler entscheiden per Voting, welche Antworten zählen
- Punktevergabe mit 20 Punkten für die einzige gültige Antwort einer Kategorie
- finale Platzierungen nach der letzten Runde
- Spieler können Lobbys verlassen
- nur der Host kann Lobbys neu starten oder löschen
- gelöschte Lobbys leiten offene Clients automatisch zurück zur Übersicht

---

## 🏓 Pong Multiplayer

Pong ist ein schnelles 1v1-Arcade-Spiel mit privaten Räumen, Freundeseinladungen und Profil-/Achievement-Anbindung.

Funktionen:

- Räume erstellen und per Code oder Link teilen
- Freunde direkt aus der Lobby einladen
- offene Einladungen und eigene Räume mit Live-Aktualisierung
- maximal zwei Spieler pro Raum
- Canvas-Spieloberfläche mit Maus-, Touch- und Tastatursteuerung
- serverseitige Ballphysik, Punktewertung und Zielscore
- Rally-Zähler, beste Rally und Gewinner-Overlay
- nur der Host kann Räume löschen oder eine neue Runde starten
- Spieler können Räume verlassen; leere Räume werden automatisch gelöscht
- Header-Benachrichtigung für offene Pong-Einladungen
- Pong-Statistiken in Profil-Spielkarten und eigene Achievements

---

## 📝 Notizen

Die Notizen-App speichert persönliche Notizen direkt in MyTools.

Funktionen:

- Notizen erstellen, bearbeiten und löschen
- Notizen anpinnen
- Notizen archivieren
- Farben und Tags
- Such- und Filterfunktionen
- nutzerbezogene Speicherung

---

## ⚡ Human Benchmark

Die Human-Benchmark-Seite enthält kleine Reaktions- und Geschicklichkeits-Tests.

Funktionen:

- verschiedene Spielmodi
- letzte Ergebnisse pro Spielmodus
- gespeicherte Highscores
- zusätzliche Statistiken je nach Spielmodus
- Bestenliste pro Nutzer

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

## 🎚️ Stream Deck

Die Stream-Deck-Seite ist als Button-Dashboard für schnelle Aktionen gedacht.

Mögliche Einsatzbereiche:

- Mediensteuerung
- Spotify-Verbindung
- lokale Dashboard-Aktionen
- eigene Buttons und Shortcuts
- Steuerung auf Tablet oder Zweitgerät

---

## ⛽ Spritkostenrechner

Der Spritkostenrechner nutzt die **Tankerkönig API**.

Funktionen:

- Tankstellenabfrage über Browser-Standortfreigabe
- Stadtsuche als Alternative zur Standortfreigabe
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
GENIUS_ACCESS_TOKEN=dein_genius_access_token
```

---

## 📐 Einheitenrechner

Der Einheitenrechner bietet schnelle Umrechnungen direkt im Browser.

Beispiele:

- Speichergrößen
- Zeitwerte
- Entfernungen
- Geld-Zeiträume

---

## 📚 Avatar Wiki

Das Avatar Wiki dient als kleine Charakterverwaltung.

Funktionen:

- Charaktere erstellen
- Charaktere bearbeiten
- Charaktere löschen
- Suche und Übersicht
- API-Endpunkte für Charakterdaten

---

## 🏎️ Drift Circuit Pro

Drift Circuit Pro ist ein kleines browserbasiertes Racing-Game.

Funktionen:

- Canvas-basiertes Spiel
- verschiedene Maps
- Nitro
- Drift-Score
- Tastatursteuerung

---

## 🌍 Internationalisierung

MyTools nutzt Django i18n.

Aktuell vorgesehen:

- Deutsch
- Englisch

Nach Änderungen an übersetzbaren Texten:

```bash
python manage.py makemessages -l de
python manage.py makemessages -l en
python manage.py compilemessages
```

Unter Windows müssen dafür die GNU-gettext-Tools installiert sein.

---

## 🎨 Design

Design-Funktionen:

- Dark Mode
- Theme-Editor
- eigene Accent-Farbe
- moderne Kartenlayouts
- responsive Darstellung für Desktop, Tablet und Smartphone
- sticky Header
- überarbeiteter Footer
- Widget-Farbstile und Widget-Layouts

---

## 🐳 Docker Deployment

Produktiv läuft MyTools typischerweise über Docker Compose.

Typische Container:

- `web` für Django/Gunicorn
- `db` für PostgreSQL
- `redis` für Cache/Redis und spätere Echtzeit-/Caching-Funktionen
- `caddy` als Reverse Proxy
- optional `cloudflared` für Cloudflare Tunnel

Start/Rebuild:

```bash
docker compose up -d --build
```

Migrationen ausführen:

```bash
docker compose exec web python manage.py makemigrations
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

---

## ⚙️ Wichtige `.env` Werte

Beispiel:

```env
DEBUG=False
SECRET_KEY=dein_secret_key
ALLOWED_HOSTS=localhost,127.0.0.1,mytools.yfserver.de
CSRF_TRUSTED_ORIGINS=https://mytools.yfserver.de

OPENWEATHER_API_KEY=dein_openweather_api_key
TANKERKOENIG_API_KEY=dein_tankerkoenig_api_key
GENIUS_ACCESS_TOKEN=dein_genius_access_token

DB_NAME=mytools
DB_USER=mytools
DB_PASSWORD=dein_db_passwort
DB_HOST=db
DB_PORT=5432

REDIS_URL=redis://redis:6379/1
```

Secrets gehören nicht ins Git-Repository. Dafür sollte eine `.env.example` ohne echte Zugangsdaten gepflegt werden.


---

## 📱 PWA / installierbare App

MyTools ist als Progressive Web App vorbereitet:

- `manifest.webmanifest` liefert App-Name, Start-URL, Theme-Farbe, Icons und Shortcuts.
- `service-worker.js` wird am Origin-Root ausgeliefert und darf dadurch die komplette App-Scope `/` kontrollieren.
- Die Offline-Seite unter `/offline/` wird vorab gecacht.
- Statische Dateien unter `/static/` werden beim ersten Laden gecacht und danach schneller wiederverwendet.
- Private HTML-Seiten und API-Antworten werden bewusst nicht vorab gecacht.

Nach dem Deployment einmal ausführen:

```bash
python manage.py collectstatic --noinput
```

Dann im Browser prüfen:

```text
https://deine-domain.de/manifest.webmanifest
https://deine-domain.de/service-worker.js
https://deine-domain.de/offline/
```

Für die Installation muss die Seite über HTTPS laufen. Lokal funktioniert der Service Worker auch auf `localhost`.

---

## 🧪 Tests

Tests lokal starten:

```bash
python manage.py test
```

Tests im Docker-Container:

```bash
docker compose exec web python manage.py test
```

---

## 📁 Projektstruktur

Grob:

```text
MyTools/
├── MyTools/
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── app/
│   ├── templates/app/
│   ├── static/app/css/
│   ├── static/app/js/
│   ├── static/app/img/
│   ├── migrations/
│   ├── models.py
│   ├── views.py
│   ├── profile_views.py
│   ├── chat_views.py
│   ├── skribble_views.py
│   ├── tictactoe_views.py
│   ├── battleship_views.py
│   └── urls.py
├── locale/
├── media/
├── docker-compose.yml
├── Dockerfile
├── Caddyfile
├── requirements.txt
└── manage.py
```

---

## 🚀 Ziel

MyTools soll eine persönliche, erweiterbare Web-Toolbox bleiben:

- schnell erreichbar
- gut für Homelab, Alltag und kleine gemeinsame Tools
- nutzerbezogen mit Profilen, Freunden und Chats
- optisch modern
- einfach per Docker deploybar
- Schritt für Schritt um neue Tools erweiterbar


### Color Palette Tool

- Farbauswahl per Standard-Farbpicker
- Bildschirm-Farbaufnahme über die Browser EyeDropper API, wenn unterstützt
- Bild hochladen und Pixel-Farbe direkt im Canvas anklicken
- HEX, RGB und HSL kopieren
- Lokale Palette per `localStorage`
- Kontrastprüfung für weißen und dunklen Text


## Sicherheits-Dashboard und QR-Code Tool

- `/security/`: zeigt 2FA-Status, aktive Sessions, erfolgreiche/fehlgeschlagene Login-Ereignisse und erlaubt das Beenden anderer Sitzungen.
- `/qr-code/`: erstellt QR-Codes für Text, URLs, WLAN-Zugänge und Kontakte mit PNG-Download und anpassbaren Farben.

Nach dem Einspielen ausführen:

```bash
python manage.py migrate
python manage.py test app.tests.SecurityDashboardAndQrToolTests
```

## Roadmap, Achievement-Center und Serverstatus

Neue Bereiche:

- `/roadmap/`: Feature-Ideen einreichen, nach Status/Kategorie filtern, voten, kommentieren und als Admin den Status plus Admin-Notiz pflegen.
- `/achievements/`: persönliches Achievement-Center mit Level, XP-Fortschritt, Kategorien, nächsten Zielen und Top-10-XP-Ranking.
- `/server-status/`: staff-only System-Monitor mit App-/Datenbank-/Cache-Status, Speicherplatz, Laufzeitdaten und App-Zählern.

Nach dem Einspielen ausführen:

```bash
python manage.py migrate
python manage.py test app.tests.RoadmapAchievementAndServerStatusTests
```
