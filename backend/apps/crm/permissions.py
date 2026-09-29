"""Permissions for CRM endpoints."""

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


class IsSalesOrAdmin(BasePermission):
    """Allows access to users with Sales or Admin role, or superusers."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.is_superuser:
            return True
        return request.user.roles.filter(name__in=["Sales", "Admin"]).exists()
