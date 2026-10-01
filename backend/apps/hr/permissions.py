"""HR role and employee-scope permissions."""

from django.db.models import QuerySet
from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request

from apps.core.models import User
from apps.hr.models import EmployeeProfile


def has_any_role(user: User, *roles: str) -> bool:
    return bool(
        user.is_authenticated
        and (
            user.is_superuser
            or getattr(user, "approval_status", None) == "approved"
        )
        and (user.is_superuser or user.roles.filter(name__in=roles).exists())
    )


def employee_scope(user: User) -> QuerySet[EmployeeProfile]:
    from django.db.models import Q

    if not user.is_authenticated:
        return EmployeeProfile.objects.none()
    if has_any_role(user, "Admin", "HR"):
        return EmployeeProfile.objects.all()
    profile = EmployeeProfile.objects.filter(user=user).first()
    if profile is None:
        return EmployeeProfile.objects.none()
    if has_any_role(user, "Manager"):
        return EmployeeProfile.objects.filter(Q(pk=profile.pk) | Q(manager=profile))
    return EmployeeProfile.objects.filter(pk=profile.pk)


def private_employee_scope(user: User) -> QuerySet[EmployeeProfile]:
    """Limit sensitive documents and contacts to the employee and HR/Admin."""
    if not user.is_authenticated:
        return EmployeeProfile.objects.none()
    if has_any_role(user, "Admin", "HR"):
        return EmployeeProfile.objects.all()
    return EmployeeProfile.objects.filter(user=user)


class HRReadWritePermission(BasePermission):
    """Allow authenticated reads and HR/Admin changes."""

    def has_permission(self, request: Request, view: object) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        user = request.user
        if request.method in SAFE_METHODS:
            return has_any_role(user, "Admin", "HR", "Manager", "Employee")
        return has_any_role(user, "Admin", "HR")
