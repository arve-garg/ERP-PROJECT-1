"""Role-scoped API endpoints for client projects and delivery workflows."""

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, ClassVar, cast

from django.db.models import F, Model, Q, QuerySet, Sum
from django.http import FileResponse
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from apps.core.models import User
from apps.projects.models import (
    Bug,
    Client,
    EmployeeHourlyCost,
    Milestone,
    Project,
    ProjectDocument,
    ProjectWikiPage,
    ReleaseNote,
    ResourceAllocation,
    Sprint,
    Task,
    TaskAttachment,
    TaskComment,
    TaskLabel,
    TimeEntry,
    TimeSubmission,
)
from apps.projects.permissions import (
    FinanceProjectPermission,
    InternalProjectRolePermission,
    ProjectRolePermission,
    can_manage_project,
    client_scope,
    employee_for,
    has_client_role,
    has_role,
    is_elevated,
    project_scope,
    team_scope,
)
from apps.projects.serializers import (
    BugSerializer,
    ClientPortalSerializer,
    ClientSerializer,
    EmployeeHourlyCostSerializer,
    MilestoneSerializer,
    ProjectBudgetSummarySerializer,
    ProjectDocumentSerializer,
    ProjectPortalSerializer,
    ProjectSerializer,
    ProjectWikiPageSerializer,
    ReleaseNoteSerializer,
    ResourceAllocationSerializer,
    ResourceCapacityRowSerializer,
    SprintBurndownPointSerializer,
    SprintSerializer,
    StatusTransitionSerializer,
    TaskAttachmentSerializer,
    TaskCommentSerializer,
    TaskLabelSerializer,
    TaskSerializer,
    TimeDecisionSerializer,
    TimeEntrySerializer,
    TimeSubmissionSerializer,
)
from apps.projects.services import (
    build_record,
    create_time_submission,
    decide_time_entry,
    decide_time_submission,
    employee_rate_at,
    save_record,
    save_serialized_record,
    submit_time_entry,
    transition_status,
)


def request_user(request: Request) -> User:
    return cast(User, request.user)


def is_client_portal_user(user: User) -> bool:
    return has_client_role(user) and not has_role(user, "Admin", "HR", "Manager", "Employee")


def task_scope_for(user: User) -> QuerySet[Task]:
    if is_client_portal_user(user):
        return Task.objects.none()
    tasks = Task.objects.filter(
        is_deleted=False, project__in=project_scope(user, include_clients=False)
    )
    if not is_elevated(user) and not has_role(user, "Manager"):
        profile = employee_for(user)
        if profile is None:
            return Task.objects.none()
        tasks = tasks.filter(assignee=profile)
    return tasks.select_related(
        "project", "project__client", "assignee", "assignee__user", "milestone", "sprint"
    )


class ClientViewSet(viewsets.ModelViewSet[Client]):
    permission_classes = [ProjectRolePermission]
    search_fields = ["name", "email", "phone"]
    ordering_fields = ["name", "status", "created_at"]
    filterset_fields = ["status"]

    def get_serializer_class(self) -> type[BaseSerializer[Any]]:
        if is_client_portal_user(request_user(self.request)):
            return ClientPortalSerializer
        return ClientSerializer

    def get_queryset(self) -> QuerySet[Client]:
        user = request_user(self.request)
        if is_elevated(user):
            return Client.objects.filter(is_deleted=False).prefetch_related("portal_users")
        if has_role(user, "Manager"):
            return Client.objects.filter(
                is_deleted=False,
                projects__in=project_scope(user, include_clients=False),
            ).distinct()
        if has_role(user, "Employee"):
            return Client.objects.filter(
                is_deleted=False,
                projects__in=project_scope(user, include_clients=False),
            ).distinct()
        return client_scope(user).prefetch_related("portal_users")

    def perform_create(self, serializer: BaseSerializer[Client]) -> None:
        save_serialized_record(serializer, request_user(self.request), create=True)

    def perform_update(self, serializer: BaseSerializer[Client]) -> None:
        save_serialized_record(serializer, request_user(self.request))

    def perform_destroy(self, instance: Client) -> None:
        if instance.projects.filter(is_deleted=False).exists():
            raise ValidationError(
                {"detail": "Archive or move active projects before archiving a client."}
            )
        instance.is_deleted = True
        instance.updated_by = request_user(self.request)
        instance.save(update_fields=["is_deleted", "updated_by", "updated_at"])


