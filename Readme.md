# Django Skeleton

Skeleton para desplegar Django en un VPS con nginx como reverse proxy. Incluye soporte opcional para n8n (automatización) y n8n-MCP (integración con Claude Code / clientes MCP).

## Stack

| Componente | Tecnología |
|---|---|
| Framework | Django 6.1+ (Python 3.14) |
| Servidor WSGI | Gunicorn (`GUNICORN_WORKERS`, default 3), contenedor no-root |
| Base de datos | PostgreSQL 17 (contenedor o host) |
| Cache / Sesiones | Redis 8 (sesiones `cached_db`) |
| CSS | Tailwind CSS v4.2 + DaisyUI v5.5 |
| Archivos estáticos | Whitenoise (`CompressedManifestStaticFilesStorage`) + nginx (`gzip_static`) |
| Seguridad | django-axes (handler de DB, gestionable desde el admin), django-csp, HSTS |
| Hot reload (dev) | django-browser-reload |
| Automatización (opcional) | n8n |
| MCP Server (opcional) | n8n-MCP |
| Reverse proxy | Nginx (host) + Let's Encrypt |

---

## Quick Start (VPS)

```bash
# 1. Clonar el proyecto
git clone <repo> miproyecto && cd miproyecto

# 2. Configurar — genera .env de forma interactiva
make setup

# 3. Configurar nginx (SOLO la primera vez — no volver a ejecutar tras certbot)
make nginx

# 4. Obtener certificado SSL
sudo certbot --nginx -d tudominio.com
# Si n8n está habilitado, agregar también: -d n8n.tudominio.com

# 5. Desplegar
make deploy
```

Para deploys posteriores solo se necesita `make deploy` (ver sección *Deploy*). **Nunca volver a ejecutar `make nginx`** después de que certbot configuró el SSL.

---

## Desarrollo local

### Opción A — Mínimo (solo SQLite, sin contenedores)

Ideal para trabajar en templates, vistas y lógica de negocio sin necesitar base de datos completa.

```bash
make install           # instala dependencias Python + Tailwind
make setup             # genera .env (elige SQLite / sin n8n)
make dev               # migrate + tailwind watcher + runserver
```

### Opción B — Completo (PostgreSQL + Redis en Docker)

```bash
make install           # instala dependencias Python + Tailwind
make setup             # genera .env con PostgreSQL
make dev               # levanta Redis + PostgreSQL (+ n8n/MCP) y arranca Django + Tailwind
make dev-check         # verifica que todo esté corriendo
make dev-down          # detiene los contenedores de desarrollo
```

En ambos casos Django corre nativo en el host (no en Docker). Redis en Docker es accesible en `localhost:6379`.

### Hot reload

`make dev` lanza Tailwind en background y Django con `django-browser-reload`:

- **Python y templates**: Django recarga automáticamente → el browser se refresca solo
- **CSS**: Tailwind recompila el CSS → refrescar el browser manualmente

### Dos terminales (alternativa a `make dev`)

```bash
# Terminal 1 — watcher CSS
python manage.py tailwind start

# Terminal 2 — servidor Django
python manage.py runserver
```

### Comportamiento automático según `.env`

| Variable | Ausente | Presente |
|---|---|---|
| `POSTGRES_DB` | SQLite | PostgreSQL |
| `N8N_DOMAIN` | n8n deshabilitado | n8n en contenedor |
| `REDIS_URL` | `localhost:6379` | valor configurado |

---

## PostgreSQL: contenedor vs host

Controla el comportamiento con `POSTGRES_MODE` en `.env`:

### Contenedor Docker (default)
```env
POSTGRES_MODE=container
POSTGRES_HOST=postgres
```
PostgreSQL corre en Docker, incluido en `docker-compose.yml` con el profile `postgres`.

### PostgreSQL del servidor host
```env
POSTGRES_MODE=host
POSTGRES_HOST=host.docker.internal
```
Los contenedores se conectan al PostgreSQL instalado en el VPS via `host.docker.internal`. El contenedor postgres **no se inicia**.

**Requisitos para modo host:**
1. `listen_addresses` en `postgresql.conf` debe incluir la IP del bridge Docker (o `*`)
2. `pg_hba.conf` debe aceptar conexiones desde la red Docker (`172.16.0.0/12`):
   ```
   host  all  all  172.16.0.0/12  md5
   ```
3. Crear manualmente las bases de datos del proyecto y `n8n`

---

## Servicios opcionales

Los servicios opcionales se activan via Docker Compose profiles. `deploy.sh` los gestiona automáticamente según el `.env`.

### n8n

