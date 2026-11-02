from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import models

CACHE_KEY = 'cdn:media-config'
CACHE_TTL = 300


class MediaStorageConfig(models.Model):
    """Configuración única (singleton) de dónde se guardan y sirven los archivos de media."""

    class Mode(models.TextChoices):
        LOCAL = 'local', 'Este servidor (VPS)'
        S3 = 's3', 'Almacenamiento S3-compatible (S3, R2, Spaces, MinIO…)'

    mode = models.CharField('Dónde guardar los archivos', max_length=10, choices=Mode.choices, default=Mode.LOCAL)
    cdn_url = models.URLField(
        'URL de la CDN (opcional)', blank=True,
        help_text=(
            'Si se define, las URLs públicas de los archivos usan este dominio. '
            'Modo "Este servidor": CDN que apunta al sitio como origen (pull), ej. https://cdn.midominio.com '
            '(se le añade /media/). Modo S3: dominio personalizado del bucket.'
        ),
    )

    s3_endpoint_url = models.URLField(
        'Endpoint', blank=True,
        help_text='Vacío para AWS S3. Ej. R2: https://<cuenta>.r2.cloudflarestorage.com · Spaces: https://nyc3.digitaloceanspaces.com',
    )
    s3_bucket = models.CharField('Bucket', max_length=100, blank=True)
    s3_region = models.CharField('Región', max_length=50, blank=True, help_text='Ej. us-east-1 (R2: auto)')
    s3_access_key = models.CharField('Access key', max_length=200, blank=True)
    s3_secret_key = models.CharField(
        'Secret key', max_length=200, blank=True,
        help_text='Se guarda en la base de datos. Usa una clave con permisos solo sobre este bucket.',
    )
    s3_location = models.CharField('Carpeta dentro del bucket', max_length=100, blank=True, help_text='Opcional, ej. media')
    s3_path_style = models.BooleanField(
        'Direccionamiento por ruta (path-style)', default=False,
        help_text='Necesario en MinIO y algunos proveedores. Déjalo desmarcado en AWS, R2 y Spaces.',
    )

    class Meta:
        verbose_name = 'configuración de media / CDN'
        verbose_name_plural = 'configuración de media / CDN'

    def __str__(self):
        return 'Configuración de media / CDN'

    def clean(self):
        if self.mode == self.Mode.S3:
            missing = [label for label, value in (
                ('Bucket', self.s3_bucket), ('Access key', self.s3_access_key), ('Secret key', self.s3_secret_key),
            ) if not value]
            if missing:
                raise ValidationError('El modo S3 requiere: %s.' % ', '.join(missing))

    def save(self, *args, **kwargs):
        self.pk = 1  # singleton
        super().save(*args, **kwargs)
        cache_invalidate()

    def delete(self, *args, **kwargs):
        result = super().delete(*args, **kwargs)
        cache_invalidate()
        return result

    def as_dict(self):
        return {
            'mode': self.mode,
            'cdn_url': self.cdn_url,
            's3_endpoint_url': self.s3_endpoint_url,
            's3_bucket': self.s3_bucket,
            's3_region': self.s3_region,
            's3_access_key': self.s3_access_key,
            's3_secret_key': self.s3_secret_key,
            's3_location': self.s3_location,
            's3_path_style': self.s3_path_style,
        }


DEFAULT_CONFIG = {
    'mode': MediaStorageConfig.Mode.LOCAL, 'cdn_url': '', 's3_endpoint_url': '', 's3_bucket': '',
    's3_region': '', 's3_access_key': '', 's3_secret_key': '', 's3_location': '', 's3_path_style': False,
}


def cache_invalidate():
    try:
        cache.delete(CACHE_KEY)
    except Exception:  # Redis caído: el TTL corto cubre la invalidación
        pass


def get_media_config():
    """Configuración vigente. Cacheada (compartida entre workers) y a prueba de fallos:
    si la tabla aún no existe o la DB falla, se usa el almacenamiento local por defecto."""
    from django.db import DatabaseError, transaction

    try:
        cfg = cache.get(CACHE_KEY)
    except Exception:
        cfg = None
    if cfg is not None:
        return cfg
    try:
        with transaction.atomic():  # savepoint: un error no rompe una transacción en curso
            obj = MediaStorageConfig.objects.first()
    except DatabaseError:
        return dict(DEFAULT_CONFIG)
    cfg = obj.as_dict() if obj else dict(DEFAULT_CONFIG)
    try:
        cache.set(CACHE_KEY, cfg, CACHE_TTL)
    except Exception:
        pass
    return cfg