class ProjectViewSet(viewsets.ModelViewSet[Project]):
    permission_classes = [ProjectRolePermission]
    filterset_fields = ["client", "manager", "status"]
    search_fields = ["name", "code", "description", "client__name", "manager__employee_number"]
    ordering_fields = ["name", "code", "start_date", "end_date", "budget", "created_at"]

    def get_queryset(self) -> QuerySet[Project]:
        return project_scope(request_user(self.request)).select_related(
            "client", "manager", "manager__user"
        )

    def get_serializer_class(self) -> type[BaseSerializer[Any]]:
        if is_client_portal_user(request_user(self.request)):
            return ProjectPortalSerializer
        return ProjectSerializer

    def perform_create(self, serializer: BaseSerializer[Project]) -> None:
        user = request_user(self.request)
        project, many_to_many = build_record(serializer)
        project = cast(Project, project)
        if not is_elevated(user):
            profile = employee_for(user)
            if profile is None or project.manager_id != profile.pk:
                raise PermissionDenied("Managers can create projects only for themselves.")
        save_record(project, user, create=True)
        for field, values in many_to_many.items():
            getattr(project, field).set(values)
        serializer.instance = project

    def perform_update(self, serializer: BaseSerializer[Project]) -> None:
        user = request_user(self.request)
        project, many_to_many = build_record(serializer)
        project = cast(Project, project)
        if not can_manage_project(user, self.get_object()):
            raise PermissionDenied("You cannot manage this project.")
        if not is_elevated(user):
            profile = employee_for(user)
            if profile is None or project.manager_id != profile.pk:
                raise PermissionDenied("Managers cannot transfer project ownership.")
        save_record(project, user)
        for field, values in many_to_many.items():
            getattr(project, field).set(values)
        serializer.instance = project

    def perform_destroy(self, instance: Project) -> None:
        if instance.tasks.filter(is_deleted=False).exists():
            raise ValidationError({"detail": "A project with tasks cannot be archived."})
        instance.is_deleted = True
        instance.updated_by = request_user(self.request)
        instance.save(update_fields=["is_deleted", "updated_by", "updated_at"])

    @extend_schema(request=StatusTransitionSerializer, responses=ProjectSerializer)
    @action(detail=True, methods=["post"], url_path="transition")
    def transition(self, request: Request, pk: str | None = None) -> Response:
        project = self.get_object()
        if not can_manage_project(request_user(request), project):
            raise PermissionDenied("You cannot manage this project.")
        serializer = StatusTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = transition_status(
            Project, int(project.pk), serializer.validated_data["status"], request_user(request)
        )
        return Response(self.get_serializer(updated).data)

    @action(detail=True, methods=["get"], url_path="budget-summary")
    def budget_summary(self, request: Request, pk: str | None = None) -> Response:
        project = self.get_object()
        if is_client_portal_user(request_user(request)):
            raise PermissionDenied("Project financial information is not available to clients.")
        entries = TimeEntry.objects.filter(
            task__project=project,
            status=TimeEntry.Status.APPROVED,
            is_deleted=False,
            hourly_cost_currency_snapshot=project.budget_currency,
        )
        aggregates = entries.aggregate(
            total_hours=Sum("hours"),
            billable_hours=Sum("hours", filter=Q(is_billable=True)),
            unpriced_hours=Sum("hours", filter=Q(hourly_cost_snapshot=Decimal("0.00"))),
        )
        cost = entries.aggregate(total_cost=Sum(F("hours") * F("hourly_cost_snapshot")))[
            "total_cost"
        ] or Decimal("0.00")
        payload = {
            "project_id": project.pk,
            "budget": project.budget,
            "currency": project.budget_currency,
            "actual_cost": cost,
            "remaining_budget": project.budget - cost,
            "approved_hours": aggregates["total_hours"] or Decimal("0.00"),
            "billable_hours": aggregates["billable_hours"] or Decimal("0.00"),
            "unpriced_approved_hours": aggregates["unpriced_hours"] or Decimal("0.00"),
        }
        return Response(ProjectBudgetSummarySerializer(payload).data)


class ScopedProjectRecordViewSet(viewsets.ModelViewSet[Any]):
    """Shared scope and audited persistence for project-owned child records."""

    queryset_model: ClassVar[type[Model]]
    parent_field = "project"

    def get_queryset(self) -> QuerySet[Any]:
        if getattr(self, "swagger_fake_view", False):
            return self.queryset_model._default_manager.none()
        return cast(
            QuerySet[Any],
            self.queryset_model._default_manager.filter(
                is_deleted=False,
                project__in=project_scope(request_user(self.request)),
            ).select_related("project", "project__client"),
        )

    def _check_project_write(self, project: Project) -> None:
        if not can_manage_project(request_user(self.request), project):
            raise PermissionDenied("You cannot manage this project.")

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        record, many_to_many = build_record(serializer)
        record = cast(Any, record)
        self._check_project_write(record.project)
        save_record(record, request_user(self.request), create=True)
        for field, values in many_to_many.items():
            getattr(record, field).set(values)
        serializer.instance = record

    def perform_update(self, serializer: BaseSerializer[Any]) -> None:
        record, many_to_many = build_record(serializer)
        record = cast(Any, record)
        self._check_project_write(record.project)
        save_record(record, request_user(self.request))
        for field, values in many_to_many.items():
            getattr(record, field).set(values)
        serializer.instance = record

    def perform_destroy(self, instance: Any) -> None:
        self._check_project_write(instance.project)
        instance.is_deleted = True
        instance.updated_by = request_user(self.request)
        instance.save(update_fields=["is_deleted", "updated_by", "updated_at"])


class MilestoneViewSet(ScopedProjectRecordViewSet):
    queryset_model = Milestone
    serializer_class = MilestoneSerializer
    permission_classes = [ProjectRolePermission]
    filterset_fields = ["project", "status", "due_date"]
    search_fields = ["name", "description", "project__name", "project__code"]
    ordering_fields = ["name", "due_date", "status", "created_at"]

    @extend_schema(request=StatusTransitionSerializer, responses=MilestoneSerializer)
    @action(detail=True, methods=["post"], url_path="transition")
    def transition(self, request: Request, pk: str | None = None) -> Response:
        milestone = self.get_object()
        self._check_project_write(milestone.project)
        serializer = StatusTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = transition_status(
            Milestone, int(milestone.pk), serializer.validated_data["status"], request_user(request)
        )
        return Response(self.get_serializer(updated).data)


