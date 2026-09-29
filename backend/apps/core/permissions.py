"""Reusable role and object-scoped API permissions."""

from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


class HasRole(BasePermission):
    """Allow access to users with one of the view's declared roles."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        allowed_roles = getattr(view, "required_roles", ())
        if not allowed_roles:
            return bool(request.user and request.user.is_authenticated)
        return bool(
            request.user
            and request.user.is_authenticated
            and (
                request.user.is_superuser
                or request.user.roles.filter(name__in=allowed_roles).exists()
            )
        )


class AdminOrReadOnly(HasRole):
    """Allow authenticated reads and restrict mutations to administrators."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_superuser or request.user.roles.filter(name="Admin").exists())
        )
