# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

MyTools is a personal Django dashboard (German-first UI, English also supported) bundling home shortcuts/widgets, profiles, friends, chats, notes, file sharing, calculators/converters, small API-backed tools, and ~15 single/multiplayer games behind one Django app. Realtime features (chat, live presence, Pong) run over Django Channels/Daphne. Production runs Postgres + Redis behind Caddy in Docker; local dev typically uses SQLite + in-memory cache/channel layer.

## Commands

### Setup
```bash
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements.txt
copy .env.example .env   # then set DEBUG=True, USE_SQLITE=True, USE_LOCAL_CACHE=True for local dev
python manage.py migrate
python manage.py compilemessages   # requires gettext tools on Windows
python manage.py collectstatic --noinput
```

### Run
```bash
python manage.py runserver 127.0.0.1:8090
```

### Tests
```bash
python manage.py test app                          # full suite (app/tests.py + app/test_*.py)
python manage.py test app.tests.ChatEnhancementTests   # single test class
python manage.py test app.tests.ChatEnhancementTests.test_something  # single test method
```

### Quality gate (run before considering a change done)
```bash
python scripts/verify.py                # Django check, migration-drift check, full test suite, collectstatic dry-run, JS syntax check (skips JS check if node is missing)
python scripts/verify.py --quick         # same, but runs only the focused security/media/PWA/rate-limit/chat/file-share test subset (see QUICK_TEST_LABELS in scripts/verify.py)
python manage.py makemigrations --check --dry-run   # fails if a model change needs a migration that wasn't generated
```
This is what CI (`.github/workflows/deploy.yml`) runs on every push/PR, so run it locally first.

### i18n
After changing any translatable string:
```bash
python manage.py makemessages -l de
python manage.py makemessages -l en
python manage.py compilemessages
```
JS-heavy areas (e.g. Nebula Forge Tycoon) additionally keep translation strings in template/JSON data files under `app/static/app/data/` so `makemessages` can still pick them up — check there when adding UI strings inside `.js` files.

### Changelog
The `/changelog/` page reads a generated JSON file, not manual entries:
```bash
python manage.py generate_git_changelog --limit 0
# or: python scripts/generate_git_changelog.py --limit 0
```
Regenerate after commits if you want the changelog page to reflect them locally; production regenerates this automatically during deploy.

### Docker
```bash
docker compose up -d --build
docker compose exec web python manage.py migrate
docker compose exec web python manage.py collectstatic --noinput
docker compose logs -f web
```
See [DOCKER.md](DOCKER.md) for the full production checklist (env vars, Cloudflare Tunnel, troubleshooting).

## Architecture