class SprintViewSet(ScopedProjectRecordViewSet):
    queryset_model = Sprint
    serializer_class = SprintSerializer
    permission_classes = [InternalProjectRolePermission]
    filterset_fields = ["project", "status", "start_date", "end_date"]
    search_fields = ["name", "goal", "project__name", "project__code"]
    ordering_fields = ["name", "start_date", "end_date", "status"]

    @action(detail=True, methods=["get"], url_path="backlog")
    def backlog(self, request: Request, pk: str | None = None) -> Response:
        sprint = self.get_object()
        tasks = Task.objects.filter(sprint=sprint, is_deleted=False).select_related(
            "assignee", "assignee__user"
        )
        page = self.paginate_queryset(tasks)
        serializer = TaskSerializer(
            page if page is not None else tasks,
            many=True,
            context=self.get_serializer_context(),
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="burndown")
    def burndown(self, request: Request, pk: str | None = None) -> Response:
        sprint = self.get_object()
        total = sprint.tasks.filter(is_deleted=False).aggregate(value=Sum("estimate_hours"))[
            "value"
        ] or Decimal("0.00")
        points: list[dict[str, Any]] = []
        day = sprint.start_date
        while day <= min(sprint.end_date, timezone.localdate()):
            completed = sprint.tasks.filter(
                is_deleted=False,
                status=Task.Status.DONE,
                completed_at__date__lte=day,
            ).aggregate(value=Sum("estimate_hours"))["value"] or Decimal("0.00")
            points.append(
                {
                    "date": day,
                    "remaining_estimate_hours": max(total - completed, 0),
                    "completed_estimate_hours": completed,
                }
            )
            day += timedelta(days=1)
        return Response(SprintBurndownPointSerializer(points, many=True).data)

    @extend_schema(request=StatusTransitionSerializer, responses=SprintSerializer)
    @action(detail=True, methods=["post"], url_path="transition")
    def transition(self, request: Request, pk: str | None = None) -> Response:
        sprint = self.get_object()
        self._check_project_write(sprint.project)
        serializer = StatusTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = transition_status(
            Sprint, int(sprint.pk), serializer.validated_data["status"], request_user(request)
        )
        return Response(self.get_serializer(updated).data)


class TaskViewSet(viewsets.ModelViewSet[Task]):
    serializer_class = TaskSerializer
    permission_classes = [InternalProjectRolePermission]
    filterset_fields = ["project", "milestone", "sprint", "assignee", "priority", "status"]
    search_fields = ["title", "description", "project__name", "project__code"]
    ordering_fields = ["title", "priority", "status", "due_date", "estimate_hours", "created_at"]

    def get_queryset(self) -> QuerySet[Task]:
        if getattr(self, "swagger_fake_view", False):
            return Task.objects.none()
        return task_scope_for(request_user(self.request))

    def perform_create(self, serializer: BaseSerializer[Task]) -> None:
        task, many_to_many = build_record(serializer)
        task = cast(Task, task)
        self._check_task_write(task)
        save_record(task, request_user(self.request), create=True)
        for field, values in many_to_many.items():
            getattr(task, field).set(values)
        serializer.instance = task

    def perform_update(self, serializer: BaseSerializer[Task]) -> None:
        task, many_to_many = build_record(serializer)
        task = cast(Task, task)
        self._check_task_write(self.get_object())
        self._check_assignment(task)
        save_record(task, request_user(self.request))
        for field, values in many_to_many.items():
            getattr(task, field).set(values)
        serializer.instance = task

    def _check_task_write(self, task: Task) -> None:
        self._check_assignment(task)
        if not can_manage_project(request_user(self.request), task.project):
            raise PermissionDenied("You cannot manage tasks in this project.")

    def _check_assignment(self, task: Task) -> None:
        user = request_user(self.request)
        if task.assignee_id and not is_elevated(user):
            if not team_scope(user).filter(pk=task.assignee_id).exists():
                raise PermissionDenied("You can assign tasks only to your team.")

    def perform_destroy(self, instance: Task) -> None:
        if not can_manage_project(request_user(self.request), instance.project):
            raise PermissionDenied("You cannot manage tasks in this project.")
        if instance.time_entries.filter(is_deleted=False).exists():
            raise ValidationError({"detail": "Tasks with time entries cannot be archived."})
        instance.is_deleted = True
        instance.updated_by = request_user(self.request)
        instance.save(update_fields=["is_deleted", "updated_by", "updated_at"])

    @extend_schema(request=StatusTransitionSerializer, responses=TaskSerializer)
    @action(detail=True, methods=["post"], url_path="status")
    def update_status(self, request: Request, pk: str | None = None) -> Response:
        task = self.get_object()
        user = request_user(request)
        if task.assignee is not None and task.assignee.user_id == user.pk:
            if not (is_elevated(user) or has_role(user, "Employee", "Manager")):
                raise PermissionDenied(
                    "Only assigned employees or project managers can update task status."
                )
        elif not can_manage_project(user, task.project):
            raise PermissionDenied("You cannot manage this task.")
        serializer = StatusTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = transition_status(Task, int(task.pk), serializer.validated_data["status"], user)
        return Response(self.get_serializer(updated).data)


