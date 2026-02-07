import os

env = os.getenv("DJANGO_ENV", "dev")

if env == "prod" or env == "production":
    from .prod import *
else:
    from .dev import *
