"""Client delivery, work planning, time tracking, and resource allocation records."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import PurePosixPath
from typing import Any
from zipfile import BadZipFile, ZipFile

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.models import AuditedModel
from apps.hr.models import EmployeeProfile


class Client(AuditedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    name = models.CharField(max_length=160, unique=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    website = models.URLField(blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    portal_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="project_clients", blank=True
    )

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Project(AuditedModel):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        ACTIVE = "active", "Active"
        ON_HOLD = "on_hold", "On hold"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    client = models.ForeignKey(
        Client, related_name="projects", on_delete=models.PROTECT, db_index=True
    )
    name = models.CharField(max_length=160)
    code = models.CharField(max_length=30, unique=True)
    description = models.TextField(blank=True)
    manager = models.ForeignKey(
        EmployeeProfile, related_name="managed_projects", on_delete=models.PROTECT
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    estimated_hours = models.DecimalField(
        max_digits=9,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    budget = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    budget_currency = models.CharField(
        max_length=3,
        default=settings.BASE_CURRENCY,
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PLANNED)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "start_date"])]

    def clean(self) -> None:
        super().clean()
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot precede the start date."})
        if (
            len(self.budget_currency) != 3
            or not self.budget_currency.isalpha()
            or self.budget_currency != self.budget_currency.upper()
        ):
            raise ValidationError(
                {"budget_currency": "Currency must be a three-letter uppercase code."}
            )
        if (
            self.manager_id
            and self.manager.employment_status == EmployeeProfile.EmploymentStatus.TERMINATED
        ):
            raise ValidationError({"manager": "A terminated employee cannot manage a project."})

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class Milestone(AuditedModel):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        BLOCKED = "blocked", "Blocked"

    project = models.ForeignKey(Project, related_name="milestones", on_delete=models.CASCADE)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    due_date = models.DateField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PLANNED)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["due_date", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "name"],
                condition=Q(is_deleted=False),
                name="unique_live_milestone_name_per_project",
            )
        ]

    def __str__(self) -> str:
        return f"{self.project.code}: {self.name}"

    def clean(self) -> None:
        super().clean()
        if self.project_id and self.due_date < self.project.start_date:
            raise ValidationError(
                {"due_date": "Milestone cannot be due before the project starts."}
            )
        if self.project_id and self.project.end_date and self.due_date > self.project.end_date:
            raise ValidationError({"due_date": "Milestone cannot be due after the project ends."})


class Sprint(AuditedModel):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    project = models.ForeignKey(Project, related_name="sprints", on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    goal = models.TextField(blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PLANNED)

    class Meta:
        ordering = ["-start_date", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "name"],
                condition=Q(is_deleted=False),
                name="unique_live_sprint_name_per_project",
            ),
            models.UniqueConstraint(
                fields=["project"],
                condition=Q(status="active", is_deleted=False),
                name="one_active_sprint_per_project",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.end_date < self.start_date:
            raise ValidationError({"end_date": "Sprint end date must be on or after its start."})
        if self.project_id and self.start_date < self.project.start_date:
            raise ValidationError({"start_date": "Sprint cannot start before the project."})
        if self.project_id and self.project.end_date and self.end_date > self.project.end_date:
            raise ValidationError({"end_date": "Sprint cannot end after the project."})

    def __str__(self) -> str:
        return f"{self.project.code}: {self.name}"


class TaskLabel(AuditedModel):
    name = models.CharField(max_length=40, unique=True)
    color = models.CharField(max_length=7, default="#64748B")

    class Meta:
        ordering = ["name"]

    def clean(self) -> None:
        super().clean()
        if len(self.color) != 7 or not self.color.startswith("#"):
            raise ValidationError({"color": "Color must use #RRGGBB format."})
        try:
            int(self.color[1:], 16)
        except ValueError as error:
            raise ValidationError({"color": "Color must use #RRGGBB format."}) from error

    def __str__(self) -> str:
        return self.name


class Task(AuditedModel):
    class Status(models.TextChoices):
        BACKLOG = "backlog", "Backlog"
        READY = "ready", "Ready"
        IN_PROGRESS = "in_progress", "In progress"
        BLOCKED = "blocked", "Blocked"
        DONE = "done", "Done"
        CANCELLED = "cancelled", "Cancelled"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    project = models.ForeignKey(Project, related_name="tasks", on_delete=models.CASCADE)
    milestone = models.ForeignKey(
        Milestone, related_name="tasks", null=True, blank=True, on_delete=models.SET_NULL
    )
    sprint = models.ForeignKey(
        Sprint, related_name="tasks", null=True, blank=True, on_delete=models.SET_NULL
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    assignee = models.ForeignKey(
        EmployeeProfile,
        related_name="assigned_tasks",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
    )
    labels = models.ManyToManyField(TaskLabel, related_name="tasks", blank=True)
    estimate_hours = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    priority = models.CharField(max_length=12, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.BACKLOG)
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["project", "status"]),
            models.Index(fields=["assignee", "status"]),
        ]

    def clean(self) -> None:
        super().clean()
        if self.project_id and self.due_date and self.due_date < self.project.start_date:
            raise ValidationError({"due_date": "Task cannot be due before the project starts."})
        if (
            self.project_id
            and self.project.end_date
            and self.due_date
            and self.due_date > self.project.end_date
        ):
            raise ValidationError({"due_date": "Task cannot be due after the project ends."})
        if self.milestone is not None and self.milestone.project_id != self.project_id:
            raise ValidationError({"milestone": "Milestone must belong to the task's project."})
        if self.sprint is not None and self.sprint.project_id != self.project_id:
            raise ValidationError({"sprint": "Sprint must belong to the task's project."})
        if (
            self.assignee is not None
            and self.assignee.employment_status == EmployeeProfile.EmploymentStatus.TERMINATED
        ):
            raise ValidationError({"assignee": "A terminated employee cannot be assigned."})

    def __str__(self) -> str:
        return self.title


def validate_private_attachment(upload: Any) -> None:
    """Allow small, signature-checked project files for authenticated download only."""
    if upload.size == 0 or upload.size > 10 * 1024 * 1024:
        raise ValidationError("Attachments must be non-empty and no larger than 10 MiB.")
    extension = PurePosixPath(upload.name).suffix.lower().lstrip(".")
    header = upload.read(8)
    upload.seek(0)
    signatures = {
        "pdf": header.startswith(b"%PDF-"),
        "png": header.startswith(b"\x89PNG\r\n\x1a\n"),
        "jpg": header.startswith(b"\xff\xd8\xff"),
        "jpeg": header.startswith(b"\xff\xd8\xff"),
    }
    if extension == "docx" and header.startswith(b"PK"):
        try:
            with ZipFile(upload) as archive:
                valid = {
                    "[Content_Types].xml",
                    "word/document.xml",
                }.issubset(archive.namelist())
        except (BadZipFile, OSError, ValueError):
            valid = False
    else:
        valid = signatures.get(extension, False)
    if not valid:
        raise ValidationError("Upload a valid PDF, PNG, JPEG, or DOCX attachment.")


class TaskAttachment(AuditedModel):
    task = models.ForeignKey(Task, related_name="attachments", on_delete=models.CASCADE)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="project_task_attachments", on_delete=models.PROTECT
    )
    file = models.FileField(
        upload_to="projects/task-attachments/%Y/%m/", validators=[validate_private_attachment]
    )
    file_name = models.CharField(max_length=255)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.file_name


class ProjectDocument(AuditedModel):
    project = models.ForeignKey(Project, related_name="documents", on_delete=models.CASCADE)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="project_documents_uploaded",
        on_delete=models.PROTECT,
    )
    title = models.CharField(max_length=180)
    description = models.CharField(max_length=1000, blank=True)
    file = models.FileField(
        upload_to="projects/documents/%Y/%m/", validators=[validate_private_attachment]
    )
    file_name = models.CharField(max_length=255)
    client_visible = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.project.code}: {self.title}"


class ProjectWikiPage(AuditedModel):
    project = models.ForeignKey(Project, related_name="wiki_pages", on_delete=models.CASCADE)
    title = models.CharField(max_length=180)
    slug = models.SlugField(max_length=200)
    content = models.TextField()

    class Meta:
        ordering = ["title"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "slug"],
                condition=Q(is_deleted=False),
                name="unique_live_wiki_slug_per_project",
            )
        ]

    def __str__(self) -> str:
        return f"{self.project.code}: {self.title}"


class Bug(AuditedModel):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        TRIAGED = "triaged", "Triaged"
        IN_PROGRESS = "in_progress", "In progress"
        FIXED = "fixed", "Fixed"
        VERIFIED = "verified", "Verified"
        CLOSED = "closed", "Closed"
        WONT_FIX = "wont_fix", "Won't fix"

    class Severity(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    project = models.ForeignKey(Project, related_name="bugs", on_delete=models.CASCADE)
    task = models.ForeignKey(
        Task, related_name="bugs", null=True, blank=True, on_delete=models.SET_NULL
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    steps_to_reproduce = models.TextField(blank=True)
    expected_behavior = models.TextField(blank=True)
    actual_behavior = models.TextField(blank=True)
    severity = models.CharField(max_length=12, choices=Severity.choices, default=Severity.MEDIUM)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="reported_project_bugs",
        on_delete=models.PROTECT,
    )
    assignee = models.ForeignKey(
        EmployeeProfile,
        related_name="assigned_project_bugs",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["project", "status", "severity"])]

    def clean(self) -> None:
        super().clean()
        if self.task is not None and self.task.project_id != self.project_id:
            raise ValidationError({"task": "Bug task must belong to the selected project."})

    def __str__(self) -> str:
        return self.title


class ReleaseNote(AuditedModel):
    project = models.ForeignKey(Project, related_name="release_notes", on_delete=models.CASCADE)
    version = models.CharField(max_length=40)
    title = models.CharField(max_length=180)
    content = models.TextField()
    release_date = models.DateField(default=date.today)
    is_published = models.BooleanField(default=False)

    class Meta:
        ordering = ["-release_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "version"],
                condition=Q(is_deleted=False),
                name="unique_live_release_version_per_project",
            )
        ]

    def __str__(self) -> str:
        return f"{self.project.code} {self.version}"


class EmployeeHourlyCost(AuditedModel):
    employee = models.ForeignKey(
        EmployeeProfile, related_name="hourly_cost_rates", on_delete=models.CASCADE
    )
    hourly_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    currency = models.CharField(max_length=3, default="USD")
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["employee", "-effective_from"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "currency", "effective_from"],
                condition=Q(is_deleted=False),
                name="unique_hourly_cost_currency_effective_date",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError({"effective_to": "Rate end cannot precede its start."})
        if (
            len(self.currency) != 3
            or not self.currency.isalpha()
            or self.currency != self.currency.upper()
        ):
            raise ValidationError({"currency": "Currency must be a three-letter uppercase code."})
        overlap = EmployeeHourlyCost.objects.filter(
            employee_id=self.employee_id,
            currency=self.currency,
            is_deleted=False,
            effective_from__lte=self.effective_to or date.max,
        ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=self.effective_from))
        if self.pk:
            overlap = overlap.exclude(pk=self.pk)
        if overlap.exists():
            raise ValidationError({"effective_from": "Hourly cost periods cannot overlap."})

    def __str__(self) -> str:
        return f"{self.employee.employee_number}: {self.hourly_cost} {self.currency}/hour"


class TaskComment(AuditedModel):
    task = models.ForeignKey(Task, related_name="comments", on_delete=models.CASCADE)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="project_task_comments", on_delete=models.PROTECT
    )
    body = models.TextField(max_length=5000)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Comment by {self.author} on {self.task}"


class TimeEntry(AuditedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    task = models.ForeignKey(Task, related_name="time_entries", on_delete=models.PROTECT)
    employee = models.ForeignKey(
        EmployeeProfile, related_name="time_entries", on_delete=models.PROTECT, db_index=True
    )
    work_date = models.DateField(db_index=True)
    hours = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01")), MaxValueValidator(Decimal("24.00"))],
    )
    description = models.CharField(max_length=1000, blank=True)
    is_billable = models.BooleanField(default=True)
    hourly_cost_snapshot = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    hourly_cost_currency_snapshot = models.CharField(
        max_length=3,
        default=settings.BASE_CURRENCY,
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    submitted_at = models.DateTimeField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="approved_time_entries",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    decision_note = models.CharField(max_length=1000, blank=True)

    class Meta:
        ordering = ["-work_date", "-created_at"]
        indexes = [models.Index(fields=["employee", "status", "work_date"])]

    def clean(self) -> None:
        super().clean()
        if self.task_id and self.employee_id:
            if self.task.assignee_id != self.employee_id:
                raise ValidationError({"employee": "Time must be recorded by the task assignee."})
            if self.task.project.is_deleted or self.task.is_deleted:
                raise ValidationError({"task": "Time cannot be recorded against an archived task."})
        if self.work_date and self.task_id and self.work_date < self.task.created_at.date():
            raise ValidationError({"work_date": "Work date cannot predate task creation."})

    def __str__(self) -> str:
        return f"{self.employee.employee_number}: {self.hours}h on {self.work_date}"


class TimeSubmission(AuditedModel):
    class PeriodType(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"

    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    employee = models.ForeignKey(
        EmployeeProfile, related_name="time_submissions", on_delete=models.PROTECT
    )
    period_type = models.CharField(max_length=8, choices=PeriodType.choices)
    period_start = models.DateField()
    period_end = models.DateField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SUBMITTED)
    entries = models.ManyToManyField(TimeEntry, related_name="submissions")
    submitted_at = models.DateTimeField(default=timezone.now)
    decided_at = models.DateTimeField(null=True, blank=True)
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="decided_time_submissions",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    decision_note = models.CharField(max_length=1000, blank=True)

    class Meta:
        ordering = ["-period_start", "-created_at"]

    def clean(self) -> None:
        super().clean()
        from datetime import timedelta

        if self.period_type == self.PeriodType.DAILY and self.period_end != self.period_start:
            raise ValidationError({"period_end": "A daily submission must cover one day."})
        if self.period_type == self.PeriodType.WEEKLY:
            if self.period_start.weekday() != 0 or self.period_end != self.period_start + timedelta(
                days=6
            ):
                raise ValidationError(
                    {"period_start": "A weekly submission must cover Monday through Sunday."}
                )
        if self.period_end < self.period_start:
            raise ValidationError({"period_end": "Period end cannot precede period start."})

    def __str__(self) -> str:
        return f"{self.employee.employee_number}: {self.period_type} {self.period_start}"


class ResourceAllocation(AuditedModel):
    project = models.ForeignKey(Project, related_name="allocations", on_delete=models.CASCADE)
    employee = models.ForeignKey(
        EmployeeProfile, related_name="resource_allocations", on_delete=models.PROTECT
    )
    role = models.CharField(max_length=100, blank=True)
    allocation_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal("0.01")),
            MaxValueValidator(Decimal("100.00")),
        ],
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["start_date", "employee__employee_number"]
        indexes = [models.Index(fields=["employee", "start_date", "end_date"])]

    def clean(self) -> None:
        super().clean()
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot precede the start date."})
        if (
            self.employee_id
            and self.employee.employment_status == EmployeeProfile.EmploymentStatus.TERMINATED
        ):
            raise ValidationError({"employee": "A terminated employee cannot be allocated."})
        if self.project_id and self.start_date < self.project.start_date:
            raise ValidationError({"start_date": "Allocation cannot start before the project."})
        if (
            self.project_id
            and self.project.end_date
            and (self.end_date is None or self.end_date > self.project.end_date)
        ):
            raise ValidationError({"end_date": "Allocation cannot extend beyond the project."})

    def __str__(self) -> str:
        return f"{self.employee.employee_number}: {self.project.code} ({self.allocation_percent}%)"