class TaskLabelViewSet(viewsets.ModelViewSet[TaskLabel]):
    serializer_class = TaskLabelSerializer
    permission_classes = [InternalProjectRolePermission]
    filterset_fields = ["name"]
    search_fields = ["name"]
    ordering_fields = ["name", "created_at"]

    def get_queryset(self) -> QuerySet[TaskLabel]:
        return TaskLabel.objects.filter(is_deleted=False)

    def perform_create(self, serializer: BaseSerializer[TaskLabel]) -> None:
        self._require_label_manager()
        save_serialized_record(serializer, request_user(self.request), create=True)

    def perform_update(self, serializer: BaseSerializer[TaskLabel]) -> None:
        self._require_label_manager()
        save_serialized_record(serializer, request_user(self.request))

    def perform_destroy(self, instance: TaskLabel) -> None:
        self._require_label_manager()
        instance.is_deleted = True
        instance.updated_by = request_user(self.request)
        instance.save(update_fields=["is_deleted", "updated_by", "updated_at"])

    def _require_label_manager(self) -> None:
        user = request_user(self.request)
        if not (is_elevated(user) or has_role(user, "Manager")):
            raise PermissionDenied("Only a manager, HR, or Admin can manage task labels.")


class TaskAttachmentViewSet(viewsets.ModelViewSet[TaskAttachment]):
    serializer_class = TaskAttachmentSerializer
    permission_classes = [InternalProjectRolePermission]
    http_method_names = ["get", "post", "delete", "head", "options"]
    filterset_fields = ["task"]
    search_fields = ["file_name", "task__title"]
    ordering_fields = ["created_at", "file_name"]

    def get_queryset(self) -> QuerySet[TaskAttachment]:
        if getattr(self, "swagger_fake_view", False):
            return TaskAttachment.objects.none()
        return TaskAttachment.objects.filter(
            is_deleted=False, task__in=task_scope_for(request_user(self.request))
        ).select_related("task", "uploaded_by")

    def perform_create(self, serializer: BaseSerializer[TaskAttachment]) -> None:
        attachment, _ = build_record(serializer)
        attachment = cast(TaskAttachment, attachment)
        user = request_user(self.request)
        if not task_scope_for(user).filter(pk=attachment.task_id).exists():
            raise PermissionDenied("You cannot upload attachments to this task.")
        if not (
            is_elevated(user)
            or can_manage_project(user, attachment.task.project)
            or (
                attachment.task.assignee is not None and attachment.task.assignee.user_id == user.pk
            )
        ):
            raise PermissionDenied("Only a project manager or task assignee can attach files.")
        attachment.uploaded_by = user
        attachment.file_name = attachment.file.name
        save_record(attachment, user, create=True)
        serializer.instance = attachment

    def perform_destroy(self, instance: TaskAttachment) -> None:
        user = request_user(self.request)
        if (
            instance.uploaded_by_id != user.pk
            and not is_elevated(user)
            and not can_manage_project(user, instance.task.project)
        ):
            raise PermissionDenied("You cannot delete this attachment.")
        instance.is_deleted = True
        instance.updated_by = user
        instance.save(update_fields=["is_deleted", "updated_by", "updated_at"])

    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request: Request, pk: str | None = None) -> FileResponse:
        attachment = self.get_object()
        return FileResponse(
            attachment.file.open("rb"),
            as_attachment=True,
            filename=Path(attachment.file_name).name,
        )


class ProjectWikiPageViewSet(ScopedProjectRecordViewSet):
    queryset_model = ProjectWikiPage
    serializer_class = ProjectWikiPageSerializer
    permission_classes = [InternalProjectRolePermission]
    filterset_fields = ["project"]
    search_fields = ["title", "content", "project__name"]
    ordering_fields = ["title", "created_at", "updated_at"]


class ProjectDocumentViewSet(viewsets.ModelViewSet[ProjectDocument]):
    serializer_class = ProjectDocumentSerializer
    permission_classes = [ProjectRolePermission]
    http_method_names = ["get", "post", "delete", "head", "options"]
    filterset_fields = ["project", "client_visible"]
    search_fields = ["title", "description", "file_name", "project__name"]
    ordering_fields = ["title", "created_at"]

    def get_queryset(self) -> QuerySet[ProjectDocument]:
        user = request_user(self.request)
        documents = ProjectDocument.objects.filter(is_deleted=False)
        if is_client_portal_user(user):
            return documents.filter(
                client_visible=True,
                project__in=project_scope(user),
            ).select_related("project", "project__client")
        if not has_role(user, "Admin", "HR", "Manager", "Employee"):
            return ProjectDocument.objects.none()
        return documents.filter(project__in=project_scope(user)).select_related(
            "project", "project__client", "uploaded_by"
        )

    def perform_create(self, serializer: BaseSerializer[ProjectDocument]) -> None:
        document, _ = build_record(serializer)
        document = cast(ProjectDocument, document)
        if not can_manage_project(request_user(self.request), document.project):
            raise PermissionDenied("You cannot manage documents for this project.")
        document.uploaded_by = request_user(self.request)
        document.file_name = document.file.name
        save_record(document, request_user(self.request), create=True)
        serializer.instance = document

    def perform_destroy(self, instance: ProjectDocument) -> None:
        if not can_manage_project(request_user(self.request), instance.project):
            raise PermissionDenied("You cannot manage documents for this project.")
        instance.is_deleted = True
        instance.updated_by = request_user(self.request)
        instance.save(update_fields=["is_deleted", "updated_by", "updated_at"])

    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request: Request, pk: str | None = None) -> FileResponse:
        document = self.get_object()
        return FileResponse(
            document.file.open("rb"),
            as_attachment=True,
            filename=Path(document.file_name).name,
        )


