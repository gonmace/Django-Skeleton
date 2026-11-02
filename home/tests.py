from django.conf import settings
from django.test import TestCase, override_settings


@override_settings(
    SECURE_SSL_REDIRECT=False,
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class HomeTests(TestCase):
    def test_index(self):
        self.assertEqual(self.client.get('/').status_code, 200)

    def test_healthz(self):
        response = self.client.get('/healthz')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})

    def test_sitemap(self):
        self.assertEqual(self.client.get('/sitemap.xml').status_code, 200)

    def test_robots_no_expone_admin(self):
        response = self.client.get('/robots.txt')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(settings.ADMIN_URL.strip('/') + '/', response.content.decode().replace('Sitemap', ''))


@override_settings(
    SECURE_SSL_REDIRECT=False,
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class AxesAdminTests(TestCase):
    """Un usuario bloqueado por axes se puede desbloquear desde el admin."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        self.login_url = f'/{settings.ADMIN_URL}login/'
        self.superuser = get_user_model().objects.create_superuser('boss', 'boss@example.com', 'pass-12345-xyz')

    def _fail(self, username='intruso'):
        return self.client.post(self.login_url, {'username': username, 'password': 'mal'})

    def test_bloqueo_y_desbloqueo_desde_admin(self):
        from axes.models import AccessAttempt
        for _ in range(settings.AXES_FAILURE_LIMIT):
            self._fail()
        self.assertEqual(self._fail().status_code, 429)  # bloqueado
        self.assertTrue(AccessAttempt.objects.filter(username='intruso').exists())

        # El superusuario (otro IP) ve el intento en el admin y lo borra
        from django.test import Client
        admin_client = Client(REMOTE_ADDR='10.0.0.99')
        admin_client.force_login(self.superuser)
        changelist = admin_client.get('/%saxes/accessattempt/' % settings.ADMIN_URL)
        self.assertContains(changelist, 'intruso')
        attempt = AccessAttempt.objects.get(username='intruso')
        resp = admin_client.post(
            '/%saxes/accessattempt/' % settings.ADMIN_URL,
            {'action': 'delete_selected', '_selected_action': [attempt.pk], 'post': 'yes'},
        )
        self.assertEqual(resp.status_code, 302)

        # Ya no está bloqueado
        self.assertEqual(self._fail().status_code, 200)
