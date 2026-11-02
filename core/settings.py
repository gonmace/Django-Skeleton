import os
from decouple import config, Csv

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(PROJECT_DIR)

_SECRET_KEY_DEFAULT = 'django-insecure-default-only-for-dev-run-make-setup'
SECRET_KEY = config('SECRET_KEY', default=_SECRET_KEY_DEFAULT)

DEBUG = config('DEBUG', default=False, cast=bool)

# Validar solo cuando existe .env (entorno configurado) pero SECRET_KEY no fue definido.
# Sin .env = instalación inicial, el default es aceptable.
if SECRET_KEY == _SECRET_KEY_DEFAULT and os.path.exists(os.path.join(BASE_DIR, '.env')):
    raise ValueError("SECRET_KEY no está en .env. Ejecuta 'make setup' para generarlo.")

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='', cast=Csv())

ADMIN_URL = config('ADMIN_URL', default='admin/')

# Application definition

INSTALLED_APPS = [
    'home',
    'cdn',
    'axes',

    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'csp.middleware.CSPMiddleware',
    'cdn.middleware.MediaCspMiddleware',  # añade la CDN configurada en el admin al CSP
    'django.contrib.sessions.middleware.SessionMiddleware',
    'axes.middleware.AxesMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

INSTALLED_APPS += ['tailwind', 'theme']
TAILWIND_APP_NAME = 'theme'

if DEBUG:
    INSTALLED_APPS += ['django_browser_reload']
    MIDDLEWARE += ['django_browser_reload.middleware.BrowserReloadMiddleware']
    INTERNAL_IPS = ['127.0.0.1', '::1']
    import sys
    if sys.platform == 'win32':
        NPM_BIN_PATH = r'C:\Program Files\nodejs\npm.cmd'

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# Database: SQLite por defecto en dev, PostgreSQL si se define POSTGRES_DB
if config('POSTGRES_DB', default=''):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config('POSTGRES_DB'),
            'USER': config('POSTGRES_USER'),
            'PASSWORD': config('POSTGRES_PASSWORD'),
            'HOST': config('POSTGRES_HOST', default='postgres'),
            'PORT': config('POSTGRES_PORT', default='5432'),
            'CONN_MAX_AGE': 60,
            'CONN_HEALTH_CHECKS': True,
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'es'
TIME_ZONE = 'America/La_Paz'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
WHITENOISE_MANIFEST_STRICT = not DEBUG  # True en prod: rechaza archivos sin entrada en manifest

STORAGES = {
    'staticfiles': {
        # CompressedManifestStaticFilesStorage: hashes en filenames (cache-busting seguro)
        # + archivos .gz pre-generados que nginx sirve con gzip_static on
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
    # Media: disco local por defecto; S3/CDN configurable desde el admin (app 'cdn')
    'default': {
        'BACKEND': 'cdn.storage.ConfigurableMediaStorage',
    },
}

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Email: consola en dev, SMTP en prod si se configura EMAIL_HOST
if config('EMAIL_HOST', default=''):
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = config('EMAIL_HOST')
    EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
    EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
    EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
    EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
    DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@example.com')
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# ── Seguridad ──────────────────────────────────────────────────────────────────
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='', cast=Csv())

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_REDIRECT_EXEMPT = [r'^healthz$']  # healthcheck interno de Docker (HTTP plano)

X_FRAME_OPTIONS = 'DENY'

# ── Redis (cache, sesiones) ───────────────────────────────────────────────────
# En dev sin .env, se conecta a localhost:6379 (Docker Desktop expone el puerto al host).
# En producción, .env siempre define REDIS_URL=redis://redis:6379/0 (nombre del servicio Docker).
REDIS_URL = config('REDIS_URL', default='redis://localhost:6379/0')

if DEBUG and not config('REDIS_URL', default=''):
    # Dev sin Redis: permite 'runserver' sin contenedores activos.
    CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
else:
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': REDIS_URL,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            },
        }
    }

# cached_db: lectura rápida desde Redis y respaldo en DB (un reinicio de Redis no desloguea a nadie).
SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'
SESSION_CACHE_ALIAS = 'default'

# ── django-axes (protección brute force) ──────────────────────────────────────
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # hora
AXES_LOCKOUT_PARAMETERS = ['ip_address', 'username']
AXES_RESET_ON_SUCCESS = True

# Handler de base de datos en todos los entornos: los intentos fallidos quedan en el admin
# (Axes → Access attempts) y un superusuario desbloquea borrando el registro del bloqueado.
# (El handler de caché no guarda nada en DB, así que no se podría gestionar desde el admin.)
AXES_HANDLER = 'axes.handlers.database.AxesDatabaseHandler'

if not DEBUG:
    # Tras nginx, REMOTE_ADDR es la IP del gateway Docker (igual para todos): sin esto un
    # atacante bloquearía a todos los usuarios. nginx sobrescribe X-Real-IP con la IP real
    # y gunicorn solo escucha en 127.0.0.1, así que el header es confiable.
    AXES_IPWARE_META_PRECEDENCE_ORDER = ['HTTP_X_REAL_IP', 'REMOTE_ADDR']

# ── Content Security Policy ───────────────────────────────────────────────────
# Formato django-csp >= 4.0
CONTENT_SECURITY_POLICY = {
    'DIRECTIVES': {
        'default-src': ["'self'"],
        'script-src': ["'self'"],
        'style-src': ["'self'"],
        'img-src': ["'self'", 'data:'],
        'font-src': ["'self'"],
        'connect-src': ["'self'"] if not DEBUG else ["'self'", 'ws://localhost:*', 'ws://127.0.0.1:*'],
    },
}

# ── Integración n8n (opcional) ───────────────────────────────────────────────
N8N_URL = config('N8N_URL', default='')
N8N_API_KEY = config('N8N_API_KEY', default='')
N8N_WEBHOOK_URL = config('N8N_WEBHOOK_URL', default='')

# ── Admins y logging ──────────────────────────────────────────────────────────
ADMIN_EMAIL = config('ADMIN_EMAIL', default='')
ADMINS = [('Admin', ADMIN_EMAIL)] if ADMIN_EMAIL else []
MANAGERS = ADMINS

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {'()': 'django.utils.log.RequireDebugFalse'}
    },
    'formatters': {
        'simple': {'format': '{asctime} {levelname} {name} {message}', 'style': '{'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'simple'},
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler',
        },
    },
    # Errores visibles en 'docker logs'; email a admins solo si hay ADMIN_EMAIL.
    'loggers': {
        'django': {'handlers': ['console'], 'level': 'INFO'},
        'django.request': {
            'handlers': ['console'] + (['mail_admins'] if ADMINS else []),
            'level': 'ERROR',
            'propagate': False,
        },
    },
}