class ReleaseNoteViewSet(viewsets.ModelViewSet[ReleaseNote]):
    serializer_class = ReleaseNoteSerializer
    permission_classes = [ProjectRolePermission]
    filterset_fields = ["project", "release_date", "is_published"]
    search_fields = ["version", "title", "content", "project__name"]
    ordering_fields = ["release_date", "version", "created_at"]

    def get_queryset(self) -> QuerySet[ReleaseNote]:
        user = request_user(self.request)
        queryset = ReleaseNote.objects.filter(is_deleted=False)
        if is_client_portal_user(user):
            return queryset.filter(
                is_published=True,
                project__in=project_scope(user),
            ).select_related("project")
        if not has_role(user, "Admin", "HR", "Manager", "Employee"):
            return ReleaseNote.objects.none()
        return queryset.filter(project__in=project_scope(user)).select_related(
            "project", "project__client"
        )

    def perform_create(self, serializer: BaseSerializer[ReleaseNote]) -> None:
        note, many_to_many = build_record(serializer)
        note = cast(ReleaseNote, note)
        if not can_manage_project(request_user(self.request), note.project):
            raise PermissionDenied("You cannot manage release notes for this project.")
        save_record(note, request_user(self.request), create=True)
        serializer.instance = note

    def perform_update(self, serializer: BaseSerializer[ReleaseNote]) -> None:
        note, _ = build_record(serializer)
        note = cast(ReleaseNote, note)
        if not can_manage_project(request_user(self.request), self.get_object().project):
            raise PermissionDenied("You cannot manage release notes for this project.")
        save_record(note, request_user(self.request))
        serializer.instance = note

    def perform_destroy(self, instance: ReleaseNote) -> None:
        if not can_manage_project(request_user(self.request), instance.project):
            raise PermissionDenied("You cannot manage release notes for this project.")
        instance.is_deleted = True
        instance.updated_by = request_user(self.request)
        instance.save(update_fields=["is_deleted", "updated_by", "updated_at"])


class BugViewSet(viewsets.ModelViewSet[Bug]):
    serializer_class = BugSerializer
    permission_classes = [InternalProjectRolePermission]
    filterset_fields = ["project", "task", "severity", "status", "assignee"]
    search_fields = ["title", "description", "project__name", "task__title"]
    ordering_fields = ["created_at", "severity", "status", "updated_at"]

    def get_queryset(self) -> QuerySet[Bug]:
        if getattr(self, "swagger_fake_view", False):
            return Bug.objects.none()
        return Bug.objects.filter(
            is_deleted=False,
            project__in=project_scope(request_user(self.request), include_clients=False),
        ).select_related("project", "task", "reporter", "assignee", "assignee__user")

    def perform_create(self, serializer: BaseSerializer[Bug]) -> None:
        bug, _ = build_record(serializer)
        bug = cast(Bug, bug)
        user = request_user(self.request)
        if not project_scope(user, include_clients=False).filter(pk=bug.project_id).exists():
            raise PermissionDenied("You cannot report bugs for this project.")
        if bug.assignee_id and not is_elevated(user):
            if not team_scope(user).filter(pk=bug.assignee_id).exists():
                raise PermissionDenied("You can assign bugs only to your team.")
        bug.reporter = user
        save_record(bug, user, create=True)
        serializer.instance = bug

    def perform_update(self, serializer: BaseSerializer[Bug]) -> None:
        bug, _ = build_record(serializer)
        bug = cast(Bug, bug)
        if not can_manage_project(request_user(self.request), self.get_object().project):
            raise PermissionDenied("Only a project manager, HR, or Admin can edit bugs.")
        if bug.assignee_id and not is_elevated(request_user(self.request)):
            if not team_scope(request_user(self.request)).filter(pk=bug.assignee_id).exists():
                raise PermissionDenied("You can assign bugs only to your team.")
        save_record(bug, request_user(self.request))
        serializer.instance = bug

    @extend_schema(request=StatusTransitionSerializer, responses=BugSerializer)
    @action(detail=True, methods=["post"], url_path="status")
    def update_status(self, request: Request, pk: str | None = None) -> Response:
        bug = self.get_object()
        user = request_user(request)
        assigned_to_actor = bug.assignee is not None and bug.assignee.user_id == user.pk
        if not assigned_to_actor and not can_manage_project(user, bug.project):
            raise PermissionDenied("You cannot update this bug.")
        serializer = StatusTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = transition_status(Bug, int(bug.pk), serializer.validated_data["status"], user)
        return Response(self.get_serializer(updated).data)

    def perform_destroy(self, instance: Bug) -> None:
        if not can_manage_project(request_user(self.request), instance.project):
            raise PermissionDenied("Only a project manager, HR, or Admin can archive bugs.")
        instance.is_deleted = True
        instance.updated_by = request_user(self.request)
        instance.save(update_fields=["is_deleted", "updated_by", "updated_at"])


