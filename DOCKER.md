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

## Production Deployment

1. Secrets in `.env` setzen (nicht commiten!)
2. `DEBUG=False` in `.env`
3. Gültigen `SECRET_KEY` generieren
4. Echte Domain in `DOMAIN` Variable setzen
5. Optional zusätzliche Hosts in `ALLOWED_HOSTS` konfigurieren
6. `docker compose up -d --build` ausführen

Bei Cloudflare Tunnel muss Caddy selbst kein Let's-Encrypt-Zertifikat beziehen.
