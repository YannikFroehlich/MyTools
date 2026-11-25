# Docker Build Anleitung und Verwendung

## Vorbereitung

1. **Umgebungsvariablen konfigurieren:**
   ```bash
   cp .env.example .env
   # .env bearbeiten und Werte anpassen
   ```

2. **Wichtige Production-Werte setzen:**
   - `DEBUG=False`
   - `SECRET_KEY` mit einem echten Secret
   - `DOMAIN`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`
   - PostgreSQL-Werte `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST=db`, `DB_PORT=5432`
   - `REDIS_URL=redis://redis:6379/0`
   - optionale API-Keys wie `OPENWEATHER_API_KEY`, `TANKERKOENIG_API_KEY`, `GENIUS_API_KEY`

## Docker Services starten

### Production Mode
```bash
docker compose up -d --build
```

### Development Mode (mit Hot-Reload)
```bash
docker compose -f docker-compose.yml up
```

### Logs anschauen
```bash
docker compose logs -f web
```

## Datenbank-Migrationen

Migrationen laufen automatisch beim Container-Start. Falls manuell nötig:
```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py compilemessages
docker compose exec web python manage.py collectstatic --noinput
docker compose exec web python manage.py createsuperuser
```

## Statische Dateien und Media

```bash
# Statische Dateien sammeln
docker compose exec web python manage.py collectstatic --noinput

# Volumes anschauen
docker compose exec web ls -la /app/app/static/
docker compose exec web ls -la /app/media/
```

Caddy liefert nur öffentliche Medienordner direkt aus. Private Uploads liegen unter `/app/media/private/` oder in nicht veröffentlichten Media-Unterordnern und werden über Django-Views geprüft.

## Services herunterfahren

```bash
docker compose down
```

### Mit Datenlöschung
```bash
docker compose down -v
```

## Zugriff

- **Web-Anwendung**: https://deine-domain.example (mit Cloudflare Tunnel)
- **Django Admin**: https://deine-domain.example/admin
- **Interner Caddy-Test**:
  ```bash
  docker compose exec -T caddy sh -c 'wget -q --spider --header="Host: ${DOMAIN:-localhost}" http://127.0.0.1/'
  ```

Caddy veroeffentlicht keinen Port auf dem Host. Cloudflared erreicht den Dienst
innerhalb des Docker-Netzwerks unter `http://caddy:80`.

## Troubleshooting

### Port bereits in Benutzung
```bash
docker compose down
lsof -i :80
kill -9 <PID>
```

### Datenbankfehler
```bash
docker compose down -v
docker compose up -d --build
```

### Cloudflare Tunnel prüfen
Setze `DOMAIN` und `CLOUDFLARE_TUNNEL_TOKEN` in `.env`. Cloudflare stellt außen HTTPS bereit,
intern leitet der Tunnel an Caddy weiter.

## Production auf yfsrv1

MyTools läuft auf `yfsrv1` als Docker-Stack unter `/opt/mytools` hinter einem eigenen
Cloudflare Tunnel. Caddy veröffentlicht keinen Host-Port und kollidiert deshalb nicht mit den
anderen Diensten auf yfsrv1 (RoundRush-Caddy auf `80`/`443`, Lunora auf `8090` usw.).

Deployt wird per Auto-Pull: `deploy/mytools-auto-deploy.timer` startet alle 2 Minuten
`scripts/auto-deploy.sh`. Das Skript holt `origin/main`. Wenn es einen neuen Commit gibt, macht es Folgendes:

1. Checkout per Fast-Forward aktualisieren und den Git-Changelog erzeugen
2. Neues `web`-Image bauen und `manage.py check` sowie `makemigrations --check` darin ausführen
3. PostgreSQL-Dump nach `/var/backups/mytools/` schreiben (die letzten 14 bleiben)
4. `docker compose up -d --wait` ausführen (Migrationen laufen beim Start von `web`)

Wenn ein Schritt fehlschlägt, laufen die alten Container weiter. Der Commit wird dann als
fehlgeschlagen gemerkt und erst mit dem nächsten neuen Commit auf `main` wieder versucht.
Jeder Merge auf `main` geht also live.

### Einmalige Einrichtung