### Single app, split by concern
Everything lives in the `app` Django app (project config is in `MyTools/`). Rather than one `views.py`/`forms.py`, logic is split into feature modules:
- `app/views/*.py` — one module per feature/game (e.g. `chat.py`, `werewolf.py`, `budget.py`, `security.py`, `moderation.py`); `app/urls.py` (~550 lines) wires all of them together.
- `app/forms/*.py` — grouped as `core.py`, `chat.py`, `platform.py`, `profile.py` (not one-per-feature like views).
- `app/models.py` is a single ~4000-line file with ~80 models covering every feature (profiles, chats, every game's Game/Player/Invite trio, budget, shopping list, vacation planner, security events, moderation, etc.). When adding a feature, models still go here, following the existing per-feature grouping in the file.
- Root-level utility modules handle cross-cutting concerns: `access_control.py` (publish/unpublish/hide tools & games), `rate_limits.py` + `middleware.py` (`RateLimitMiddleware`, `LoginRequiredMiddleware`, CSP/permissions-policy middleware), `presence_utils.py` (online status), `trash_utils.py` (soft delete), `notification_utils.py`, `achievement_utils.py`, `totp_utils.py` (2FA), `image_optimization.py`, `voicemod.py`, `open_food_facts.py`.

### Access control (publish / unpublish / hidden)
`app/access_control.py` defines `ACCESS_CONTROL_ITEMS`, a registry mapping a feature `key` to its URL names, label, icon and category. `SiteAccessSettings` (in `models.py`) stores a status per key: **published**, **unpublished**, or **hidden** (`"Niemand"` is a legacy value treated as unpublished). `LoginRequiredMiddleware`/view-level checks consult this registry to gate access, and the moderation dashboard (`/moderation/`, staff-only) edits it. When adding a new tool/game, register its URL names here so it can be moderated and shown/hidden consistently.

### Soft delete (trash)
Models that support recovery inherit `TrashableModel` (`app/models.py`), which adds a soft-delete flag and an `ActiveTrashManager` default manager (so normal querysets exclude trashed rows automatically). `trash_utils.py` and the `/trash/` views handle restore/permanently-delete/empty-trash. Currently used by shortcuts, notes, file shares, and home widgets — follow this pattern for new trashable content instead of hard-deleting.

### Realtime (Channels)
`app/routing.py` defines three websocket routes (`app/consumers.py`): `ws/live-status/`, `ws/chat/<room_id>/`, `ws/pong/<code>/`. `ASGI_APPLICATION` (`MyTools/asgi.py`) is the entrypoint used by Daphne in production; `WSGI_APPLICATION` also exists but Daphne serves both HTTP and WS in one process. `CHANNEL_LAYERS` and `CACHES` switch between Redis (production) and in-memory/locmem (tests, or when `USE_LOCAL_CACHE=True`) based on `settings.IS_TESTING` / env vars — mirror that pattern rather than hardcoding a backend when touching realtime code. Other multiplayer games (Tic Tac Toe, Uno, Kniffel, Werewolf, etc.) are turn-based and use polling/HTTP with server-side move validation rather than a dedicated websocket consumer.

### Settings (`MyTools/settings.py`)
Almost everything is env-driven via `.env` (loaded with `python-dotenv`); see the `.env` block in [README.md](README.md) for the full variable list. Notable behavior baked into settings:
- `IS_TESTING = "test" in sys.argv` flips DB (SQLite), cache/channel layer (locmem/in-memory), and reCAPTCHA (Google's public test keys) automatically — you don't need to set `USE_SQLITE`/`USE_LOCAL_CACHE` when running `manage.py test`, only when using `runserver` locally.
- `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS`/`DOMAIN` are derived from env with helper functions (`hostname_from_value`, `is_public_host`) — trusted origins are auto-derived as `https://<host>` for any public host in `ALLOWED_HOSTS`/`DOMAIN`.
- CSP is enforced via custom `ContentSecurityPolicyMiddleware`/`PermissionsPolicyMiddleware` in `app/middleware.py`, policy string built from `DEFAULT_CSP_POLICY`, starts in report-only mode (`CSP_REPORT_ONLY=True`) because some templates still use inline scripts/styles.
- Google OAuth (`allauth`) and Google Analytics are feature-flagged: they only activate when their respective env vars are set (`GOOGLE_OAUTH_ENABLED`, `GOOGLE_ANALYTICS_ENABLED`).

### Media privacy
Public media (profile pictures, shortcut icons, avatar-wiki images) is served directly by Caddy/static fallback. Anything private (chat attachments, file-share uploads, custom timer sounds, profile gallery images) is stored under `media/private/` and served through a permission-checked Django view — never assume `/media/<path>` is safe to expose for new private uploads.

### Tests
No pytest — plain `django.test.TestCase`/`SimpleTestCase`. Most tests live in one large `app/tests.py` (~6700 lines, ~35 test classes, one per feature/game); a few feature areas have their own file (`app/test_shopping_list.py`, `app/test_vacation_planner.py`, `app/test_werewolf.py`). `BaseTestCase` in `tests.py` is the common base with shared setup helpers. `scripts/verify.py`'s `--quick` mode runs a fixed subset of test classes (`QUICK_TEST_LABELS`) chosen to cover security/media/PWA/rate-limit/chat/file-share behavior fast — update that list if you add a test class that should be part of the fast gate.

### CI/CD
`.github/workflows/deploy.yml` runs on a self-hosted runner: OSV dependency scan (warn-only, never blocks) → Django tests (`scripts/verify.py --test-label app`) on every push/PR → Docker build → deploy (only on push to `main`, via `git reset --hard origin/main` + `docker compose up -d --build` on the server, with a Caddy health-check retry loop). `quality.yml` is manual-only (`workflow_dispatch`). `develop` branch pushes are intentionally excluded from the test/build/deploy pipeline.
