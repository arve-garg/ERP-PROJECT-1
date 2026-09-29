"""Request-local actor context used by model audit signals."""

from contextvars import ContextVar
from typing import Any

from django.contrib.auth import get_user_model

current_actor: ContextVar[Any | None] = ContextVar("current_audit_actor", default=None)


def actor_for_audit() -> Any | None:
    """Return the authenticated request user or None outside a request."""
    actor = current_actor.get()
    if actor is None or not getattr(actor, "is_authenticated", False):
        return None
    if getattr(actor, "is_deleted", False):
        return None
    return actor if isinstance(actor, get_user_model()) else None
