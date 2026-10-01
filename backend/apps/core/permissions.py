"""Reusable role and object-scoped API permissions."""

from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


def is_approved(user) -> bool:
    return bool(
        user
        and user.is_authenticated
        and (user.is_superuser or getattr(user, "approval_status", None) == "approved")
    )


class HasRole(BasePermission):
    """Allow approved users with one of the view's declared roles."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        allowed_roles = getattr(view, "required_roles", ())
        if not allowed_roles:
            return is_approved(request.user)
        return bool(
            is_approved(request.user)
            and (
                request.user.is_superuser
                or request.user.roles.filter(name__in=allowed_roles).exists()
            )
        )


class AdminOrReadOnly(HasRole):
    """Allow approved authenticated reads and restrict mutations to administrators."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        if request.method in SAFE_METHODS:
            return is_approved(request.user)
        return bool(
            is_approved(request.user)
            and (
                request.user.is_superuser
                or request.user.roles.filter(name="Admin").exists()
            )
        )
