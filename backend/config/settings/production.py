"""Production settings with secure defaults."""

import os

from . import base as base_settings
from .base import *  # noqa: F403

DEBUG = False
if (
    base_settings.SECRET_KEY == "unsafe-development-key-change-me"
    or len(base_settings.SECRET_KEY) < 50
):
    raise RuntimeError("Set DJANGO_SECRET_KEY to a unique value of at least 50 characters.")
if not base_settings.ALLOWED_HOSTS or "*" in base_settings.ALLOWED_HOSTS:
    raise RuntimeError("Set DJANGO_ALLOWED_HOSTS to explicit host names.")
SECURE_SSL_REDIRECT = os.getenv("DJANGO_SECURE_SSL_REDIRECT", "true").lower() in {
    "1",
    "true",
    "yes",
}
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
