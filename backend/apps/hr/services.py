"""Transactional HR workflows."""

from __future__ import annotations

import calendar
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.core.models import CompanySetting, User
from apps.hr.models import (
    Attendance,
    EmployeeProfile,
    Holiday,
    LeaveAccrual,
    LeaveBalance,
    LeaveRequest,
    LeaveType,
)


def business_days(start_date: date, end_date: date) -> int:
    """Count weekdays in an inclusive interval, excluding configured company holidays."""
    if end_date < start_date:
        raise ValidationError({"end_date": "End date must be on or after the start date."})
    holiday_dates = set(
        Holiday.objects.filter(
            is_deleted=False, is_recurring=False, date__gte=start_date, date__lte=end_date
        ).values_list("date", flat=True)
    )
    recurring_dates = set(
        Holiday.objects.filter(is_deleted=False, is_recurring=True).values_list(
            "date__month", "date__day"
        )
    )
    total = 0
    current = start_date
    while current <= end_date:
        if (
            current.weekday() < 5
            and current not in holiday_dates
            and (current.month, current.day) not in recurring_dates
        ):
            total += 1
        current += timedelta(days=1)
    return total


def _company_time_setting(key: str, default: str) -> time:
    setting = CompanySetting.objects.filter(key=key, is_deleted=False).first()
    value = str(setting.value) if setting is not None else default
    try:
        return time.fromisoformat(value)
    except ValueError as error:
        raise ValidationError({key: "Company work hours must use HH:MM format."}) from error


@transaction.atomic
def check_in(employee: EmployeeProfile, moment: datetime | None = None) -> Attendance:
    moment = moment or timezone.now()
    local_moment = timezone.localtime(moment)
    attendance, created = Attendance.objects.select_for_update().get_or_create(
        employee=employee, date=local_moment.date()
    )
    if not created and attendance.check_in is not None:
        raise ValidationError({"detail": "You have already checked in today."})
    start_time = _company_time_setting("workday_start", "09:00")
    attendance.check_in = moment
    attendance.is_late = local_moment.time().replace(tzinfo=None) > start_time
    attendance.save(update_fields=["check_in", "is_late", "updated_at", "updated_by"])
    return attendance


@transaction.atomic
def check_out(employee: EmployeeProfile, moment: datetime | None = None) -> Attendance:
    moment = moment or timezone.now()
    local_moment = timezone.localtime(moment)
    try:
        attendance = Attendance.objects.select_for_update().get(
            employee=employee, date=local_moment.date()
        )
    except Attendance.DoesNotExist as error:
        raise ValidationError({"detail": "Check in before checking out."}) from error
    if attendance.check_in is None:
        raise ValidationError({"detail": "Check in before checking out."})
    if attendance.check_out is not None:
        raise ValidationError({"detail": "You have already checked out today."})
    end_time = _company_time_setting("workday_end", "17:00")
    attendance.check_out = moment
    attendance.left_early = local_moment.time().replace(tzinfo=None) < end_time
    attendance.save(update_fields=["check_out", "left_early", "updated_at", "updated_by"])
    return attendance


def manager_can_approve(user: User, employee: EmployeeProfile) -> bool:
    if user.is_superuser or user.roles.filter(name__in=["Admin", "HR"]).exists():
        return True
    manager_profile = EmployeeProfile.objects.filter(user=user).first()
    if manager_profile is None:
        return False
    return employee.manager_id == manager_profile.pk and user.roles.filter(name="Manager").exists()


@transaction.atomic
def decide_leave_request(
    request_id: int, approver: User, *, approve: bool, decision_note: str = ""
) -> LeaveRequest:
    try:
        leave_request = (
            LeaveRequest.objects.select_for_update()
            .select_related("employee", "leave_type")
            .get(pk=request_id, is_deleted=False)
        )
    except LeaveRequest.DoesNotExist as error:
        raise ValidationError({"detail": "Leave request no longer exists."}) from error
    if not manager_can_approve(approver, leave_request.employee):
        raise PermissionDenied("Only HR or the employee's manager can decide this request.")
    if leave_request.status != LeaveRequest.Status.PENDING:
        raise ValidationError({"detail": "Only pending leave requests can be decided."})
    if approve:
        balance = (
            LeaveBalance.objects.select_for_update()
            .filter(
                employee=leave_request.employee,
                leave_type=leave_request.leave_type,
                year=leave_request.start_date.year,
            )
            .first()
        )
        if balance is None or balance.available_days < leave_request.requested_days:
            raise ValidationError({"detail": "Insufficient accrued leave balance."})
        balance.used_days += leave_request.requested_days
        balance.updated_by = approver
        balance.save(update_fields=["used_days", "updated_by", "updated_at"])
        leave_request.status = LeaveRequest.Status.APPROVED
    else:
        leave_request.status = LeaveRequest.Status.REJECTED
    leave_request.approver = approver
    leave_request.decision_note = decision_note
    leave_request.decided_at = timezone.now()
    leave_request.updated_by = approver
    leave_request.save(
        update_fields=[
            "status",
            "approver",
            "decision_note",
            "decided_at",
            "updated_by",
            "updated_at",
        ]
    )
    return leave_request


@transaction.atomic
def accrue_monthly_leave_balances(year: int, month: int) -> int:
    """Accrue annual allowances monthly; unique accrual rows make reruns safe."""
    if month < 1 or month > 12:
        raise ValueError("Month must be between 1 and 12.")
    month_start = date(year, month, 1)
    month_end = date(year, month, calendar.monthrange(year, month)[1])
    profiles = EmployeeProfile.objects.filter(
        is_deleted=False,
        hire_date__lte=month_end,
        employment_status__in=[
            EmployeeProfile.EmploymentStatus.ACTIVE,
            EmployeeProfile.EmploymentStatus.ON_LEAVE,
        ],
    ).filter(Q(termination_date__isnull=True) | Q(termination_date__gte=month_start))
    leave_types = list(LeaveType.objects.filter(is_deleted=False, annual_allowance_days__gt=0))
    applied = 0
    for employee in profiles.iterator():
        for leave_type in leave_types:
            amount = (leave_type.annual_allowance_days / Decimal("12")).quantize(Decimal("0.01"))
            accrual, created = LeaveAccrual.objects.get_or_create(
                employee=employee,
                leave_type=leave_type,
                year=year,
                month=month,
                defaults={"accrued_days": amount},
            )
            if not created:
                continue
            LeaveBalance.objects.get_or_create(
                employee=employee,
                leave_type=leave_type,
                year=year,
            )
            balance = LeaveBalance.objects.select_for_update().get(
                employee=employee, leave_type=leave_type, year=year
            )
            balance.accrued_days += accrual.accrued_days
            balance.save(update_fields=["accrued_days", "updated_at"])
            applied += 1
    return applied
