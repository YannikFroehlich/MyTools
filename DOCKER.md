# Docker Build Anleitung und Verwendung

## Vorbereitung

1. **Umgebungsvariablen konfigurieren:**
   ```bash
   cp .env.example .env
   # .env bearbeiten und Werte anpassen
   ```

2. **Django-Einstellungen für Production aktualisieren:**
   - In `MyTools/settings.py`:
     ```python
     DEBUG = os.getenv('DEBUG', 'False') == 'True'
     ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost').split(',')
     SECRET_KEY = os.getenv('SECRET_KEY')
     DATABASES = {
         'default': {
             'ENGINE': 'django.db.backends.postgresql',
             'NAME': os.getenv('DB_NAME', 'mytools'),
             'USER': os.getenv('DB_USER', 'postgres'),
             'PASSWORD': os.getenv('DB_PASSWORD', 'postgres'),
             'HOST': 'db',
             'PORT': '5432',
         }
     }
     CACHES = {
         'default': {
             'BACKEND': 'django_redis.cache.RedisCache',
             'LOCATION': os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
         }
     }
     ```

## Docker Services starten

### Production Mode
```bash
docker-compose up -d
```

### Development Mode (mit Hot-Reload)
```bash
docker-compose -f docker-compose.yml up
```

### Logs anschauen
```bash
docker-compose logs -f web
```

## Datenbank-Migrationen

Migrationen laufen automatisch beim Container-Start. Falls manuell nötig:
```bash
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser
```

## Statische Dateien und Media

```bash
# Statische Dateien sammeln
docker-compose exec web python manage.py collectstatic --noinput

# Volumes anschauen
docker-compose exec web ls -la /app/app/static/
docker-compose exec web ls -la /app/media/
```

## Services herunterfahren

```bash
docker-compose down
```

### Mit Datenlöschung
```bash
docker-compose down -v
```

## Zugriff

- **Web-Anwendung**: http://localhost oder https://localhost (mit Caddy)
- **Django Admin**: http://localhost/admin
- **API/Backend**: http://localhost:8000 (direkt)

## Troubleshooting

### Port bereits in Benutzung
```bash
docker-compose down
lsof -i :80
kill -9 <PID>
```

### Datenbankfehler
```bash
docker-compose down -v
docker-compose up -d
```

### Caddy SSL-Fehler (lokal)
Caddy erstellt automatisch selbstsignierte Zertifikate für localhost. Browser-Warnung ist normal.

## Production Deployment

1. Secrets in `.env` setzen (nicht commiten!)
2. `DEBUG=False` in `.env`
3. Gültigen `SECRET_KEY` generieren
4. `ALLOWED_HOSTS` konfigurieren
5. Echte Domain in `DOMAIN` Variable setzen
6. `docker-compose up -d` ausführen

Caddy bezieht automatisch Let's Encrypt Zertifikate für echte Domains.
