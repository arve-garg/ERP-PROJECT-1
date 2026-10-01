"""Versioned REST endpoints for core platform resources."""

import csv
from collections.abc import Sequence
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any, cast
from zipfile import BadZipFile

from django.db import transaction
from django.db.models import Q
from django.db.models.query import QuerySet
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from openpyxl import Workbook, load_workbook
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.generics import GenericAPIView, ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from apps.core.models import (
    ActivityFeedItem,
    AuditLog,
    CompanySetting,
    Notification,
    Role,
    SavedFilter,
    User,
)
from apps.core.permissions import AdminOrReadOnly, HasRole
from apps.core.serializers import (
    ActivityFeedSerializer,
    AuditLogSerializer,
    CompanySettingSerializer,
    NotificationSerializer,
    RoleSerializer,
    SavedFilterSerializer,
    UserProfileSerializer,
    UserSearchResultSerializer,
    UserSerializer,
)


class HealthView(GenericAPIView[Any]):
    """Unauthenticated liveness endpoint for runtime orchestration."""

    permission_classes = []
    authentication_classes = []

    def get(self, request: Request) -> Response:
        return Response({"status": "ok", "service": "DevERP API"})


class UserViewSet(viewsets.ModelViewSet[User]):
    """Admin user directory, plus the current user's own profile."""

    serializer_class = UserSerializer
    permission_classes = [HasRole]
    required_roles = ("Admin",)
    filterset_fields = ["is_active", "is_deleted", "roles__name"]
    search_fields = ["email", "first_name", "last_name"]
    ordering_fields = ["email", "date_joined", "first_name", "last_name"]

    def get_serializer_class(self) -> type[UserSerializer] | type[UserProfileSerializer]:
        if self.action == "me":
            return UserProfileSerializer
        return self.serializer_class

    def get_queryset(self) -> QuerySet[User, User]:
        if getattr(self, "action", None) == "me":
            return User.objects.filter(pk=cast(User, self.request.user).pk)
        return User.objects.filter(is_deleted=False).prefetch_related("roles")

    @action(
        detail=False, methods=["get", "patch"], permission_classes=[IsAuthenticated], url_path="me"
    )
    def me(self, request: Request) -> Response:
        serializer = self.get_serializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        if request.method == "PATCH":
            serializer.save()
        return Response(serializer.data)

    def perform_destroy(self, instance: User) -> None:
        instance.soft_delete()

    @action(detail=False, methods=["get"], url_path="export")
    def export_users(self, request: Request) -> HttpResponse:
        file_format = request.query_params.get("file_format", "csv").lower()
        if file_format not in {"csv", "xlsx"}:
            raise ValidationError({"file_format": "Choose csv or xlsx."})
        users = self.filter_queryset(self.get_queryset()).prefetch_related("roles")
        rows: list[list[Any]] = [
            [
                user.email,
                user.first_name,
                user.last_name,
                user.is_active,
                ";".join(user.roles.values_list("name", flat=True)),
                user.date_joined.isoformat(),
            ]
            for user in users
        ]
        headers = ["email", "first_name", "last_name", "is_active", "roles", "date_joined"]
        if file_format == "csv":
            csv_buffer = StringIO()
            writer = csv.writer(csv_buffer)
            writer.writerow(headers)
            writer.writerows(rows)
            response = HttpResponse(csv_buffer.getvalue(), content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = 'attachment; filename="deverp-users.csv"'
            return response
        workbook = Workbook(write_only=True)
        sheet = workbook.create_sheet("Users")
        sheet.append(headers)
        for row in rows:
            sheet.append(row)
        xlsx_buffer = BytesIO()
        workbook.save(xlsx_buffer)
        response = HttpResponse(
            xlsx_buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="deverp-users.xlsx"'
        return response

    @action(detail=False, methods=["post"], url_path="import")
    def import_users(self, request: Request) -> Response:
        uploaded = request.FILES.get("file")
        if uploaded is None:
            raise ValidationError({"file": "Choose a CSV or XLSX file to import."})
        if uploaded.size == 0 or uploaded.size > 5 * 1024 * 1024:
            raise ValidationError({"file": "File must be non-empty and no larger than 5 MiB."})
        extension = Path(uploaded.name).suffix.lower()
        content = uploaded.read()
        table: Sequence[Sequence[Any]]
        try:
            if extension == ".csv":
                table = list(csv.reader(StringIO(content.decode("utf-8-sig"))))
            elif extension == ".xlsx":
                workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
                table = list(workbook.active.iter_rows(values_only=True))
                workbook.close()
            else:
                raise ValidationError({"file": "Only CSV and XLSX files are supported."})
        except (BadZipFile, UnicodeDecodeError, csv.Error, OSError, ValueError) as error:
            raise ValidationError({"file": "The uploaded file could not be parsed."}) from error
        if not table:
            raise ValidationError({"file": "The uploaded file has no header row."})
        headers = [str(value or "").strip().lower() for value in table[0]]
        required = {"email", "first_name", "last_name", "password"}
        if not required.issubset(headers):
            raise ValidationError({"file": f"Required columns: {', '.join(sorted(required))}."})
        validated: list[UserSerializer] = []
        errors: list[dict[str, Any]] = []
        seen_emails: set[str] = set()
        for row_number, row in enumerate(table[1:], start=2):
            values: dict[str, Any] = {
                headers[index]: str(value or "").strip()
                for index, value in enumerate(row)
                if index < len(headers) and headers[index]
            }
            email = values.get("email", "").casefold()
            if not email:
                errors.append({"row": row_number, "errors": {"email": ["Email is required."]}})
                continue
            if email in seen_emails or User.objects.filter(email__iexact=email).exists():
                errors.append({"row": row_number, "errors": {"email": ["Email already exists."]}})
                continue
            seen_emails.add(email)
            values["roles"] = [
                role.strip() for role in values.get("roles", "").split(";") if role.strip()
            ]
            serializer = UserSerializer(data=values, context=self.get_serializer_context())
            if serializer.is_valid():
                validated.append(serializer)
            else:
                errors.append({"row": row_number, "errors": serializer.errors})
        if errors:
            return Response({"detail": "No users were imported.", "rows": errors}, status=400)
        if not validated:
            raise ValidationError({"file": "The file contains no user rows."})
        with transaction.atomic():
            for serializer in validated:
                serializer.save()
        return Response({"created": len(validated)}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["put"], url_path="roles")
    def assign_roles(self, request: Request, pk: str | None = None) -> Response:
        user = self.get_object()
        roles = request.data.get("roles")
        if not isinstance(roles, list) or not all(isinstance(role, str) for role in roles):
            raise ValidationError({"roles": "Provide a list of role names."})
        matching_roles = Role.objects.filter(name__in=roles, is_deleted=False)
        if matching_roles.count() != len(set(roles)):
            raise ValidationError({"roles": "One or more requested roles do not exist."})
        user.roles.set(matching_roles)
        return Response(
            {"user_id": user.pk, "roles": list(user.roles.values_list("name", flat=True))}
        )


class RoleViewSet(viewsets.ModelViewSet[Role]):
    queryset = Role.objects.filter(is_deleted=False)
    serializer_class = RoleSerializer
    permission_classes = [HasRole]
    required_roles = ("Admin",)
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]

    def perform_destroy(self, instance: Role) -> None:
        instance.delete()


class AuditLogViewSet(mixins.ListModelMixin, viewsets.GenericViewSet[AuditLog]):
    queryset = AuditLog.objects.select_related("actor").all()
    serializer_class = AuditLogSerializer
    permission_classes = [HasRole]
    required_roles = ("Admin",)
    filterset_fields = ["action", "model_label", "actor"]
    search_fields = ["model_label", "object_id", "actor__email"]
    ordering_fields = ["occurred_at", "action", "model_label"]


class NotificationViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet[Notification]
):
    queryset = Notification.objects.none()
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["category", "read_at"]
    search_fields = ["title", "body"]
    ordering_fields = ["created_at", "read_at"]

    def get_queryset(self) -> QuerySet[Notification, Notification]:
        return Notification.objects.filter(
            recipient=cast(User, self.request.user), is_deleted=False
        )

    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request: Request) -> Response:
        return Response({"unread_count": self.get_queryset().filter(read_at__isnull=True).count()})

    @action(detail=True, methods=["post"], url_path="read")
    def mark_read(self, request: Request, pk: str | None = None) -> Response:
        notification = self.get_object()
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.updated_by = cast(User, request.user)
            notification.save(update_fields=["read_at", "updated_by", "updated_at"])
        return Response(self.get_serializer(notification).data)

    @action(detail=False, methods=["post"], url_path="read-all")
    def mark_all_read(self, request: Request) -> Response:
        for notification in self.get_queryset().filter(read_at__isnull=True).iterator():
            notification.read_at = timezone.now()
            notification.updated_by = cast(User, request.user)
            notification.save(update_fields=["read_at", "updated_by", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class CompanySettingViewSet(viewsets.ModelViewSet[CompanySetting]):
    queryset = CompanySetting.objects.filter(is_deleted=False)
    serializer_class = CompanySettingSerializer
    permission_classes = [AdminOrReadOnly]
    lookup_field = "key"
    filterset_fields = ["key"]
    search_fields = ["key", "description"]
    ordering_fields = ["key", "updated_at"]

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by=request.user, updated_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=kwargs.pop("partial", False)
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data)

    def perform_destroy(self, instance: CompanySetting) -> None:
        instance.delete()


class SavedFilterViewSet(viewsets.ModelViewSet[SavedFilter]):
    queryset = SavedFilter.objects.none()
    serializer_class = SavedFilterSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["module", "is_shared"]
    search_fields = ["name", "module"]
    ordering_fields = ["module", "name", "created_at"]

    def get_queryset(self) -> QuerySet[SavedFilter, SavedFilter]:
        return (
            SavedFilter.objects.filter(is_deleted=False)
            .filter(Q(owner=cast(User, self.request.user)) | Q(is_shared=True))
            .select_related("owner")
        )

    def perform_create(self, serializer: BaseSerializer[SavedFilter]) -> None:
        serializer.save(
            owner=cast(User, self.request.user),
            created_by=cast(User, self.request.user),
            updated_by=cast(User, self.request.user),
        )

    def perform_update(self, serializer: BaseSerializer[SavedFilter]) -> None:
        if serializer.instance is None:
            raise ValidationError("A saved filter record is required for this update.")
        if serializer.instance.owner_id != self.request.user.pk:
            raise PermissionDenied("Only the saved filter owner may edit it.")
        serializer.save(updated_by=self.request.user)

    def perform_destroy(self, instance: SavedFilter) -> None:
        if instance.owner_id != self.request.user.pk:
            raise PermissionDenied("Only the saved filter owner may delete it.")
        instance.delete()


class ActivityFeedView(ListAPIView[ActivityFeedItem]):
    serializer_class = ActivityFeedSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["actor", "target_type"]
    search_fields = ["verb", "target_type", "target_id"]
    ordering_fields = ["created_at", "verb"]
    queryset = ActivityFeedItem.objects.filter(is_deleted=False).select_related("actor")


class SearchView(GenericAPIView[Any]):
    """Search authorized user directory records."""

    permission_classes = [IsAuthenticated]
    serializer_class = UserSearchResultSerializer
    pagination_class = PageNumberPagination
    queryset = User.objects.none()

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="q",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Search at least two characters across user names and email addresses.",
            )
        ],
        responses={200: UserSearchResultSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        query = request.query_params.get("q", "").strip()
        if len(query) < 2:
            return Response(
                {"detail": "Search query must contain at least 2 characters."}, status=400
            )
        users = (
            User.objects.filter(is_active=True, is_deleted=False)
            .filter(
                Q(email__icontains=query)
                | Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
            )
            .only("id", "email", "first_name", "last_name")
        )
        results: list[dict[str, Any]] = [
            {
                "entity": "user",
                "id": user.pk,
                "display_name": user.get_full_name() or user.email,
            }
            for user in users
        ]
        paginator = self.pagination_class()
        paginator.page_size = 25
        paginator.page_size_query_param = "page_size"
        paginator.max_page_size = 100
        page = paginator.paginate_queryset(cast(Any, results), request, view=self)
        return paginator.get_paginated_response(page)