class EmployeeHourlyCostViewSet(viewsets.ModelViewSet[EmployeeHourlyCost]):
    serializer_class = EmployeeHourlyCostSerializer
    permission_classes = [FinanceProjectPermission]
    filterset_fields = ["employee", "currency", "effective_from", "effective_to"]
    search_fields = ["employee__employee_number", "employee__user__email"]
    ordering_fields = ["effective_from", "hourly_cost"]

    def get_queryset(self) -> QuerySet[EmployeeHourlyCost]:
        if getattr(self, "swagger_fake_view", False):
            return EmployeeHourlyCost.objects.none()
        user = request_user(self.request)
        if not has_role(user, "Admin", "HR", "Finance"):
            raise PermissionDenied("Only Finance, HR, or Admin can access employee hourly costs.")
        return EmployeeHourlyCost.objects.filter(is_deleted=False).select_related(
            "employee", "employee__user"
        )

    def perform_create(self, serializer: BaseSerializer[EmployeeHourlyCost]) -> None:
        self._require_finance_role()
        save_serialized_record(serializer, request_user(self.request), create=True)

    def perform_update(self, serializer: BaseSerializer[EmployeeHourlyCost]) -> None:
        self._require_finance_role()
        save_serialized_record(serializer, request_user(self.request))

    def perform_destroy(self, instance: EmployeeHourlyCost) -> None:
        self._require_finance_role()
        instance.is_deleted = True
        instance.updated_by = request_user(self.request)
        instance.save(update_fields=["is_deleted", "updated_by", "updated_at"])

    def _require_finance_role(self) -> None:
        if not has_role(request_user(self.request), "Admin", "HR", "Finance"):
            raise PermissionDenied("Only Finance, HR, or Admin can manage hourly costs.")


class TaskCommentViewSet(viewsets.ModelViewSet[TaskComment]):
    serializer_class = TaskCommentSerializer
    permission_classes = [InternalProjectRolePermission]
    http_method_names = ["get", "post", "delete", "head", "options"]
    filterset_fields = ["task", "author"]
    search_fields = ["body", "author__first_name", "author__last_name", "task__title"]
    ordering_fields = ["created_at", "updated_at"]

    def get_queryset(self) -> QuerySet[TaskComment]:
        if getattr(self, "swagger_fake_view", False):
            return TaskComment.objects.none()
        user = request_user(self.request)
        if is_client_portal_user(user):
            return TaskComment.objects.none()
        tasks = task_scope_for(user)
        return TaskComment.objects.filter(is_deleted=False, task__in=tasks).select_related(
            "task", "author"
        )

    def perform_create(self, serializer: BaseSerializer[TaskComment]) -> None:
        comment, many_to_many = build_record(serializer)
        comment = cast(TaskComment, comment)
        task = comment.task
        user = request_user(self.request)
        if not task_scope_for(user).filter(pk=task.pk).exists():
            raise PermissionDenied("You cannot comment on this task.")
        if not (
            is_elevated(user)
            or has_role(user, "Manager")
            or (task.assignee is not None and task.assignee.user_id == user.pk)
        ):
            raise PermissionDenied("Only an assigned employee or project manager can comment.")
        comment.author = user
        save_record(comment, user, create=True)
        for field, values in many_to_many.items():
            getattr(comment, field).set(values)
        serializer.instance = comment

    def perform_destroy(self, instance: TaskComment) -> None:
        user = request_user(self.request)
        if instance.author_id != user.pk and not is_elevated(user):
            raise PermissionDenied("You can delete only your own comment.")
        instance.is_deleted = True
        instance.updated_by = user
        instance.save(update_fields=["is_deleted", "updated_by", "updated_at"])


