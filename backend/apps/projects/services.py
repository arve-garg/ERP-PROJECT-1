"""Transactional project workflows and lifecycle transitions."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, cast

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.core.models import User
from apps.hr.models import EmployeeProfile
from apps.projects.models import (
    Bug,
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

AuditedRecord = (
    Bug
    | EmployeeHourlyCost
    | Milestone
    | Project
    | ProjectDocument
    | ProjectWikiPage
    | ReleaseNote
    | ResourceAllocation
    | Sprint
    | Task
    | TaskAttachment
    | TaskComment
    | TaskLabel
    | TimeEntry
    | TimeSubmission
)

PROJECT_TRANSITIONS = {
    Project.Status.PLANNED: {Project.Status.ACTIVE, Project.Status.CANCELLED},
    Project.Status.ACTIVE: {
        Project.Status.ON_HOLD,
        Project.Status.COMPLETED,
        Project.Status.CANCELLED,
    },
    Project.Status.ON_HOLD: {Project.Status.ACTIVE, Project.Status.CANCELLED},
    Project.Status.COMPLETED: set(),
    Project.Status.CANCELLED: set(),
}
TASK_TRANSITIONS = {
    Task.Status.BACKLOG: {Task.Status.READY, Task.Status.CANCELLED},
    Task.Status.READY: {Task.Status.IN_PROGRESS, Task.Status.BLOCKED, Task.Status.CANCELLED},
    Task.Status.IN_PROGRESS: {
        Task.Status.BLOCKED,
        Task.Status.DONE,
        Task.Status.CANCELLED,
    },
    Task.Status.BLOCKED: {Task.Status.READY, Task.Status.IN_PROGRESS, Task.Status.CANCELLED},
    Task.Status.DONE: set(),
    Task.Status.CANCELLED: set(),
}
SPRINT_TRANSITIONS = {
    Sprint.Status.PLANNED: {Sprint.Status.ACTIVE, Sprint.Status.CANCELLED},
    Sprint.Status.ACTIVE: {Sprint.Status.COMPLETED, Sprint.Status.CANCELLED},
    Sprint.Status.COMPLETED: set(),
    Sprint.Status.CANCELLED: set(),
}
MILESTONE_TRANSITIONS = {
    Milestone.Status.PLANNED: {
        Milestone.Status.IN_PROGRESS,
        Milestone.Status.BLOCKED,
    },
    Milestone.Status.IN_PROGRESS: {Milestone.Status.BLOCKED, Milestone.Status.COMPLETED},
    Milestone.Status.BLOCKED: {Milestone.Status.IN_PROGRESS},
    Milestone.Status.COMPLETED: set(),
}
BUG_TRANSITIONS = {
    Bug.Status.OPEN: {Bug.Status.TRIAGED, Bug.Status.WONT_FIX},
    Bug.Status.TRIAGED: {Bug.Status.IN_PROGRESS, Bug.Status.WONT_FIX},
    Bug.Status.IN_PROGRESS: {Bug.Status.FIXED, Bug.Status.OPEN, Bug.Status.WONT_FIX},
    Bug.Status.FIXED: {Bug.Status.VERIFIED, Bug.Status.IN_PROGRESS},
    Bug.Status.VERIFIED: {Bug.Status.CLOSED, Bug.Status.IN_PROGRESS},
    Bug.Status.CLOSED: set(),
    Bug.Status.WONT_FIX: set(),
}


def build_record(serializer: Any) -> tuple[Any, dict[str, Any]]:
    """Build a candidate model without persisting it, including deferred M2M values."""
    model = serializer.Meta.model
    record = serializer.instance if serializer.instance is not None else model()
    values = dict(serializer.validated_data)
    many_to_many: dict[str, Any] = {}
    for field in model._meta.many_to_many:
        if field.name in values:
            many_to_many[field.name] = values.pop(field.name)
    for name, value in values.items():
        setattr(record, name, value)
    return record, many_to_many


def save_record[T: AuditedRecord](record: T, actor: User, *, create: bool = False) -> T:
    """Validate and save an audited record with its acting user."""
    try:
        record.full_clean()
    except DjangoValidationError as error:
        detail = error.message_dict if hasattr(error, "message_dict") else error.messages
        raise ValidationError(detail) from error
    record.updated_by = actor
    if create:
        record.created_by = actor
    record.save()
    return record


@transaction.atomic
def save_serialized_record(serializer: Any, actor: User, *, create: bool = False) -> AuditedRecord:
    record, many_to_many = build_record(serializer)
    persisted = save_record(cast(AuditedRecord, record), actor, create=create)
    for field, values in many_to_many.items():
        getattr(persisted, field).set(values)
    serializer.instance = persisted
    return persisted


def transition_status(
    model: type[Project] | type[Milestone] | type[Task] | type[Sprint] | type[Bug],
    record_id: int,
    new_status: str,
    actor: User,
) -> Project | Milestone | Task | Sprint | Bug:
    """Apply an allowed lifecycle transition under a row lock."""
    with transaction.atomic():
        try:
            record = model.objects.select_for_update().get(pk=record_id, is_deleted=False)
        except model.DoesNotExist as error:
            raise ValidationError({"detail": "The requested record no longer exists."}) from error
        if model is Project:
            allowed = {
                str(status)
                for status in PROJECT_TRANSITIONS.get(Project.Status(record.status), set())
            }
        elif model is Milestone:
            allowed = {
                str(status)
                for status in MILESTONE_TRANSITIONS.get(Milestone.Status(record.status), set())
            }
        elif model is Task:
            allowed = {
                str(status) for status in TASK_TRANSITIONS.get(Task.Status(record.status), set())
            }
        elif model is Bug:
            allowed = {
                str(status) for status in BUG_TRANSITIONS.get(Bug.Status(record.status), set())
            }
        else:
            allowed = {
                str(status)
                for status in SPRINT_TRANSITIONS.get(Sprint.Status(record.status), set())
            }
        if new_status not in allowed:
            raise ValidationError(
                {"status": f"Cannot transition from {record.status} to {new_status}."}
            )
        if isinstance(record, Project) and new_status == Project.Status.COMPLETED:
            if (
                record.tasks.exclude(status__in=[Task.Status.DONE, Task.Status.CANCELLED])
                .filter(is_deleted=False)
                .exists()
            ):
                raise ValidationError({"status": "Complete or cancel all project tasks first."})
        if isinstance(record, (Milestone, Sprint)) and new_status in {
            Milestone.Status.COMPLETED,
            Sprint.Status.COMPLETED,
        }:
            if (
                record.tasks.exclude(status__in=[Task.Status.DONE, Task.Status.CANCELLED])
                .filter(is_deleted=False)
                .exists()
            ):
                raise ValidationError({"status": "Complete or cancel all associated tasks first."})
        record.status = new_status
        if isinstance(record, Milestone):
            record.completed_at = (
                timezone.now() if new_status == Milestone.Status.COMPLETED else None
            )
        elif isinstance(record, Task):
            record.completed_at = timezone.now() if new_status == Task.Status.DONE else None
        elif isinstance(record, Bug):
            record.resolved_at = (
                timezone.now()
                if new_status in {Bug.Status.FIXED, Bug.Status.VERIFIED, Bug.Status.CLOSED}
                else None
            )
        record.updated_by = actor
        try:
            with transaction.atomic():
                if isinstance(record, (Milestone, Task)):
                    record.save(
                        update_fields=["status", "completed_at", "updated_by", "updated_at"]
                    )
                elif isinstance(record, Bug):
                    record.save(update_fields=["status", "resolved_at", "updated_by", "updated_at"])
                else:
                    record.save(update_fields=["status", "updated_by", "updated_at"])
        except IntegrityError as error:
            raise ValidationError(
                {"status": "The requested transition conflicts with another active record."}
            ) from error
        return record


@transaction.atomic
def submit_time_entry(entry_id: int, actor: User) -> TimeEntry:
    entry = _locked_entry(entry_id)
    if entry.employee.user_id != actor.pk:
        raise PermissionDenied("Employees can submit only their own time entries.")
    if entry.status not in {TimeEntry.Status.DRAFT, TimeEntry.Status.REJECTED}:
        raise ValidationError({"status": "Only draft or rejected time can be submitted."})
    if entry.work_date > timezone.localdate():
        raise ValidationError({"work_date": "Future time entries cannot be submitted."})
    if entry.task.assignee_id != entry.employee_id:
        raise ValidationError({"task": "Time must be recorded against a task assigned to you."})
    entry.status = TimeEntry.Status.SUBMITTED
    entry.submitted_at = timezone.now()
    entry.decided_at = None
    entry.approver = None
    entry.decision_note = ""
    entry.updated_by = actor
    entry.save(
        update_fields=[
            "status",
            "submitted_at",
            "decided_at",
            "approver",
            "decision_note",
            "updated_by",
            "updated_at",
        ]
    )
    return entry


@transaction.atomic
def create_time_submission(
    actor: User,
    *,
    period_type: str,
    period_start: date,
    period_end: date,
    entry_ids: list[int],
) -> TimeSubmission:
    """Submit an employee's complete selected daily or weekly time set atomically."""
    employee = EmployeeProfile.objects.filter(user=actor, is_deleted=False).first()
    if employee is None:
        raise PermissionDenied("An employee profile is required to submit time.")
    draft = TimeSubmission(
        employee=employee,
        period_type=period_type,
        period_start=period_start,
        period_end=period_end,
    )
    try:
        draft.full_clean()
    except DjangoValidationError as error:
        detail = error.message_dict if hasattr(error, "message_dict") else error.messages
        raise ValidationError(detail) from error
    if not entry_ids or len(entry_ids) != len(set(entry_ids)):
        raise ValidationError({"entries": "Choose one or more unique time entries."})
    entries = list(
        TimeEntry.objects.select_for_update()
        .filter(pk__in=entry_ids, employee=employee, is_deleted=False)
        .select_related("task", "task__project")
        .order_by("pk")
    )
    if len(entries) != len(entry_ids):
        raise ValidationError({"entries": "All selected entries must belong to you."})
    if any(
        entry.status not in {TimeEntry.Status.DRAFT, TimeEntry.Status.REJECTED} for entry in entries
    ):
        raise ValidationError({"entries": "Only draft or rejected entries can be submitted."})
    if any(not period_start <= entry.work_date <= period_end for entry in entries):
        raise ValidationError(
            {"entries": "Selected entries must fall inside this submission period."}
        )
    if TimeSubmission.objects.filter(
        employee=employee,
        period_type=period_type,
        period_start=period_start,
        status=TimeSubmission.Status.SUBMITTED,
        is_deleted=False,
    ).exists():
        raise ValidationError({"period_start": "A submission for this period is already pending."})
    submission = save_record(draft, actor, create=True)
    submission.entries.set(entries)
    now = timezone.now()
    for entry in entries:
        entry.status = TimeEntry.Status.SUBMITTED
        entry.submitted_at = now
        entry.decided_at = None
        entry.approver = None
        entry.decision_note = ""
        entry.updated_by = actor
        entry.save(
            update_fields=[
                "status",
                "submitted_at",
                "decided_at",
                "approver",
                "decision_note",
                "updated_by",
                "updated_at",
            ]
        )
    return submission