Habilitar en `.env`:
```env
N8N_DOMAIN=n8n.tudominio.com
N8N_ENCRYPTION_KEY=clave-generada-por-setup
```

- Subdominio propio con imagen custom (Python 3.12 integrado para Code nodes)
- Comparte PostgreSQL con base de datos separada (`n8n`)
- Workflows en `n8n/workflows/` se importan automáticamente al arrancar
- Exportar workflows del dev: `make n8n-export`
- **`N8N_ENCRYPTION_KEY` debe mantenerse constante** — cambiarla invalida credenciales guardadas

### n8n-MCP

Requiere n8n habilitado. Habilitar en `.env`:
```env
N8N_MCP_ENABLED=true
N8N_API_KEY=<generar en n8n: Settings > API>
N8N_MCP_AUTH_TOKEN=token-generado-por-setup
```

Expone un servidor MCP sobre HTTP en `https://n8n.tudominio.com/mcp`. Permite integrar n8n con Claude Code u otros clientes MCP.

---

## Puertos

Los servicios usan puertos consecutivos desde `APP_PORT`. Para cambiarlos, ajusta solo `APP_PORT` en `.env` (los demás se calculan en `setup.sh`).

| Servicio | Puerto default | Variable |
|---|---|---|
| Django | 8000 | `APP_PORT` |
| n8n | 8001 | `N8N_PORT` |
| n8n-MCP | 8002 | `N8N_MCP_PORT` |
| Redis | interno | — |
| PostgreSQL | 5432 | `POSTGRES_HOST_PORT` (solo dev) |

En producción todos los puertos bindean a `127.0.0.1` — solo accesibles via nginx. Redis no expone puerto al exterior en ningún entorno.

---

## Actualizar n8n

n8n no tiene actualización desde la UI web. El proceso es:

```bash
make n8n-update   # rebuild imagen custom + restart contenedor
```

Esto reconstruye la imagen con la última versión de n8n, reinicia el contenedor y preserva todos los datos en `./volumes/n8n`. Para controlar la versión exacta, edita la imagen base en `docker/n8n.Dockerfile`.

---

## Tailwind + DaisyUI

Las versiones se gestionan en `theme/static_src/package.json` (devDependencies):

- **Tailwind CSS**: `^4.2.2`
- **DaisyUI**: `^5.5.19`

En **desarrollo**: `make install` → `npm install` instala los paquetes.

En **producción**: el Dockerfile usa `npm ci && npm run build` en una stage Node aislada. El CSS compilado y minificado se copia a la imagen Python final. **Los módulos npm no están en la imagen de producción.**

Para actualizar versiones: edita `package.json`, corre `npm update` en `theme/static_src/` y regenera `package-lock.json`.

---

## Archivos estáticos

Whitenoise + nginx trabajando en conjunto:

1. `collectstatic` genera archivos con hashes en el nombre (`styles.abc123.css`) y versiones `.gz` pre-comprimidas
2. nginx intercepta `/static/` y sirve directamente desde `staticfiles/` con `gzip_static on` — usa los `.gz` sin comprimir on-the-fly
3. Cache `immutable` con 365 días es seguro porque los filenames cambian en cada deploy

---

## Redis

Redis es siempre activo y optimiza tres aspectos clave:

| Aspecto | Sin Redis | Con Redis |
|---|---|---|
| Cache | `LocMemCache` por worker (no compartido) | Cache compartido entre los 3 workers Gunicorn |
| Sesiones | Escrituras a PostgreSQL en cada request | Cache en memoria, sin tocar la DB |

---

## Variables de entorno

| Variable | Requerida | Descripción |
|---|---|---|
| `PROJECT_NAME` | Sí | Nombre usado en contenedores y nginx |
| `DOMAIN` | Sí | Dominio principal de Django |
| `SECRET_KEY` | Sí | Clave secreta de Django |
| `DEBUG` | No | `False` en prod (default) |
| `ALLOWED_HOSTS` | Sí | Dominios permitidos (CSV) |
| `CSRF_TRUSTED_ORIGINS` | Sí | Orígenes confiables CSRF (CSV) |
| `ADMIN_URL` | No | URL del admin (default: `admin/`) |
| `APP_PORT` | No | Puerto Django (default: `8000`) |
| `POSTGRES_MODE` | No | `container` o `host` (default: `container`) |
| `POSTGRES_DB` | Sí | Nombre de la base de datos |
| `POSTGRES_USER` | Sí | Usuario PostgreSQL |
| `POSTGRES_PASSWORD` | Sí | Contraseña PostgreSQL |
| `POSTGRES_HOST` | No | Host PostgreSQL (default: `postgres`) |
| `POSTGRES_PORT` | No | Puerto PostgreSQL (default: `5432`) |
| `REDIS_URL` | No | URL de Redis (default: `redis://redis:6379/0`) |
| `N8N_DOMAIN` | No | Subdominio de n8n (activa el servicio) |
| `N8N_PORT` | No | Puerto externo n8n (default: `8001`) |
| `N8N_ENCRYPTION_KEY` | Si n8n | Clave de cifrado de n8n (**no cambiar**) |
| `N8N_MCP_ENABLED` | No | `true` para habilitar n8n-MCP |
| `N8N_MCP_PORT` | No | Puerto externo MCP (default: `8002`) |
| `N8N_API_KEY` | Si MCP | API key de n8n para el servidor MCP |
| `N8N_MCP_AUTH_TOKEN` | Si MCP | Token de autenticación del MCP |
| `N8N_URL` | No | URL de n8n para llamadas desde Django |
| `EMAIL_HOST` | No | SMTP host (activa email backend) |