class TimeEntryViewSet(viewsets.ModelViewSet[TimeEntry]):
    serializer_class = TimeEntrySerializer
    permission_classes = [InternalProjectRolePermission]
    filterset_fields = ["task", "employee", "work_date", "status"]
    search_fields = ["task__title", "task__project__name", "employee__employee_number"]
    ordering_fields = ["work_date", "hours", "status", "created_at"]

    def get_queryset(self) -> QuerySet[TimeEntry]:
        user = request_user(self.request)
        if is_client_portal_user(user) or not has_role(user, "Admin", "HR", "Manager", "Employee"):
            return TimeEntry.objects.none()
        entries = TimeEntry.objects.filter(is_deleted=False)
        if is_elevated(user):
            pass
        elif has_role(user, "Manager"):
            entries = entries.filter(
                Q(employee__in=team_scope(user))
                | Q(task__project__in=project_scope(user, include_clients=False))
            )
        else:
            profile = employee_for(user)
            if profile is None:
                return TimeEntry.objects.none()
            entries = entries.filter(employee=profile)
        return entries.select_related(
            "task", "task__project", "employee", "employee__user", "approver"
        )

    def perform_create(self, serializer: BaseSerializer[TimeEntry]) -> None:
        user = request_user(self.request)
        employee = employee_for(user)
        if employee is None or not has_role(user, "Employee", "Manager", "HR", "Admin"):
            raise PermissionDenied("An internal employee profile is required to record time.")
        entry, many_to_many = build_record(serializer)
        entry = cast(TimeEntry, entry)
        entry.employee = employee
        entry.status = TimeEntry.Status.DRAFT
        entry.hourly_cost_currency_snapshot = entry.task.project.budget_currency
        entry.hourly_cost_snapshot = employee_rate_at(
            employee, entry.work_date, entry.hourly_cost_currency_snapshot
        )
        save_record(entry, user, create=True)
        for field, values in many_to_many.items():
            getattr(entry, field).set(values)
        serializer.instance = entry

    def perform_update(self, serializer: BaseSerializer[TimeEntry]) -> None:
        user = request_user(self.request)
        entry = self.get_object()
        if entry.employee.user_id != user.pk or entry.status not in {
            TimeEntry.Status.DRAFT,
            TimeEntry.Status.REJECTED,
        }:
            raise PermissionDenied("You can edit only your own draft or rejected time entries.")
        updated = cast(TimeEntry, serializer.instance)
        work_date = serializer.validated_data.get("work_date", updated.work_date)
        updated.hourly_cost_currency_snapshot = updated.task.project.budget_currency
        updated.hourly_cost_snapshot = employee_rate_at(
            updated.employee, work_date, updated.hourly_cost_currency_snapshot
        )
        save_serialized_record(serializer, user)

    def perform_destroy(self, instance: TimeEntry) -> None:
        if instance.employee.user_id != request_user(self.request).pk or instance.status not in {
            TimeEntry.Status.DRAFT,
            TimeEntry.Status.REJECTED,
        }:
            raise PermissionDenied("Only your own draft or rejected time can be deleted.")
        instance.is_deleted = True
        instance.updated_by = request_user(self.request)
        instance.save(update_fields=["is_deleted", "updated_by", "updated_at"])

    @extend_schema(request=None, responses=TimeEntrySerializer)
    @action(detail=True, methods=["post"], url_path="submit")
    def submit(self, request: Request, pk: str | None = None) -> Response:
        entry = self.get_object()
        submitted = submit_time_entry(int(entry.pk), request_user(request))
        return Response(self.get_serializer(submitted).data)

    @extend_schema(request=TimeDecisionSerializer, responses=TimeEntrySerializer)
    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request: Request, pk: str | None = None) -> Response:
        entry = self.get_object()
        self._require_manage_scope(request_user(request), entry)
        serializer = TimeDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        decided = decide_time_entry(
            int(entry.pk),
            request_user(request),
            approve=True,
            decision_note=serializer.validated_data.get("decision_note", ""),
        )
        return Response(self.get_serializer(decided).data)

    @extend_schema(request=TimeDecisionSerializer, responses=TimeEntrySerializer)
    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request: Request, pk: str | None = None) -> Response:
        entry = self.get_object()
        self._require_manage_scope(request_user(request), entry)
        serializer = TimeDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        decided = decide_time_entry(
            int(entry.pk),
            request_user(request),
            approve=False,
            decision_note=serializer.validated_data.get("decision_note", ""),
        )
        return Response(self.get_serializer(decided).data)

    def _require_manage_scope(self, user: User, entry: TimeEntry) -> None:
        if is_elevated(user):
            return
        profile = employee_for(user)
        if (
            not has_role(user, "Manager")
            or profile is None
            or not (
                entry.employee.manager_id == profile.pk
                or can_manage_project(user, entry.task.project)
            )
        ):
            raise PermissionDenied("You cannot review this employee's time.")


class TimeSubmissionViewSet(viewsets.ModelViewSet[TimeSubmission]):
    serializer_class = TimeSubmissionSerializer
    permission_classes = [InternalProjectRolePermission]
    http_method_names = ["get", "post", "head", "options"]
    filterset_fields = ["period_type", "period_start", "period_end", "status", "employee"]
    search_fields = ["employee__employee_number", "employee__user__first_name"]
    ordering_fields = ["period_start", "submitted_at", "status"]

    def get_queryset(self) -> QuerySet[TimeSubmission]:
        if getattr(self, "swagger_fake_view", False):
            return TimeSubmission.objects.none()
        user = request_user(self.request)
        submissions = TimeSubmission.objects.filter(is_deleted=False)
        if is_elevated(user):
            pass
        elif has_role(user, "Manager"):
            submissions = submissions.filter(
                Q(employee__in=team_scope(user))
                | Q(entries__task__project__in=project_scope(user, include_clients=False))
            )
        else:
            profile = employee_for(user)
            if profile is None:
                return TimeSubmission.objects.none()
            submissions = submissions.filter(employee=profile)
        return (
            submissions.select_related("employee", "employee__user", "approver")
            .prefetch_related("entries")
            .distinct()
        )

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        submission = create_time_submission(
            request_user(request),
            period_type=data["period_type"],
            period_start=data["period_start"],
            period_end=data["period_end"],
            entry_ids=[entry.pk for entry in data["entries"]],
        )
        output = self.get_serializer(submission)
        return Response(output.data, status=201)

    @extend_schema(request=TimeDecisionSerializer, responses=TimeSubmissionSerializer)
    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request: Request, pk: str | None = None) -> Response:
        submission = self.get_object()
        self._check_review_access(request_user(request), submission)
        serializer = TimeDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        decided = decide_time_submission(
            int(submission.pk),
            request_user(request),
            approve=True,
            decision_note=serializer.validated_data.get("decision_note", ""),
        )
        return Response(self.get_serializer(decided).data)

    @extend_schema(request=TimeDecisionSerializer, responses=TimeSubmissionSerializer)
    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request: Request, pk: str | None = None) -> Response:
        submission = self.get_object()
        self._check_review_access(request_user(request), submission)
        serializer = TimeDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        decided = decide_time_submission(
            int(submission.pk),
            request_user(request),
            approve=False,
            decision_note=serializer.validated_data.get("decision_note", ""),
        )
        return Response(self.get_serializer(decided).data)

    def _check_review_access(self, user: User, submission: TimeSubmission) -> None:
        if is_elevated(user):
            return
        profile = employee_for(user)
        project_manager = (
            submission.entries.filter(
                task__project__manager=profile,
                task__project__is_deleted=False,
            ).exists()
            if profile is not None
            else False
        )
        if (
            not has_role(user, "Manager")
            or profile is None
            or submission.employee.user_id == user.pk
            or not (submission.employee.manager_id == profile.pk or project_manager)
        ):
            raise PermissionDenied("You cannot review this time submission.")