@transaction.atomic
def decide_time_submission(
    submission_id: int,
    actor: User,
    *,
    approve: bool,
    decision_note: str = "",
) -> TimeSubmission:
    try:
        submission = (
            TimeSubmission.objects.select_for_update()
            .select_related("employee", "employee__manager")
            .prefetch_related("entries__task__project")
            .get(pk=submission_id, is_deleted=False)
        )
    except TimeSubmission.DoesNotExist as error:
        raise ValidationError({"detail": "The time submission no longer exists."}) from error
    manager_profile = EmployeeProfile.objects.filter(user=actor).first()
    elevated = actor.is_superuser or actor.roles.filter(name__in=["Admin", "HR"]).exists()
    manages_employee = (
        actor.roles.filter(name="Manager").exists()
        and manager_profile is not None
        and (
            submission.employee.manager_id == manager_profile.pk
            or submission.entries.filter(
                task__project__manager=manager_profile,
                task__project__is_deleted=False,
            ).exists()
        )
    )
    if not (elevated or manages_employee) or submission.employee.user_id == actor.pk:
        raise PermissionDenied("Only HR, Admin, or an authorized manager can decide time.")
    if submission.status != TimeSubmission.Status.SUBMITTED:
        raise ValidationError({"status": "Only submitted time can be decided."})
    if not approve and not decision_note.strip():
        raise ValidationError({"decision_note": "A rejection note is required."})
    submission.status = (
        TimeSubmission.Status.APPROVED if approve else TimeSubmission.Status.REJECTED
    )
    submission.approver = actor
    submission.decision_note = decision_note.strip()
    submission.decided_at = timezone.now()
    submission.updated_by = actor
    submission.save(
        update_fields=[
            "status",
            "approver",
            "decision_note",
            "decided_at",
            "updated_by",
            "updated_at",
        ]
    )
    entry_status = TimeEntry.Status.APPROVED if approve else TimeEntry.Status.REJECTED
    for entry in submission.entries.select_for_update().all():
        if entry.status != TimeEntry.Status.SUBMITTED:
            raise ValidationError(
                {"entries": "The submission contains an entry that is no longer pending."}
            )
        entry.status = entry_status
        entry.approver = actor
        entry.decision_note = decision_note.strip()
        entry.decided_at = submission.decided_at
        entry.updated_by = actor
        entry.save(
            update_fields=[
                "status",
                "approver",
                "decision_note",
                "decided_at",
                "updated_by",
                "updated_at",
            ]
        )
    return submission


