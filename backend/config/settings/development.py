"""Local development settings."""

import os

from . import base as base_settings
from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = [*base_settings.ALLOWED_HOSTS, "testserver"]
SECURE_SSL_REDIRECT = os.getenv("DJANGO_SECURE_SSL_REDIRECT", "false").lower() in {
    "1",
    "true",
    "yes",
}
SESSION_COOKIE_SECURE = os.getenv("DJANGO_SECURE_COOKIES", "false").lower() in {
    "1",
    "true",
    "yes",
}
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