---

## Comandos

| Comando | Descripción |
|---|---|
| `make setup` | Wizard interactivo — genera `.env` |
| `make install` | Instala dependencias Python y Tailwind |
| `make dev-up` | Levanta servicios de desarrollo (Docker) |
| `make dev-down` | Detiene servicios de desarrollo |
| `make dev-logs` | Logs de servicios de desarrollo |
| `make dev-check` | Verifica estado del entorno de desarrollo |
| `make dev` | `dev-up` + migrate + tailwind start + runserver |
| `make sync-media` | Copia `media/` local al bucket S3 configurado en el admin |
| `make axes-reset` | Desbloquea todos los accesos bloqueados por axes |
| `make migrate` | Ejecuta migraciones |
| `make migrations` | Crea migraciones |
| `make superuser` | Crea superusuario |
| `make shell` | Django shell |
| `make collect` | collectstatic |
| `make db-shell` | Abre psql (PostgreSQL) o indica sqlite3 |
| `make db-reset` | Elimina SQLite y vuelve a migrar |
| `make n8n-export` | Exporta workflows de n8n dev a `n8n/workflows/` |
| `make n8n-update` | Actualiza n8n en producción (rebuild + restart) |
| `make check-ports` | Verifica disponibilidad de puertos |
| `make nginx` | Instala config nginx (**solo primera vez**) |
| `make deploy` | Despliega en VPS (git pull + verifica puertos + rebuild) |
| `make logs` | Logs de Django en producción |
| `make down` | Detiene contenedores de producción (todos los profiles) |
| `make backup` | Backup de PostgreSQL a `backups/*.sql.gz` (retención: 10) |
| `make restore FILE=...` | Restaura un backup (destructivo, pide confirmación) |
| `make rollback [TAG=sha]` | Vuelve a la imagen anterior de Django (no revierte migraciones) |
| `make ps` / `make restart` | Estado / reinicio de Django en producción |

---

## Estructura

```
├── core/                    # Configuración Django (settings, urls, wsgi)
├── home/                    # App principal (index, sitemaps, healthz)
├── cdn/                     # Config de media/CDN desde el admin (storage dinámico)
├── templates/               # Templates globales (base, 404, 500, robots.txt)
├── theme/                   # App Tailwind (static_src/ con npm build)
├── static/                  # Assets estáticos (img, css)
├── staticfiles/             # collectstatic output (generado)
├── media/                   # Uploads de usuarios (generado)
├── n8n/workflows/           # Workflows n8n versionados en git
├── volumes/                 # Datos persistentes de contenedores (gitignored)
│   └── n8n/                 # Datos de n8n (workflows, credenciales)
├── db/                      # Datos PostgreSQL en producción (gitignored)
├── docker/
│   ├── n8n.Dockerfile       # n8n con Python 3.12 (para Code nodes)
│   ├── n8n-export.sh        # Script de exportación de workflows
│   └── init-db.sql          # Crea la base de datos n8n al iniciar postgres
├── Dockerfile               # Multi-stage: Node (CSS build) → Python (prod)
├── docker-compose.yml       # Producción: postgres* + redis + django + n8n* + mcp*
├── docker-compose.dev.yml   # Desarrollo: postgres* + redis + n8n* + mcp*
├── entrypoint.sh            # Espera PG + Redis, collectstatic, migrate, gunicorn
├── nginx.conf               # Template nginx Django
├── nginx-n8n.conf           # Template nginx n8n (con marcador {{MCP_BLOCK}})
├── nginx-n8n-mcp.conf       # Location block para n8n-MCP (SSE)
├── nginx-deploy.sh          # Genera e instala config nginx (solo primera vez)
├── deploy.sh                # Despliegue VPS (build, backup condicional, healthcheck, rollback)
├── scripts/                 # lib.sh, backup.sh, restore.sh, rollback.sh
├── setup.sh                 # Wizard de configuración inicial
├── check-ports.sh           # Verifica disponibilidad de puertos
├── Makefile
├── .env.example             # Plantilla de variables de entorno
└── requirements.txt         # Dependencias Python de producción
```

