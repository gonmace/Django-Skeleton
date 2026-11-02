from .models import get_media_config
from .storage import media_origin


class MediaCspMiddleware:
    """Añade al CSP el origen de la CDN/bucket configurado en el admin (img-src y media-src).
    Debe ir DESPUÉS de CSPMiddleware en MIDDLEWARE (su respuesta se procesa antes)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        origin = media_origin(get_media_config())
        if origin:
            update = dict(getattr(response, '_csp_update', None) or {})
            update['img-src'] = [origin]
            update['media-src'] = ["'self'", origin]
            response._csp_update = update
        return response
