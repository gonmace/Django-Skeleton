from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache


def index(request):
    return render(request, 'home/index.html')


@never_cache
def healthz(request):
    """Healthcheck para Docker/deploy: verifica DB y cache."""
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        cache.set('healthz', 1, 10)
        if cache.get('healthz') != 1:
            raise RuntimeError('cache no responde')
    except Exception:
        return JsonResponse({'status': 'error'}, status=503)
    return JsonResponse({'status': 'ok'})
