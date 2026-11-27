#!/usr/bin/env bash
# Replaces the dev instance's data with a copy of production (Postgres + media volume).
# Production is only read. Runs as root from mytools-dev-refresh.timer at 03:00 Europe/Berlin;
# see DOCKER.md, "Dev-Instanz".
set -Eeuo pipefail

DEV_DIR="${MYTOOLS_DEV_DIR:-/opt/mytools-dev}"
PROD_DB_CONTAINER="mytools_db"
DEV_DB_CONTAINER="mytools_dev_db"
DEV_REDIS_CONTAINER="mytools_dev_redis"
PROD_MEDIA_VOLUME="mytools_media_volume"
DEV_MEDIA_VOLUME="mytools-dev_media_volume"
# Shared with the dev auto-deploy, which skips its run while this holds the lock.
LOCK_FILE="${MYTOOLS_DEV_LOCK_FILE:-/run/mytools-dev-auto-deploy.lock}"

cd "${DEV_DIR}"

# Dev now holds real users' data: it must never send them mail.
if ! grep -q '^EMAIL_BACKEND_MODE=console$' .env; then
    echo "Abbruch: ${DEV_DIR}/.env verschickt echte E-Mails; erst EMAIL_BACKEND_MODE=console setzen." >&2
    exit 1
fi

exec 9>"${LOCK_FILE}"
flock 9

dump=$(mktemp)
trap 'rm -f -- "${dump}"; docker compose up -d --wait --wait-timeout 300 || true' EXIT

docker compose stop web caddy
docker compose up -d --wait db redis

docker exec "${PROD_DB_CONTAINER}" sh -c 'pg_dump -Fc -U "$POSTGRES_USER" -d "$POSTGRES_DB"' > "${dump}"
docker exec -i "${DEV_DB_CONTAINER}" sh -c '
    set -e
    dropdb -U "$POSTGRES_USER" --force --if-exists "$POSTGRES_DB"
    createdb -U "$POSTGRES_USER" "$POSTGRES_DB"
    pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-acl --exit-on-error
' < "${dump}"

# Any image with sh and cp will do; postgres:16-alpine is always present here.
docker run --rm --entrypoint sh \
    -v "${PROD_MEDIA_VOLUME}:/from:ro" -v "${DEV_MEDIA_VOLUME}:/to" \
    postgres:16-alpine -c 'find /to -mindepth 1 -delete && cp -a /from/. /to/'

# Dev code may be ahead of production. Drop copied OAuth tokens so dev can never act on
# users' Google accounts, and dev's cached sessions and rate limits.
docker compose run --rm --no-deps web sh -c '
    python manage.py migrate --noinput &&
    python manage.py shell -c "from allauth.socialaccount.models import SocialToken; SocialToken.objects.all().delete()"
'
docker exec "${DEV_REDIS_CONTAINER}" redis-cli FLUSHALL >/dev/null

echo "Dev-Daten aus der Produktion übernommen."