def employee_rate_at(employee: EmployeeProfile, work_date: date, currency: str) -> Decimal:
    rate = (
        EmployeeHourlyCost.objects.filter(
            employee=employee,
            currency=currency,
            is_deleted=False,
            effective_from__lte=work_date,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=work_date))
        .order_by("-effective_from")
        .first()
    )
    return rate.hourly_cost if rate is not None else Decimal("0.00")


def _locked_entry(entry_id: int) -> TimeEntry:
    try:
        return (
            TimeEntry.objects.select_for_update()
            .select_related("employee", "employee__manager", "task", "task__project")
            .get(pk=entry_id, is_deleted=False)
        )
    except TimeEntry.DoesNotExist as error:
        raise ValidationError({"detail": "The time entry no longer exists."}) from error


@transaction.atomic
def decide_time_entry(
    entry_id: int, actor: User, *, approve: bool, decision_note: str = ""
) -> TimeEntry:
    entry = _locked_entry(entry_id)
    manager_profile = EmployeeProfile.objects.filter(user=actor).first()
    elevated = actor.is_superuser or actor.roles.filter(name__in=["Admin", "HR"]).exists()
    allowed = elevated or (
        actor.roles.filter(name="Manager").exists()
        and manager_profile is not None
        and (
            entry.employee.manager_id == manager_profile.pk
            or entry.task.project.manager_id == manager_profile.pk
        )
    )
    if not allowed or entry.employee.user_id == actor.pk:
        raise PermissionDenied("Only HR, Admin, or the employee's manager can decide time.")
    if entry.status != TimeEntry.Status.SUBMITTED:
        raise ValidationError({"status": "Only submitted time entries can be decided."})
    if not approve and not decision_note.strip():
        raise ValidationError({"decision_note": "A rejection note is required."})
    entry.status = TimeEntry.Status.APPROVED if approve else TimeEntry.Status.REJECTED
    entry.approver = actor
    entry.decision_note = decision_note.strip()
    entry.decided_at = timezone.now()
    entry.updated_by = actor
    entry.save(
        update_fields=[
            "status",
            "approver",
            "decision_note",
            "decided_at",
            "updated_by",
            "updated_at",
        ]
    )
    return entry


def validate_resource_period(
    allocation: ResourceAllocation, *, start_date: date, end_date: date | None
) -> None:
    """Keep allocation periods inside the project delivery window."""
    if allocation.project.start_date and start_date < allocation.project.start_date:
        raise ValidationError({"start_date": "Allocation cannot start before the project."})
    if allocation.project.end_date and (end_date is None or end_date > allocation.project.end_date):
        raise ValidationError({"end_date": "Allocation cannot extend beyond the project."})
