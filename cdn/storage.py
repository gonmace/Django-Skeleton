from urllib.parse import urlparse

from django.conf import settings
from django.core.files.storage import FileSystemStorage, Storage

from .models import get_media_config

_DELEGATED = (
    'open', 'save', 'path', 'delete', 'exists', 'listdir', 'size', 'url',
    'get_accessed_time', 'get_created_time', 'get_modified_time',
    'get_available_name', 'get_alternative_name', 'get_valid_name', 'generate_filename',
    'is_name_available',
)


def _origin(url):
    p = urlparse(url)
    return f'{p.scheme}://{p.netloc}'


def media_origin(cfg):
    """Origen (scheme://host) desde el que el navegador cargará los archivos, o None si es el propio sitio."""
    if cfg['cdn_url']:
        return _origin(cfg['cdn_url'])
    if cfg['mode'] != 's3':
        return None
    bucket, endpoint, region = cfg['s3_bucket'], cfg['s3_endpoint_url'], cfg['s3_region']
    if endpoint:
        ep = urlparse(endpoint)
        return f'{ep.scheme}://{ep.netloc}' if cfg['s3_path_style'] else f'{ep.scheme}://{bucket}.{ep.netloc}'
    return f'https://{bucket}.s3.{region}.amazonaws.com' if region else f'https://{bucket}.s3.amazonaws.com'


def build_backend(cfg):
    if cfg['mode'] == 's3':
        from storages.backends.s3 import S3Storage

        opts = {
            'bucket_name': cfg['s3_bucket'],
            'access_key': cfg['s3_access_key'],
            'secret_key': cfg['s3_secret_key'],
            'endpoint_url': cfg['s3_endpoint_url'] or None,
            'region_name': cfg['s3_region'] or None,
            'location': cfg['s3_location'].strip('/'),
            'querystring_auth': False,   # archivos públicos (URLs sin firma, cacheables por la CDN)
            'default_acl': None,
            'file_overwrite': False,
        }
        if cfg['s3_path_style']:
            opts['addressing_style'] = 'path'
        if cfg['cdn_url']:
            parsed = urlparse(cfg['cdn_url'])
            opts['custom_domain'] = parsed.netloc
            opts['url_protocol'] = f'{parsed.scheme}:'
        return S3Storage(**opts)

    base_url = settings.MEDIA_URL
    if cfg['cdn_url']:
        base_url = cfg['cdn_url'].rstrip('/') + settings.MEDIA_URL
    return FileSystemStorage(location=settings.MEDIA_ROOT, base_url=base_url)


class ConfigurableMediaStorage(Storage):
    """Storage por defecto: delega en disco local o en S3 según lo configurado en el admin.
    La configuración se relee (con caché) en cada operación: los cambios aplican sin reiniciar."""

    def __init__(self):
        self._built_for = None
        self._built = None

    def _backend(self):
        cfg = get_media_config()
        key = tuple(sorted(cfg.items()))
        if key != self._built_for:
            self._built = build_backend(cfg)
            self._built_for = key
        return self._built


def _delegate(name):
    def method(self, *args, **kwargs):
        return getattr(self._backend(), name)(*args, **kwargs)
    method.__name__ = name
    return method


for _name in _DELEGATED:
    setattr(ConfigurableMediaStorage, _name, _delegate(_name))
