"""
ASGI config for watchlog.

Uses the project settings dispatcher (`watchlog.settings`) so DJANGO_ENV
selects dev/prod correctly. Serves HTTP plus authenticated lobby websockets.
"""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "watchlog.settings")

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402
from django.core.asgi import get_asgi_application  # noqa: E402

django_asgi_app = get_asgi_application()

from lobby import routing  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(AuthMiddlewareStack(URLRouter(routing.websocket_urlpatterns))),
    }
)