Docker mit Compose-Plugin ist auf yfsrv1 schon installiert. Alle Befehle laufen als root (`sudo -i`).

1. **Deploy-Key anlegen** (Repo ist privat). Den Public Key in GitHub unter
   *Settings → Deploy keys* **ohne** Schreibrecht hinzufügen:
   ```bash
   ssh-keygen -t ed25519 -N "" -C "mytools@yfsrv1" -f /root/.ssh/mytools_deploy
   cat /root/.ssh/mytools_deploy.pub
   ```
2. **Repo klonen:**
   ```bash
   GIT_SSH_COMMAND="ssh -i /root/.ssh/mytools_deploy -o IdentitiesOnly=yes" \
     git clone --branch main git@github.com:YannikFroehlich/MyTools.git /opt/mytools
   git -C /opt/mytools config core.sshCommand "ssh -i /root/.ssh/mytools_deploy -o IdentitiesOnly=yes"
   ```
3. **`.env` anlegen** (neu, nichts vom alten Server übernehmen):
   ```bash
   cd /opt/mytools
   cp .env.example .env && chmod 600 .env
   python3 -c "import secrets; print(secrets.token_urlsafe(50))"   # für SECRET_KEY
   python3 -c "import secrets; print(secrets.token_urlsafe(32))"   # für DB_PASSWORD
   ```
   Mindestens diese Werte setzen:
   ```ini
   SECRET_KEY=<neu>
   DEBUG=False
   DOMAIN=mytools.yfserver.de
   ALLOWED_HOSTS=mytools.yfserver.de,localhost,127.0.0.1
   CSRF_TRUSTED_ORIGINS=https://mytools.yfserver.de
   USE_SQLITE=False
   USE_LOCAL_CACHE=False
   DB_PASSWORD=<neu>
   CLOUDFLARE_TUNNEL_TOKEN=<Token des Tunnels>
   SPOTIFY_REDIRECT_URI=https://mytools.yfserver.de/stream-deck/
   ```
   `localhost,127.0.0.1` muss in `ALLOWED_HOSTS` bleiben, sonst schlägt der Healthcheck von `web` fehl.
   E-Mail, reCAPTCHA und API-Keys nach Bedarf ergänzen.
4. **Cloudflare Tunnel:** In Zero Trust einen Tunnel anlegen, z. B. `mytools-yfsrv1`, und den Token in `.env` eintragen.
   Als Public Hostname `mytools.yfserver.de` auf **`http://caddy:80`** setzen.
   Wenn du stattdessen den alten Tunnel weiterverwendest, auf dem alten Server vorher `docker compose down` ausführen.
   Sonst bedienen zwei Server dieselbe Domain mit getrennten Datenbanken.
5. **Auto-Deploy installieren und ersten Deploy starten:**
   ```bash
   install -m 0644 deploy/mytools-auto-deploy.service deploy/mytools-auto-deploy.timer /etc/systemd/system/
   systemctl daemon-reload
   systemctl start mytools-auto-deploy.service     # erster Build, dauert ein paar Minuten
   journalctl -u mytools-auto-deploy.service -n 50 --no-pager
   systemctl enable --now mytools-auto-deploy.timer
   ```
6. **Admin anlegen:**
   ```bash
   docker compose exec web python manage.py createsuperuser
   ```
7. **Prüfen:** `docker compose ps` zeigt alles als `healthy`/`running`, und https://mytools.yfserver.de lädt.

### Betrieb

```bash
systemctl list-timers mytools-auto-deploy.timer          # nächster Lauf
journalctl -u mytools-auto-deploy.service -f             # Deploy-Logs
systemctl start mytools-auto-deploy.service              # sofort deployen
rm /var/lib/mytools-auto-deploy/last-failed-commit       # fehlgeschlagenen Commit erneut versuchen
gunzip -c /var/backups/mytools/<datei>.sql.gz | docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'   # Backup in leere DB einspielen
```

Gesichert wird nur die Datenbank. Uploads im Volume `mytools_media_volume` sind nicht im Backup.

Bei Cloudflare Tunnel muss Caddy selbst kein Let's-Encrypt-Zertifikat beziehen.
