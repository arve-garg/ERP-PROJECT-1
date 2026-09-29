"""Middleware exposing the current user to audit event handlers."""

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from apps.core.audit_context import current_actor


class AuditActorMiddleware:
    """Set and reliably reset the actor for the lifetime of each request."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        token = current_actor.set(getattr(request, "user", None))
        try:
            return self.get_response(request)
        finally:
            current_actor.reset(token)