`*` servicio opcional (Docker Compose profile)

---

## Deploy

`make deploy` (`deploy.sh`) despliega con downtime de segundos:

1. `git pull --ff-only` y re-ejecución del script actualizado.
2. Build de la imagen **mientras la versión actual sigue sirviendo**; se etiqueta con el SHA de git.
3. **Backup condicional**: solo si hay migraciones pendientes y la DB ya tiene datos. `BACKUP=always|never` lo fuerza u omite (`make deploy BACKUP=always`). Si el backup falla, el deploy se aborta sin tocar nada.
4. `docker compose up -d` recrea solo lo que cambió (sin `down`).
5. Espera el healthcheck (`/healthz`: DB + cache). Si falla y no se aplicaron migraciones → **rollback automático** a la imagen anterior; si se aplicaron, indica `make restore` / `make rollback`.
6. Conserva las 3 últimas imágenes de la app y registra `.deploy/previous`.

Backups periódicos independientes del deploy (cron diario, 03:00):

```cron
0 3 * * * cd /ruta/al/proyecto && bash scripts/backup.sh diario >/dev/null
```

Las versiones de n8n / n8n-MCP son `latest` por defecto; fíjalas con `N8N_VERSION` / `N8N_MCP_VERSION` en `.env`. PostgreSQL se mantiene en 17 (la 18 cambia el layout de datos; migrar requiere dump/restore: `make backup` → cambiar imagen → `make restore`).

---

## Media y CDN (configurable desde el admin)

Por defecto los uploads se guardan en el propio VPS (`media/`, servidos por nginx en `/media/`). Desde el admin, **Almacenamiento de media / CDN → Configuración**, se puede cambiar sin tocar código ni reiniciar:

| Modo | Qué hace |
|---|---|
| **Este servidor** (defecto) | Archivos en el VPS. Con *URL de la CDN* definida, las URLs públicas pasan por una CDN *pull* que apunta al sitio (ej. `https://cdn.midominio.com` → se sirve `/media/…`). |
| **S3-compatible** | Archivos en un bucket (AWS S3, Cloudflare R2, DigitalOcean Spaces, MinIO…). Con *URL de la CDN*, las URLs usan el dominio personalizado del bucket. |

- Los cambios aplican de inmediato (config cacheada en Redis, invalidada al guardar). Al guardar en modo S3 se prueba la conexión y se avisa si falla.
- El origen de la CDN/bucket se agrega solo al CSP (`img-src`, `media-src`).
- Los archivos ya subidos **no se mueven solos** al cambiar de modo: `make sync-media` copia `media/` al bucket (no borra nada).
- En plantillas/código usa siempre `campo.url` (no `{{ MEDIA_URL }}`) para que respete la configuración.
- Las credenciales S3 se guardan en la base de datos: usa una clave limitada a ese bucket.

---

## Notas de seguridad

- **Admin URL aleatorio** — generado por `setup.sh` (no se publica en `robots.txt`)
- **Brute-force protection** — django-axes bloquea tras 5 intentos fallidos (1h de cooldown). Los intentos se guardan en la DB: en el admin, **Axes → Access attempts** (filtro *Locked Out*); para desbloquear a alguien, selecciona su registro y bórralo. Si el bloqueado es el propio admin: `make axes-reset`. En producción la IP real se toma de `X-Real-IP` (nginx)
- **CSP headers** — política estricta vía django-csp, relajada en DEBUG para browser-reload
- **HSTS** — habilitado en producción (1 año, incluye subdominios)
- **Static files** — hashes en filenames + cache `immutable` 365 días, seguros porque cambian en cada deploy

---

## Checklist de personalización

- [ ] Cambiar favicon: reemplazar `static/img/favicon.svg`
- [ ] Definir `ADMIN_EMAIL` en `.env` para recibir errores 500 por email (requiere SMTP)
- [ ] Ajustar zona horaria y locale → `TIME_ZONE`, `LANGUAGE_CODE` en `settings.py`
- [ ] Personalizar tema DaisyUI en `theme/static_src/src/styles.css`
- [ ] Al agregar nuevas apps: `INSTALLED_APPS` + `@source "../../../<app>"` en `styles.css`
