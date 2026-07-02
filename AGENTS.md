# Repository Guidelines

## Project Structure & Module Organization

This is a Django 5.2 project named `MyTools`. Project configuration lives in `MyTools/` (`settings.py`, `urls.py`, ASGI/WSGI). The main app is `app/`, with domain code split across `models.py`, `views/`, `forms/`, `consumers.py`, `routing.py`, utilities, and `app/management/commands/`. Templates are in `app/templates/`, static assets in `app/static/app/`, translations in `locale/`, and tests in `app/tests.py` plus focused files such as `app/test_werewolf.py`. Docker and deployment files are at the repository root.

## Build, Test, and Development Commands

- `python -m venv .venv` and `.venv\Scripts\activate`: create and activate a local Windows virtualenv.
- `pip install -r requirements.txt`: install Django, Channels, Redis, image, and API dependencies.
- `python manage.py migrate`: apply database migrations.
- `python manage.py runserver 127.0.0.1:8090`: run the local Django development server.
- `python manage.py test app`: run the Django test suite for the app.
- `python scripts/verify.py --test-label app`: run the quality gate: Django check, migration drift check, tests, collectstatic dry-run, and JS syntax checks when Node is available.
- `docker compose up -d --build`: build and start the production-like stack.

## Coding Style & Naming Conventions

Use conventional Django/Python style: 4-space indentation, `snake_case` functions and variables, `PascalCase` classes, and clear model/view names. Keep feature-specific view logic in the matching module under `app/views/`. Name templates and static assets by feature, for example `budget_tracker.html`, `budget_tracker.js`, and `budget_tracker.css`.

## Testing Guidelines

Tests use Django's built-in `TestCase` and `SimpleTestCase`; no separate pytest setup is present. Name tests `test_<behavior>` and group related cases in descriptive classes. Mock external APIs and services such as weather, Genius, Voicemod, Redis, or Channels where practical. For model, view, permission, realtime, and template changes, add or update focused tests.

## Commit & Pull Request Guidelines

Recent history uses short, descriptive subjects in English or German, often imperative or summary style, with occasional prefixes such as `fix:`. Keep commits focused, for example `Fix failed tests` or `fix: fehlende Uebersetzungen ergaenzen`. Pull requests should include a summary, tests run, migration notes, linked issues, and screenshots for visible UI changes.

## Security & Configuration Tips

Keep secrets in `.env`; do not commit API keys, production credentials, or generated databases. Local and CI checks commonly use `USE_SQLITE=True`, `USE_LOCAL_CACHE=True`, dummy API keys, and a test `SECRET_KEY`. When adding settings, document required environment variables in `README.md`.
