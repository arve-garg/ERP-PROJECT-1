"""People, attendance, leave, and holiday records."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from zipfile import BadZipFile, ZipFile

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from apps.core.models import AuditedModel


class Department(AuditedModel):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Designation(AuditedModel):
    title = models.CharField(max_length=100)
    department = models.ForeignKey(
        Department, related_name="designations", on_delete=models.PROTECT
    )
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["department__name", "title"]
        constraints = [
            models.UniqueConstraint(
                fields=["department", "title"], name="unique_designation_per_department"
            )
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.department.code})"


class EmployeeProfile(AuditedModel):
    class EmploymentStatus(models.TextChoices):
        ACTIVE = "active", "Active"
        ON_LEAVE = "on_leave", "On leave"
        TERMINATED = "terminated", "Terminated"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, related_name="employee_profile", on_delete=models.PROTECT
    )
    employee_number = models.CharField(max_length=30, unique=True)
    department = models.ForeignKey(
        Department, related_name="employees", on_delete=models.PROTECT, db_index=True
    )
    designation = models.ForeignKey(Designation, related_name="employees", on_delete=models.PROTECT)
    manager = models.ForeignKey(
        "self",
        related_name="direct_reports",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
    )
    phone = models.CharField(max_length=30, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    hire_date = models.DateField(default=date.today, db_index=True)
    termination_date = models.DateField(null=True, blank=True)
    employment_status = models.CharField(
        max_length=20, choices=EmploymentStatus.choices, default=EmploymentStatus.ACTIVE
    )
    location = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["user__last_name", "user__first_name", "employee_number"]
        indexes = [
            models.Index(fields=["department", "employment_status"]),
            models.Index(fields=["manager", "employment_status"]),
        ]

    def clean(self) -> None:
        super().clean()
        current_manager = self.manager
        visited: set[int] = set()
        while current_manager is not None:
            if self.pk is not None and current_manager.pk == self.pk:
                raise ValidationError(
                    {"manager": "Reporting relationships cannot contain a cycle."}
                )
            if current_manager.pk in visited:
                raise ValidationError(
                    {"manager": "The selected manager already has a reporting cycle."}
                )
            visited.add(current_manager.pk)
            current_manager = current_manager.manager
        if self.termination_date and self.termination_date < self.hire_date:
            raise ValidationError({"termination_date": "Termination cannot predate the hire date."})
        if self.employment_status == self.EmploymentStatus.TERMINATED and not self.termination_date:
            raise ValidationError(
                {"termination_date": "A termination date is required for terminated employees."}
            )

    def __str__(self) -> str:
        return f"{self.employee_number} - {self.user.get_full_name() or self.user.email}"


class EmergencyContact(AuditedModel):
    employee = models.ForeignKey(
        EmployeeProfile, related_name="emergency_contacts", on_delete=models.CASCADE
    )
    name = models.CharField(max_length=120)
    relationship = models.CharField(max_length=60)
    phone = models.CharField(max_length=30)
    email = models.EmailField(blank=True)
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ["-is_primary", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee"],
                condition=Q(is_primary=True, is_deleted=False),
                name="one_primary_emergency_contact_per_employee",
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.relationship})"


def validate_employee_document(upload: Any) -> None:
    """Reject oversized and unsupported uploads using their file signature."""
    if upload.size == 0 or upload.size > 10 * 1024 * 1024:
        raise ValidationError("Documents must be non-empty and no larger than 10 MiB.")
    extension = upload.name.rsplit(".", 1)[-1].lower() if "." in upload.name else ""
    header = upload.read(8)
    upload.seek(0)
    signatures = {
        "pdf": header.startswith(b"%PDF-"),
        "png": header.startswith(b"\x89PNG\r\n\x1a\n"),
        "jpg": header.startswith(b"\xff\xd8\xff"),
        "jpeg": header.startswith(b"\xff\xd8\xff"),
    }
    if extension in signatures:
        valid = signatures[extension]
    elif extension == "docx" and header.startswith(b"PK"):
        try:
            with ZipFile(upload) as archive:
                valid = {
                    "[Content_Types].xml",
                    "word/document.xml",
                }.issubset(archive.namelist())
        except (BadZipFile, OSError, ValueError):
            valid = False
    else:
        valid = False
    if not valid:
        raise ValidationError("Upload a valid PDF, PNG, JPEG, or DOCX document.")


class EmployeeDocument(AuditedModel):
    employee = models.ForeignKey(
        EmployeeProfile, related_name="documents", on_delete=models.CASCADE, db_index=True
    )
    title = models.CharField(max_length=150)
    document_type = models.CharField(max_length=40)
    file = models.FileField(
        upload_to="hr/employee-documents/%Y/%m/", validators=[validate_employee_document]
    )
    expires_on = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title


class Attendance(AuditedModel):
    employee = models.ForeignKey(
        EmployeeProfile, related_name="attendance", on_delete=models.CASCADE, db_index=True
    )
    date = models.DateField(db_index=True)
    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)
    is_late = models.BooleanField(default=False)
    left_early = models.BooleanField(default=False)
    notes = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["-date", "employee__employee_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "date"], name="unique_attendance_per_employee_date"
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.check_in and self.check_out and self.check_out < self.check_in:
            raise ValidationError({"check_out": "Check-out cannot be earlier than check-in."})

    def __str__(self) -> str:
        return f"{self.employee.employee_number} - {self.date}"


class LeaveType(AuditedModel):
    name = models.CharField(max_length=80, unique=True)
    annual_allowance_days = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
    )
    is_paid = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class LeaveBalance(AuditedModel):
    employee = models.ForeignKey(
        EmployeeProfile, related_name="leave_balances", on_delete=models.CASCADE, db_index=True
    )
    leave_type = models.ForeignKey(LeaveType, related_name="balances", on_delete=models.PROTECT)
    year = models.PositiveSmallIntegerField(db_index=True)
    accrued_days = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("0.00"))
    adjustment_days = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("0.00"))
    used_days = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        ordering = ["year", "leave_type__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "leave_type", "year"],
                name="unique_leave_balance_per_employee_type_year",
            )
        ]

    @property
    def available_days(self) -> Decimal:
        return self.accrued_days + self.adjustment_days - self.used_days

    def __str__(self) -> str:
        return f"{self.employee.employee_number} - {self.leave_type.name} {self.year}"


class LeaveAccrual(AuditedModel):
    """Idempotency record for a monthly leave accrual."""

    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE)
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE)
    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField()
    accrued_days = models.DecimalField(max_digits=6, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "leave_type", "year", "month"],
                name="unique_leave_accrual_per_month",
            )
        ]


class LeaveRequest(AuditedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    employee = models.ForeignKey(
        EmployeeProfile, related_name="leave_requests", on_delete=models.CASCADE, db_index=True
    )
    leave_type = models.ForeignKey(LeaveType, related_name="requests", on_delete=models.PROTECT)
    start_date = models.DateField(db_index=True)
    end_date = models.DateField(db_index=True)
    requested_days = models.DecimalField(
        max_digits=6, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    reason = models.TextField(max_length=2000)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="approved_leave_requests",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    decision_note = models.CharField(max_length=1000, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "start_date", "end_date"])]

    def clean(self) -> None:
        super().clean()
        if self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date must be on or after the start date."})
        if self.start_date.year != self.end_date.year:
            raise ValidationError(
                {"end_date": "A leave request must stay within one calendar year."}
            )
        if self.employee_id and self.start_date < self.employee.hire_date:
            raise ValidationError(
                {"start_date": "Leave cannot begin before the employee's hire date."}
            )

    def __str__(self) -> str:
        return f"{self.employee.employee_number} - {self.leave_type.name} ({self.status})"


class Holiday(AuditedModel):
    name = models.CharField(max_length=120)
    date = models.DateField(db_index=True)
    description = models.CharField(max_length=500, blank=True)
    is_recurring = models.BooleanField(default=False)

    class Meta:
        ordering = ["date", "name"]
        constraints = [
            models.UniqueConstraint(fields=["name", "date"], name="unique_holiday_name_per_date")
        ]

    def __str__(self) -> str:
        return f"{self.name} - {self.date}"
