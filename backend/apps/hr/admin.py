"""Django admin configuration for people operations."""

from django.contrib import admin

from apps.hr.models import (
    Attendance,
    Department,
    Designation,
    EmergencyContact,
    EmployeeDocument,
    EmployeeProfile,
    Holiday,
    LeaveBalance,
    LeaveRequest,
    LeaveType,
)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["name", "code"]
    search_fields = ["name", "code"]


@admin.register(Designation)
class DesignationAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["title", "department"]
    list_filter = ["department"]
    search_fields = ["title", "department__name"]


@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = [
        "employee_number",
        "user",
        "department",
        "designation",
        "manager",
        "employment_status",
    ]
    list_filter = ["department", "employment_status"]
    search_fields = ["employee_number", "user__email", "user__first_name", "user__last_name"]
    autocomplete_fields = ["user", "manager"]


@admin.register(EmergencyContact)
class EmergencyContactAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["name", "employee", "relationship", "phone", "is_primary"]
    list_filter = ["is_primary"]
    search_fields = ["name", "employee__employee_number"]


@admin.register(EmployeeDocument)
class EmployeeDocumentAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["title", "employee", "document_type", "expires_on"]
    list_filter = ["document_type"]
    search_fields = ["title", "employee__employee_number"]


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["employee", "date", "check_in", "check_out", "is_late", "left_early"]
    list_filter = ["date", "is_late", "left_early"]
    search_fields = ["employee__employee_number", "employee__user__email"]


@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["name", "annual_allowance_days", "is_paid"]


@admin.register(LeaveBalance)
class LeaveBalanceAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = [
        "employee",
        "leave_type",
        "year",
        "accrued_days",
        "adjustment_days",
        "used_days",
    ]
    list_filter = ["year", "leave_type"]
    search_fields = ["employee__employee_number"]


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["employee", "leave_type", "start_date", "end_date", "status", "approver"]
    list_filter = ["status", "leave_type"]
    search_fields = ["employee__employee_number", "employee__user__email"]


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["name", "date", "is_recurring"]
    list_filter = ["is_recurring", "date"]
    search_fields = ["name"]
