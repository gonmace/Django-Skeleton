from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.test import Client, TestCase, override_settings

from .models import MediaStorageConfig
from .storage import ConfigurableMediaStorage, media_origin
from .models import get_media_config

TEST_SETTINGS = dict(
    SECURE_SSL_REDIRECT=False,
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    STORAGES={
        'default': {'BACKEND': 'cdn.storage.ConfigurableMediaStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)


@override_settings(**TEST_SETTINGS)
class MediaConfigTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_por_defecto_es_local_en_el_vps(self):
        cfg = get_media_config()
        self.assertEqual(cfg['mode'], 'local')
        storage = ConfigurableMediaStorage()
        self.assertEqual(storage.url('a/b.jpg'), '/media/a/b.jpg')
        self.assertIsNone(media_origin(cfg))

    def test_local_con_cdn_pull(self):
        MediaStorageConfig.objects.create(cdn_url='https://cdn.example.com/')
        storage = ConfigurableMediaStorage()
        self.assertEqual(storage.url('a.jpg'), 'https://cdn.example.com/media/a.jpg')

    def test_cambio_aplica_sin_reiniciar(self):
        storage = ConfigurableMediaStorage()
        self.assertEqual(storage.url('a.jpg'), '/media/a.jpg')
        MediaStorageConfig.objects.create(cdn_url='https://cdn.example.com')
        self.assertEqual(storage.url('a.jpg'), 'https://cdn.example.com/media/a.jpg')

    def test_s3_con_dominio_cdn(self):
        MediaStorageConfig.objects.create(
            mode='s3', s3_bucket='b', s3_access_key='k', s3_secret_key='s',
            s3_endpoint_url='https://acct.r2.cloudflarestorage.com', cdn_url='https://media.example.com',
        )
        storage = ConfigurableMediaStorage()
        self.assertEqual(storage.url('x/y.png'), 'https://media.example.com/x/y.png')

    def test_s3_exige_credenciales(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            MediaStorageConfig(mode='s3').full_clean()

    def test_singleton(self):
        MediaStorageConfig.objects.create(cdn_url='https://a.example.com')
        MediaStorageConfig(cdn_url='https://b.example.com').save()
        self.assertEqual(MediaStorageConfig.objects.count(), 1)
        self.assertEqual(MediaStorageConfig.objects.get().cdn_url, 'https://b.example.com')

    def test_guardar_archivo_local(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp, override_settings(MEDIA_ROOT=tmp):
            storage = ConfigurableMediaStorage()
            name = storage.save('t.txt', ContentFile(b'hola'))
            self.assertTrue(storage.exists(name))
            storage.delete(name)

    def test_csp_incluye_origen_de_la_cdn(self):
        home = self.client.get('/')
        self.assertNotIn('cdn.example.com', home['Content-Security-Policy'])
        MediaStorageConfig.objects.create(cdn_url='https://cdn.example.com')
        response = self.client.get('/')
        csp = response['Content-Security-Policy']
        self.assertIn('img-src', csp)
        self.assertIn('https://cdn.example.com', csp)

    def test_admin_edita_la_configuracion(self):
        user = get_user_model().objects.create_superuser('boss', 'b@example.com', 'pass-12345-xyz')
        client = Client()
        client.force_login(user)
        url = f'/{settings.ADMIN_URL}cdn/mediastorageconfig/add/'
        resp = client.post(url, {'mode': 'local', 'cdn_url': 'https://cdn.example.com', 's3_endpoint_url': '',
                                 's3_bucket': '', 's3_region': '', 's3_access_key': '', 's3_secret_key': '',
                                 's3_location': ''})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(get_media_config()['cdn_url'], 'https://cdn.example.com')
        # El listado redirige al único registro
        self.assertEqual(client.get(f'/{settings.ADMIN_URL}cdn/mediastorageconfig/').status_code, 302)
