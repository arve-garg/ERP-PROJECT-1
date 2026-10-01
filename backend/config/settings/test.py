"""Test settings that keep fixture creation fast without changing production security."""

from .development import *  # noqa: F403

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
