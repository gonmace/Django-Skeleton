# CLAUDE.md

## Comandos clave

```bash
# Setup y dev
make setup          # genera .env interactivo (primera vez)
make install        # pip install requirements-dev + tailwind install
make dev-up         # levanta Redis + PostgreSQL + n8n/MCP según .env
make dev            # dev-up (Postgres+Redis en Docker) + migrate + tailwind + runserver
make dev-check      # verifica estado del entorno

# Django
make migrate / migrations / superuser / shell / collect

# Producción
make nginx          # configura nginx (SOLO la primera vez — certbot modifica este archivo)
make deploy         # pull + build + backup si hay migraciones + healthcheck + rollback auto
make backup / restore FILE=... / rollback [TAG=sha]
make n8n-update     # actualiza n8n (rebuild imagen + restart, preserva volumen)
make n8n-export     # exporta workflows dev a n8n/workflows/
```

On Windows: `NPM_BIN_PATH = r'C:\Program Files\nodejs\npm.cmd'` en `settings.py` dentro del bloque `if DEBUG:`.

## Arquitectura

`core/settings.py` único — comportamiento por variables de entorno:
- Sin `POSTGRES_DB` → SQLite | con `POSTGRES_DB` → PostgreSQL
- `POSTGRES_MODE=host` → contenedores usan `host.docker.internal`
- Sin `EMAIL_HOST` → consola | con `EMAIL_HOST` → SMTP
- `DEBUG=True` → browser-reload, tailwind activo
- `DEBUG=False` → HSTS, CSP estricto, IP real de axes vía `X-Real-IP`
- axes siempre con handler de DB: bloqueos visibles/borrables en admin (Axes → Access attempts); `make axes-reset` como respaldo

**Docker Compose profiles** (gestionados automáticamente por `deploy.sh`):
| Profile | Servicio | Condición |
|---------|----------|-----------|
| `postgres` | PostgreSQL | `POSTGRES_MODE=container` |
| `n8n` | n8n | `N8N_DOMAIN` definido |
| `n8n-mcp` | n8n-MCP | `N8N_MCP_ENABLED=true` + n8n activo |
| — | Redis + Django | Siempre activos |

**Puertos:** `APP_PORT` (8000), `N8N_PORT` (8001), `N8N_MCP_PORT` (8002). Todos bindean a `127.0.0.1` en producción. Redis no expone puerto al exterior.

**Static files:** Whitenoise `CompressedManifestStaticFilesStorage` → hashes en filenames + `.gz` pre-comprimidos. nginx sirve `/static/` con `gzip_static on`. Cache `immutable` 365d es seguro por los hashes.

**Hot reload dev:** `make dev` corre `tailwind start &` + `runserver` (con `trap` que cierra Tailwind al salir). Cambios CSS → Tailwind recompila → refrescar el browser.

**Tailwind/DaisyUI:** v4.2 / v5.5. Deps en `devDependencies` de `package.json`. En producción el Dockerfile compila CSS en stage Node y copia solo el CSS al stage Python (sin node_modules en prod).

**n8n:** subdominio propio, imagen custom con Python 3.12, comparte PostgreSQL (DB `n8n`). `N8N_ENCRYPTION_KEY` no cambiar nunca. Actualizar con `make n8n-update`.

**Media/CDN:** app `cdn` — storage por defecto `ConfigurableMediaStorage` delega en disco local o S3 según `MediaStorageConfig` (singleton editable en el admin, cacheado en Redis). Siempre usar `campo.url`. `MediaCspMiddleware` va después de `CSPMiddleware`. `make sync-media` migra archivos locales al bucket.

**Deploy:** imagen etiquetada con SHA git (`${PROJECT_NAME}_app:<sha>`), `/healthz` como healthcheck, contenedor no-root (UID 1000; `staticfiles/` y `media/` deben ser de 1000). CSP en formato django-csp 4 (`CONTENT_SECURITY_POLICY`). PostgreSQL fijo en 17.

**nginx:** `make nginx` solo una vez — certbot lo modifica para SSL y `deploy.sh` nunca lo toca.

**Al agregar apps Django:** añadir a `INSTALLED_APPS` + `@source "../../../<app>"` en `theme/static_src/src/styles.css`.
