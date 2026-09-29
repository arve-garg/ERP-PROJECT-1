"""Role and object-scope helpers for project delivery endpoints."""

from typing import cast

from django.db.models import Q, QuerySet
from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.core.models import User
from apps.hr.models import EmployeeProfile
from apps.projects.models import Client, Project

INTERNAL_ROLES = ("Admin", "HR", "Manager", "Employee")


def has_role(user: User, *roles: str) -> bool:
    return bool(
        user.is_authenticated and (user.is_superuser or user.roles.filter(name__in=roles).exists())
    )


def has_client_role(user: User) -> bool:
    return bool(user.is_authenticated and user.roles.filter(name="Client").exists())


def is_elevated(user: User) -> bool:
    return has_role(user, "Admin", "HR")


def employee_for(user: User) -> EmployeeProfile | None:
    return EmployeeProfile.objects.filter(user=user, is_deleted=False).first()


def team_scope(user: User) -> QuerySet[EmployeeProfile]:
    if is_elevated(user):
        return EmployeeProfile.objects.filter(is_deleted=False)
    profile = employee_for(user)
    if profile is None:
        return EmployeeProfile.objects.none()
    if has_role(user, "Manager"):
        return EmployeeProfile.objects.filter(
            Q(pk=profile.pk) | Q(manager_id=profile.pk), is_deleted=False
        )
    return EmployeeProfile.objects.filter(pk=profile.pk, is_deleted=False)


def client_scope(user: User) -> QuerySet[Client]:
    if not has_client_role(user) or has_role(user, "Admin", "HR", "Manager", "Employee"):
        return Client.objects.none()
    return Client.objects.filter(portal_users=user, is_deleted=False)


def project_scope(user: User, *, include_clients: bool = True) -> QuerySet[Project]:
    projects = Project.objects.filter(is_deleted=False, client__is_deleted=False)
    if is_elevated(user):
        return projects
    if has_role(user, "Manager"):
        profile = employee_for(user)
        if profile is None:
            return Project.objects.none()
        team = team_scope(user)
        return projects.filter(
            Q(manager=profile)
            | Q(allocations__employee__in=team, allocations__is_deleted=False)
            | Q(tasks__assignee__in=team, tasks__is_deleted=False)
        ).distinct()
    if has_role(user, "Employee"):
        profile = employee_for(user)
        if profile is None:
            return Project.objects.none()
        return projects.filter(
            Q(allocations__employee=profile, allocations__is_deleted=False)
            | Q(tasks__assignee=profile, tasks__is_deleted=False)
        ).distinct()
    if include_clients:
        return projects.filter(client__in=client_scope(user))
    return Project.objects.none()


def can_manage_project(user: User, project: Project) -> bool:
    if is_elevated(user):
        return True
    profile = employee_for(user)
    return bool(
        has_role(user, "Manager")
        and profile is not None
        and project_scope(user, include_clients=False).filter(pk=project.pk).exists()
    )


class ProjectRolePermission(BasePermission):
    """Restrict writes to managers/HR/Admin; allow scoped client reads where enabled."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return has_role(user, *INTERNAL_ROLES) or has_client_role(user)
        return has_role(user, "Admin", "HR", "Manager")


class InternalProjectRolePermission(BasePermission):
    """Require an internal employee role, with client users explicitly excluded."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and has_role(user, *INTERNAL_ROLES)
            and not has_client_role(user)
        )


class FinanceProjectPermission(BasePermission):
    """Allow only Finance, HR, and Admin users to access cost-rate records."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(request.user and has_role(cast(User, request.user), "Admin", "HR", "Finance"))
