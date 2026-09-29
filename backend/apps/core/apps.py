"""Core platform Django app."""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"

    def ready(self) -> None:
        """Connect audit event handlers when Django starts."""
        from django.db.models.signals import post_migrate

        from apps.core import signals  # noqa: F401

        post_migrate.connect(signals.create_default_roles, sender=self)