class ResourceAllocationViewSet(viewsets.ModelViewSet[ResourceAllocation]):
    serializer_class = ResourceAllocationSerializer
    permission_classes = [InternalProjectRolePermission]
    filterset_fields = ["project", "employee", "start_date", "end_date"]
    search_fields = ["project__name", "project__code", "employee__employee_number", "role"]
    ordering_fields = ["start_date", "end_date", "allocation_percent"]

    @extend_schema(
        parameters=[
            OpenApiParameter(name="start_date", type=str, required=True),
            OpenApiParameter(name="end_date", type=str, required=True),
        ],
        responses=ResourceCapacityRowSerializer(many=True),
    )
    @action(detail=False, methods=["get"], url_path="capacity")
    def capacity(self, request: Request) -> Response:
        try:
            start = date.fromisoformat(request.query_params["start_date"])
            end = date.fromisoformat(request.query_params["end_date"])
        except (KeyError, ValueError) as error:
            raise ValidationError(
                {"start_date": "Provide ISO start_date and end_date values."}
            ) from error
        if end < start or (end - start).days > 90:
            raise ValidationError(
                {"end_date": "End must follow start and the capacity window cannot exceed 90 days."}
            )
        allocations = (
            self.get_queryset()
            .filter(
                start_date__lte=end,
            )
            .filter(Q(end_date__isnull=True) | Q(end_date__gte=start))
        )
        days = [
            start + timedelta(days=offset)
            for offset in range((end - start).days + 1)
            if (start + timedelta(days=offset)).weekday() < 5
        ]
        rows: list[dict[str, Any]] = []
        employees: dict[int, list[ResourceAllocation]] = {}
        for allocation in allocations.select_related("employee", "employee__user"):
            employees.setdefault(allocation.employee_id, []).append(allocation)
        for employee_id, employee_allocations in employees.items():
            employee = employee_allocations[0].employee
            for day in days:
                allocated = sum(
                    (
                        allocation.allocation_percent
                        for allocation in employee_allocations
                        if allocation.start_date <= day
                        and (allocation.end_date is None or allocation.end_date >= day)
                    ),
                    Decimal("0.00"),
                )
                rows.append(
                    {
                        "employee_id": employee_id,
                        "employee_number": employee.employee_number,
                        "employee_name": employee.user.get_full_name() or employee.user.email,
                        "date": day,
                        "allocation_percent": allocated,
                        "capacity_hours": (Decimal("8.00") * allocated / Decimal("100.00")),
                        "overallocated": allocated > Decimal("100.00"),
                    }
                )
        return Response(ResourceCapacityRowSerializer(rows, many=True).data)

    def get_queryset(self) -> QuerySet[ResourceAllocation]:
        user = request_user(self.request)
        allocations = ResourceAllocation.objects.filter(is_deleted=False)
        if is_elevated(user):
            pass
        elif has_role(user, "Manager"):
            allocations = allocations.filter(project__in=project_scope(user, include_clients=False))
        elif has_role(user, "Employee") and not has_client_role(user):
            profile = employee_for(user)
            if profile is None:
                return ResourceAllocation.objects.none()
            allocations = allocations.filter(employee=profile)
        else:
            return ResourceAllocation.objects.none()
        return allocations.select_related("project", "employee", "employee__user")

    def perform_create(self, serializer: BaseSerializer[ResourceAllocation]) -> None:
        allocation, many_to_many = build_record(serializer)
        allocation = cast(ResourceAllocation, allocation)
        self._check_allocation(allocation)
        save_record(allocation, request_user(self.request), create=True)
        for field, values in many_to_many.items():
            getattr(allocation, field).set(values)
        serializer.instance = allocation

    def perform_update(self, serializer: BaseSerializer[ResourceAllocation]) -> None:
        allocation, many_to_many = build_record(serializer)
        allocation = cast(ResourceAllocation, allocation)
        self._check_allocation(allocation)
        save_record(allocation, request_user(self.request))
        for field, values in many_to_many.items():
            getattr(allocation, field).set(values)
        serializer.instance = allocation

    def _check_allocation(self, allocation: ResourceAllocation) -> None:
        user = request_user(self.request)
        if not can_manage_project(user, allocation.project):
            raise PermissionDenied("You cannot manage allocations for this project.")
        if (
            not is_elevated(user)
            and not team_scope(user).filter(pk=allocation.employee_id).exists()
        ):
            raise PermissionDenied("You can allocate only your team members.")

    def perform_destroy(self, instance: ResourceAllocation) -> None:
        self._check_allocation(instance)
        instance.is_deleted = True
        instance.updated_by = request_user(self.request)
        instance.save(update_fields=["is_deleted", "updated_by", "updated_at"])
