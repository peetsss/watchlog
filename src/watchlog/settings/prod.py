import os

from .base import *

DEBUG = False

if not SECRET_KEY.strip() or "replace-in-production!!!" in SECRET_KEY:
    raise RuntimeError("You must set DJANGO_SECRET_KEY in production!")

ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",")
if not ALLOWED_HOSTS or ALLOWED_HOSTS == [""]:
    raise RuntimeError("DJANGO_ALLOWED_HOSTS must be set in production")

if not REDIS_URL:
    raise RuntimeError("REDIS_URL must be set in production for lobby websockets")

SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_REDIRECT_EXEMPT = [r"^health/$"]
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
