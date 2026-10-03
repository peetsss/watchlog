"""
WSGI config for watchlog.

Uses the project settings dispatcher (`watchlog.settings`) so DJANGO_ENV
selects dev/prod correctly.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "watchlog.settings")

application = get_wsgi_application()
