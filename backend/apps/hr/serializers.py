"""Validated API representations for HR records."""

from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Sum
from rest_framework import serializers

from apps.core.models import User
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
    validate_employee_document,
)
from apps.hr.services import business_days


class DepartmentSerializer(serializers.ModelSerializer[Department]):
    employee_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Department
        fields = ["id", "name", "code", "description", "employee_count", "created_at", "updated_at"]
        read_only_fields = ["id", "employee_count", "created_at", "updated_at"]


class DesignationSerializer(serializers.ModelSerializer[Designation]):
    class Meta:
        model = Designation
        fields = ["id", "title", "department", "description", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class EmployeeProfileSerializer(serializers.ModelSerializer[EmployeeProfile]):
    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True, is_deleted=False)
    )
    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.filter(is_deleted=False)
    )
    designation = serializers.PrimaryKeyRelatedField(
        queryset=Designation.objects.filter(is_deleted=False, department__is_deleted=False)
    )
    manager = serializers.PrimaryKeyRelatedField(
        queryset=EmployeeProfile.objects.filter(
            is_deleted=False,
            employment_status__in=[
                EmployeeProfile.EmploymentStatus.ACTIVE,
                EmployeeProfile.EmploymentStatus.ON_LEAVE,
            ],
        ),
        allow_null=True,
        required=False,
    )
    email = serializers.EmailField(source="user.email", read_only=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    full_name = serializers.CharField(source="user.get_full_name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    designation_title = serializers.CharField(source="designation.title", read_only=True)
    manager_name = serializers.CharField(
        source="manager.user.get_full_name", read_only=True, allow_null=True
    )

    class Meta:
        model = EmployeeProfile
        fields = [
            "id",
            "user",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "employee_number",
            "department",
            "department_name",
            "designation",
            "designation_title",
            "manager",
            "manager_name",
            "phone",
            "date_of_birth",
            "hire_date",
            "termination_date",
            "employment_status",
            "location",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        instance = self.instance
        status = attrs.get(
            "employment_status",
            instance.employment_status
            if instance is not None
            else EmployeeProfile.EmploymentStatus.ACTIVE,
        )
        termination_date = attrs.get(
            "termination_date", instance.termination_date if instance is not None else None
        )
        hire_date = attrs.get("hire_date", instance.hire_date if instance is not None else None)
        if status == EmployeeProfile.EmploymentStatus.TERMINATED and not termination_date:
            raise serializers.ValidationError(
                {"termination_date": "A termination date is required for terminated employees."}
            )
        if termination_date and hire_date and termination_date < hire_date:
            raise serializers.ValidationError(
                {"termination_date": "Termination cannot predate the hire date."}
            )
        manager = attrs.get("manager", instance.manager if instance is not None else None)
        visited: set[int] = set()
        while manager is not None:
            if instance is not None and manager.pk == instance.pk:
                raise serializers.ValidationError(
                    {"manager": "Reporting relationships cannot contain a cycle."}
                )
            if manager.pk in visited:
                raise serializers.ValidationError(
                    {"manager": "The selected manager already has a reporting cycle."}
                )
            visited.add(manager.pk)
            manager = manager.manager
        return attrs


class OrgChartSerializer(serializers.ModelSerializer[EmployeeProfile]):
    full_name = serializers.CharField(source="user.get_full_name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    designation = serializers.CharField(source="designation.title", read_only=True)
    department = serializers.CharField(source="department.name", read_only=True)
    manager_name = serializers.CharField(
        source="manager.user.get_full_name", read_only=True, allow_null=True
    )

    class Meta:
        model = EmployeeProfile
        fields = [
            "id",
            "employee_number",
            "full_name",
            "email",
            "designation",
            "department",
            "manager",
            "manager_name",
            "employment_status",
        ]


class EmployeeAccountChoiceSerializer(serializers.ModelSerializer[User]):
    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name"]


class EmergencyContactSerializer(serializers.ModelSerializer[EmergencyContact]):
    class Meta:
        model = EmergencyContact
        fields = [
            "id",
            "employee",
            "name",
            "relationship",
            "phone",
            "email",
            "is_primary",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class EmployeeDocumentSerializer(serializers.ModelSerializer[EmployeeDocument]):
    file_name = serializers.CharField(source="file.name", read_only=True)
    file = serializers.FileField(write_only=True, validators=[validate_employee_document])

    class Meta:
        model = EmployeeDocument
        fields = [
            "id",
            "employee",
            "title",
            "document_type",
            "file",
            "file_name",
            "expires_on",
            "created_at",
        ]
        read_only_fields = ["id", "file_name", "created_at"]


class AttendanceSerializer(serializers.ModelSerializer[Attendance]):
    employee_number = serializers.CharField(source="employee.employee_number", read_only=True)
    employee_name = serializers.CharField(source="employee.user.get_full_name", read_only=True)

    class Meta:
        model = Attendance
        fields = [
            "id",
            "employee",
            "employee_number",
            "employee_name",
            "date",
            "check_in",
            "check_out",
            "is_late",
            "left_early",
            "notes",
        ]
        read_only_fields = fields


class AttendanceMonthlySummarySerializer(serializers.Serializer[dict[str, Any]]):
    employee_id = serializers.IntegerField()
    employee_number = serializers.CharField()
    employee_name = serializers.CharField()
    days_present = serializers.IntegerField()
    late_days = serializers.IntegerField()
    early_departure_days = serializers.IntegerField()


class LeaveTypeSerializer(serializers.ModelSerializer[LeaveType]):
    class Meta:
        model = LeaveType
        fields = [
            "id",
            "name",
            "annual_allowance_days",
            "is_paid",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class LeaveBalanceSerializer(serializers.ModelSerializer[LeaveBalance]):
    available_days = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True)
    employee_number = serializers.CharField(source="employee.employee_number", read_only=True)
    leave_type_name = serializers.CharField(source="leave_type.name", read_only=True)

    class Meta:
        model = LeaveBalance
        fields = [
            "id",
            "employee",
            "employee_number",
            "leave_type",
            "leave_type_name",
            "year",
            "accrued_days",
            "adjustment_days",
            "used_days",
            "available_days",
        ]
        read_only_fields = fields


class LeaveRequestSerializer(serializers.ModelSerializer[LeaveRequest]):
    leave_type = serializers.PrimaryKeyRelatedField(
        queryset=LeaveType.objects.filter(is_deleted=False)
    )
    employee_number = serializers.CharField(source="employee.employee_number", read_only=True)
    employee_name = serializers.CharField(source="employee.user.get_full_name", read_only=True)
    leave_type_name = serializers.CharField(source="leave_type.name", read_only=True)
    approver_name = serializers.CharField(
        source="approver.get_full_name", read_only=True, allow_null=True
    )
    decision_note = serializers.CharField(read_only=True)
    requested_days = serializers.DecimalField(max_digits=6, decimal_places=2, read_only=True)

    class Meta:
        model = LeaveRequest
        fields = [
            "id",
            "employee",
            "employee_number",
            "employee_name",
            "leave_type",
            "leave_type_name",
            "start_date",
            "end_date",
            "requested_days",
            "reason",
            "status",
            "approver",
            "approver_name",
            "decision_note",
            "decided_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "employee",
            "requested_days",
            "status",
            "approver",
            "approver_name",
            "decision_note",
            "decided_at",
            "created_at",
        ]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        start_date = attrs.get("start_date")
        end_date = attrs.get("end_date")
        if start_date is None or end_date is None:
            return attrs
        if end_date < start_date:
            raise serializers.ValidationError(
                {"end_date": "End date must be on or after the start date."}
            )
        if start_date.year != end_date.year:
            raise serializers.ValidationError(
                {"end_date": "A leave request must stay within one calendar year."}
            )
        employee = EmployeeProfile.objects.filter(user=self.context["request"].user).first()
        if employee is None:
            raise serializers.ValidationError(
                {"employee": "An employee profile is required to request leave."}
            )
        if employee.employment_status == EmployeeProfile.EmploymentStatus.TERMINATED:
            raise serializers.ValidationError(
                {"employee": "Terminated employees cannot request leave."}
            )
        if start_date < employee.hire_date:
            raise serializers.ValidationError(
                {"start_date": "Leave cannot begin before the employee's hire date."}
            )
        leave_type = attrs.get("leave_type")
        if leave_type is None:
            return attrs
        days = business_days(start_date, end_date)
        if days < 1:
            raise serializers.ValidationError(
                {"start_date": "The selected dates contain no working days."}
            )
        attrs["requested_days"] = Decimal(days)
        overlapping = LeaveRequest.objects.filter(
            employee=employee,
            status__in=[LeaveRequest.Status.PENDING, LeaveRequest.Status.APPROVED],
            start_date__lte=end_date,
            end_date__gte=start_date,
            is_deleted=False,
        )
        if overlapping.exists():
            raise serializers.ValidationError(
                {"start_date": "This request overlaps another pending or approved request."}
            )
        balance = LeaveBalance.objects.filter(
            employee=employee, leave_type=leave_type, year=start_date.year
        ).first()
        if balance is None:
            raise serializers.ValidationError(
                {"leave_type": "No leave balance exists for this leave type and year."}
            )
        pending_days = LeaveRequest.objects.filter(
            employee=employee,
            leave_type=leave_type,
            start_date__year=start_date.year,
            status=LeaveRequest.Status.PENDING,
            is_deleted=False,
        ).aggregate(total=Sum("requested_days"))["total"] or Decimal("0.00")
        if balance.available_days - pending_days < days:
            raise serializers.ValidationError(
                {"leave_type": "The requested days exceed the available leave balance."}
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data: dict[str, Any]) -> LeaveRequest:
        request = self.context["request"]
        employee = EmployeeProfile.objects.get(user=request.user)
        balance = (
            LeaveBalance.objects.select_for_update()
            .filter(
                employee=employee,
                leave_type=validated_data["leave_type"],
                year=validated_data["start_date"].year,
            )
            .first()
        )
        pending_days = LeaveRequest.objects.filter(
            employee=employee,
            leave_type=validated_data["leave_type"],
            start_date__year=validated_data["start_date"].year,
            status=LeaveRequest.Status.PENDING,
            is_deleted=False,
        ).aggregate(total=Sum("requested_days"))["total"] or Decimal("0.00")
        if (
            balance is None
            or balance.available_days - pending_days < validated_data["requested_days"]
        ):
            raise serializers.ValidationError(
                {"leave_type": "The requested days exceed the available leave balance."}
            )
        overlap = LeaveRequest.objects.filter(
            employee=employee,
            status__in=[LeaveRequest.Status.PENDING, LeaveRequest.Status.APPROVED],
            start_date__lte=validated_data["end_date"],
            end_date__gte=validated_data["start_date"],
            is_deleted=False,
        ).exists()
        if overlap:
            raise serializers.ValidationError(
                {"start_date": "This request overlaps another pending or approved request."}
            )
        validated_data["created_by"] = request.user
        validated_data["updated_by"] = request.user
        return super().create({**validated_data, "employee": employee})


class LeaveDecisionSerializer(serializers.Serializer[dict[str, Any]]):
    decision_note = serializers.CharField(required=False, allow_blank=True, max_length=1000)


class LeaveAdjustmentSerializer(serializers.Serializer[dict[str, Any]]):
    amount = serializers.DecimalField(max_digits=7, decimal_places=2)


class HolidaySerializer(serializers.ModelSerializer[Holiday]):
    class Meta:
        model = Holiday
        fields = [
            "id",
            "name",
            "date",
            "description",
            "is_recurring",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
