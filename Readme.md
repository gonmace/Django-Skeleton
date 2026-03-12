# Django Skeleton

Esqueleto base para proyectos Django con Tailwind v4 + DaisyUI v5, listo para desarrollo local y despliegue en producción con Docker + PostgreSQL.

## Stack

- **Backend:** Django 5.1+, Gunicorn
- **Base de datos:** SQLite (dev) / PostgreSQL 17 (prod)
- **Estilos:** Tailwind CSS v4 + DaisyUI v5
- **Archivos estáticos:** Whitenoise
- **Seguridad:** django-axes, django-csp, headers HTTP
- **Monitoreo:** Sentry
- **Producción:** Docker Compose + Nginx (gzip)

## Estructura

```
├── core/               # Configuración del proyecto
│   ├── settings.py     # Settings único (dev y prod por variables de entorno)
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── home/               # App principal
│   ├── sitemaps.py     # Sitemap de vistas estáticas
│   └── migrations/
├── theme/              # App Tailwind
│   └── static_src/
│       ├── package.json
│       └── src/styles.css
├── templates/
│   ├── base.html       # Base con OG tags, favicon, meta description
│   ├── 404.html
│   ├── 500.html
│   └── robots.txt
├── static/
│   └── img/
│       ├── favicon.svg         # Reemplazar con tu favicon
│       └── og-default.jpg      # Reemplazar con tu imagen OG (1200x630)
├── staticfiles/        # Salida de collectstatic (generado)
├── media/              # Uploads de usuarios (generado)
├── requirements.txt        # Dependencias de producción
├── requirements-dev.txt    # Dependencias de desarrollo
├── Dockerfile          # Multi-stage: Node (CSS) + Python
├── docker-compose.yml
├── entrypoint.sh       # Migraciones + Gunicorn
├── nginx.conf          # Plantilla nginx con gzip
├── deploy.sh           # Script de despliegue en VPS
└── Makefile
```

## Desarrollo local

### 1. Clonar y configurar entorno

```bash
git clone <repo>
cd <proyecto>
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
make install
```

### 2. Variables de entorno

```bash
cp .env.example .env
```

Para desarrollo basta con un `.env` mínimo:

```env
DEBUG=True
```

### 3. Iniciar el servidor

```bash
make dev
```

O manualmente en dos terminales:

```bash
# Terminal 1 — watcher de Tailwind
python manage.py tailwind start

# Terminal 2 — servidor Django
python manage.py migrate
python manage.py runserver
```

Acceder en: http://127.0.0.1:8000

## Producción (VPS)

### 1. Configurar el `.env`

```bash
cp .env.example .env
nano .env
```

Variables obligatorias en producción:

```env
PROJECT_NAME=miproyecto
DOMAIN=tudominio.com
APP_PORT=8000
ADMIN_URL=mi-panel-secreto/

DEBUG=False
SECRET_KEY=una-clave-secreta-segura

POSTGRES_DB=miproyecto_db
POSTGRES_USER=miproyecto_user
POSTGRES_PASSWORD=contraseña-segura

# Opcional — monitoreo de errores
SENTRY_DSN=https://...@sentry.io/...
```

### 2. Desplegar

```bash
make deploy
```

El script hace automáticamente:
1. `git pull` para actualizar el código
2. Genera `{PROJECT_NAME}.conf` a partir de `nginx.conf`
3. Copia la config a `/etc/nginx/sites-available/` y crea el symlink
4. Valida y recarga nginx
5. Reconstruye los contenedores Docker (el Dockerfile compila el CSS con Node)

### 3. SSL con Certbot (manual, primera vez)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d tudominio.com -d www.tudominio.com
```

## Settings

El archivo `core/settings.py` se adapta automáticamente según las variables de entorno:

| Variable presente | Comportamiento |
|---|---|
| `DEBUG=True` | SQLite, email en consola, Tailwind y browser-reload activos |
| `POSTGRES_DB` definido | Usa PostgreSQL |
| `EMAIL_HOST` definido | Usa backend SMTP |
| `SENTRY_DSN` definido | Activa monitoreo de errores |
| `DEBUG=False` | HSTS, CSRF seguro, sin herramientas de dev |

## Personalizar antes de usar

- `static/img/favicon.svg` — reemplazar con el favicon del proyecto
- `static/img/og-default.jpg` — imagen por defecto para redes sociales (1200×630px)
- `ADMINS` en `settings.py` — cambiar el email del administrador
- `LANGUAGE_CODE` y `TIME_ZONE` en `settings.py` — ajustar a tu región

## Comandos útiles

```bash
make install      # pip install + tailwind install
make dev          # migrate + tailwind start + runserver
make migrate      # python manage.py migrate
make migrations   # python manage.py makemigrations
make superuser    # python manage.py createsuperuser
make collect      # collectstatic
make deploy       # bash deploy.sh
make logs         # docker compose logs -f django
make down         # docker compose down
```

```bash
# Nueva app
python manage.py startapp nombre_app

# Acceder al contenedor
docker compose exec django bash

# Backup de la base de datos
docker compose exec postgres pg_dump -U $POSTGRES_USER $POSTGRES_DB > backup.sql
```
