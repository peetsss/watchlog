import os

from channels.routing import ProtocolTypeRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "watchlog.settings")

django_asgi_app = get_asgi_application()


def _websocket_application() -> object:
    from channels.auth import AuthMiddlewareStack
    from channels.routing import URLRouter
    from channels.security.websocket import AllowedHostsOriginValidator

    from lobby.routing import websocket_urlpatterns

    return AllowedHostsOriginValidator(AuthMiddlewareStack(URLRouter(websocket_urlpatterns)))


application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": _websocket_application(),
    }
)
