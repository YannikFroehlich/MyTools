#!/usr/bin/env bash
# Pulls origin/main and redeploys the Docker stack when a new commit is there.
# Runs as root from deploy/mytools-auto-deploy.timer (every 2 minutes).
set -Eeuo pipefail

APP_DIR="${MYTOOLS_APP_DIR:-/opt/mytools}"
BACKUP_DIR="${MYTOOLS_BACKUP_DIR:-/var/backups/mytools}"
BACKUP_KEEP="${MYTOOLS_BACKUP_KEEP:-14}"
STATE_DIR="${MYTOOLS_STATE_DIR:-/var/lib/mytools-auto-deploy}"
LOCK_FILE="${MYTOOLS_LOCK_FILE:-/run/mytools-auto-deploy.lock}"
SUCCESS_STATE="${STATE_DIR}/last-successful-commit"
FAILED_STATE="${STATE_DIR}/last-failed-commit"

install -d -m 0750 "${STATE_DIR}" "${BACKUP_DIR}"

exec 9>"${LOCK_FILE}"
if ! flock --nonblock 9; then
    echo "Ein Deployment läuft bereits; dieser Durchlauf wird übersprungen."
    exit 0
fi

read_state() { [[ -s "$1" ]] && head -n1 "$1" || true; }

cd "${APP_DIR}"

if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
    echo "Abbruch: ${APP_DIR} enthält lokale Änderungen." >&2
    exit 1
fi

GIT_TERMINAL_PROMPT=0 git fetch --quiet --prune origin main
target=$(git rev-parse --verify origin/main)

if [[ "${target}" == "$(read_state "${SUCCESS_STATE}")" ]]; then
    exit 0
fi
if [[ "${target}" == "$(read_state "${FAILED_STATE}")" ]]; then
    echo "${target:0:12} ist schon einmal fehlgeschlagen; warte auf einen neuen Commit."
    exit 0
fi

fail() {
    echo "Deployment von ${target:0:12} fehlgeschlagen." >&2
    printf '%s\n' "${target}" > "${FAILED_STATE}"
    docker compose ps >&2 || true
    docker compose logs --tail=80 web >&2 || true
}
trap fail ERR

echo "Deploye origin/main ${target:0:12}."
git merge --ff-only --quiet origin/main

python3 scripts/generate_git_changelog.py --limit 0 \
    || echo "Git-Changelog konnte nicht erzeugt werden; Deployment läuft weiter."

# Build and check the new image first. Until `up` runs, the old containers keep serving.
docker compose build --pull web
docker compose run --rm --no-deps web python manage.py check
docker compose run --rm --no-deps web python manage.py makemigrations --check --dry-run

# The web container runs migrations on start, so dump the database right before that.
if [[ -n "$(docker compose ps --status running --quiet db)" ]]; then
    backup="${BACKUP_DIR}/db-$(date +%Y%m%d-%H%M%S)-${target:0:12}.sql.gz"
    docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB"' | gzip > "${backup}"
    chmod 0600 "${backup}"
    ls -1t "${BACKUP_DIR}"/db-*.sql.gz | tail -n +"$((BACKUP_KEEP + 1))" | xargs -r rm --
    echo "Datenbank-Backup: ${backup}"
fi

docker compose pull db redis caddy cloudflared
docker compose up -d --remove-orphans --wait --wait-timeout 300

trap - ERR
printf '%s\n' "${target}" > "${SUCCESS_STATE}"
rm -f "${FAILED_STATE}"
docker image prune -f >/dev/null
echo "MyTools ${target:0:12} ist deployt."
