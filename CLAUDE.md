# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
make install      # pip install -r requirements-dev.txt + tailwind install
make dev          # migrate + tailwind start (background) + runserver
make migrate      # python manage.py migrate
make migrations   # python manage.py makemigrations
make superuser    # python manage.py createsuperuser
make collect      # collectstatic
make deploy       # bash deploy.sh (VPS only)
make logs         # docker compose logs -f django
make down         # docker compose down
```

In development, run Tailwind and Django in separate terminals:
```bash
# Terminal 1
python manage.py tailwind start

# Terminal 2
python manage.py runserver
```

On Windows, `NPM_BIN_PATH = r'C:\Program Files\nodejs\npm.cmd'` is set in settings.py inside the `if DEBUG:` block.

## Architecture

Single `core/settings.py` — no separate dev/prod files. Behavior adapts via environment variables:
- `DEBUG=True` → SQLite, console email, Tailwind + browser-reload enabled
- `POSTGRES_DB` defined → PostgreSQL
- `EMAIL_HOST` defined → SMTP backend
- `SENTRY_DSN` defined → Sentry enabled
- `DEBUG=False` → HSTS, secure CSRF, no dev tools

**Tailwind setup** (`django-tailwind` + Tailwind CSS v4 + DaisyUI v5):
- Source CSS: `theme/static_src/src/styles.css`
- Output CSS: `theme/static/css/dist/styles.css` (served by Django's staticfiles from the `theme` app)
- `{% load tailwind_tags %}` + `{% tailwind_css %}` in `templates/base.html` loads the CSS
- When adding new Django apps, add `@source "../../../<app_name>"` to `styles.css` so Tailwind scans its templates
- `@source not "../static"` prevents a recompile loop from the output file

**Static files:** Whitenoise serves static files in production (configured in `STORAGES`). `STATICFILES_DIRS` points to the root `static/` folder.

**Security:** django-axes (brute-force lockout after 5 failures, 1h cooldown), django-csp (Content Security Policy headers), HSTS in production.

**Admin URL** is randomized via `ADMIN_URL` env var (default: `admin/`). Exposed in `robots.txt` via template context.

**Production:** Docker Compose + Gunicorn (`entrypoint.sh`) + Nginx (`nginx.conf` template with `{{DOMAIN}}`, `{{APP_PORT}}`, `{{PROJECT_DIR}}` placeholders filled by `deploy.sh`). CSS is compiled inside a multi-stage Dockerfile (Node stage → Python stage).
