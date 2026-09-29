"""REST endpoints for people operations."""

from calendar import monthrange
from datetime import date
from pathlib import Path
from typing import Any, cast

from django.db import transaction
from django.db.models import Count, Q, QuerySet
from django.http import FileResponse
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from apps.core.models import User
from apps.core.pagination import StandardPagination
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
from apps.hr.permissions import (
    HRReadWritePermission,
    employee_scope,
    has_any_role,
    private_employee_scope,
)
from apps.hr.serializers import (
    AttendanceMonthlySummarySerializer,
    AttendanceSerializer,
    DepartmentSerializer,
    DesignationSerializer,
    EmergencyContactSerializer,
    EmployeeAccountChoiceSerializer,
    EmployeeDocumentSerializer,
    EmployeeProfileSerializer,
    HolidaySerializer,
    LeaveAdjustmentSerializer,
    LeaveBalanceSerializer,
    LeaveDecisionSerializer,
    LeaveRequestSerializer,
    LeaveTypeSerializer,
    OrgChartSerializer,
)
from apps.hr.services import check_in, check_out, decide_leave_request


def request_user(request: Request) -> User:
    return cast(User, request.user)


class DepartmentViewSet(viewsets.ModelViewSet[Department]):
    serializer_class = DepartmentSerializer
    permission_classes = [HRReadWritePermission]
    search_fields = ["name", "code", "description"]
    ordering_fields = ["name", "code", "created_at"]
    filterset_fields = ["code"]

    def get_queryset(self) -> QuerySet[Department]:
        return (
            Department.objects.filter(is_deleted=False)
            .annotate(
                employee_count=Count(
                    "employees",
                    filter=Q(
                        employees__is_deleted=False,
                        employees__employment_status=EmployeeProfile.EmploymentStatus.ACTIVE,
                    ),
                )
            )
            .order_by("name")
            .distinct()
        )

    def perform_destroy(self, instance: Department) -> None:
        if instance.employees.filter(is_deleted=False).exists():
            raise ValidationError({"detail": "Move or terminate department employees first."})
        if instance.designations.filter(is_deleted=False).exists():
            raise ValidationError({"detail": "Delete department designations first."})
        instance.delete()


class DesignationViewSet(viewsets.ModelViewSet[Designation]):
    serializer_class = DesignationSerializer
    permission_classes = [HRReadWritePermission]
    search_fields = ["title", "department__name"]
    ordering_fields = ["title", "created_at"]
    filterset_fields = ["department"]

    def get_queryset(self) -> QuerySet[Designation]:
        return Designation.objects.filter(is_deleted=False).select_related("department")

    def perform_destroy(self, instance: Designation) -> None:
        if instance.employees.filter(is_deleted=False).exists():
            raise ValidationError(
                {"detail": "A designation assigned to employees cannot be deleted."}
            )
        instance.delete()


class EmployeeProfileViewSet(viewsets.ModelViewSet[EmployeeProfile]):
    serializer_class = EmployeeProfileSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["department", "designation", "manager", "employment_status"]
    search_fields = [
        "employee_number",
        "user__email",
        "user__first_name",
        "user__last_name",
        "department__name",
        "designation__title",
    ]
    ordering_fields = ["employee_number", "hire_date", "user__first_name", "user__last_name"]

    def get_queryset(self) -> QuerySet[EmployeeProfile]:
        return (
            employee_scope(request_user(self.request))
            .filter(is_deleted=False)
            .select_related("user", "department", "designation", "manager__user")
            .prefetch_related("documents", "emergency_contacts")
        )

    def get_permissions(self) -> list[BasePermission]:
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [HRReadWritePermission()]
        return cast(list[BasePermission], super().get_permissions())

    def perform_destroy(self, instance: EmployeeProfile) -> None:
        raise ValidationError(
            {
                "detail": (
                    "Employee profiles are retained for audit. Set employment_status to terminated."
                )
            }
        )

    @action(detail=False, methods=["get"], url_path="eligible-users")
    def eligible_users(self, request: Request) -> Response:
        if not has_any_role(request_user(request), "Admin", "HR"):
            raise PermissionDenied("Only HR or Admin can select employee accounts.")
        accounts = User.objects.filter(
            is_active=True,
            is_deleted=False,
            employee_profile__isnull=True,
            roles__name="Employee",
        ).distinct()
        query = request.query_params.get("search", "").strip()
        if query:
            accounts = accounts.filter(
                Q(email__icontains=query)
                | Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
            )
        accounts = accounts.order_by("email")
        paginator = StandardPagination()
        page = paginator.paginate_queryset(cast(Any, accounts), request, view=self)
        serialized = EmployeeAccountChoiceSerializer(
            cast(Any, page if page is not None else accounts), many=True
        )
        return paginator.get_paginated_response(serialized.data)

    @action(detail=False, methods=["get"], url_path="org-chart")
    def org_chart(self, request: Request) -> Response:
        profiles = self.filter_queryset(self.get_queryset()).filter(
            employment_status__in=[
                EmployeeProfile.EmploymentStatus.ACTIVE,
                EmployeeProfile.EmploymentStatus.ON_LEAVE,
            ]
        )
        page = self.paginate_queryset(profiles)
        serializer = OrgChartSerializer(page or profiles, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


class EmergencyContactViewSet(viewsets.ModelViewSet[EmergencyContact]):
    serializer_class = EmergencyContactSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["employee", "is_primary"]
    search_fields = ["name", "relationship", "employee__employee_number"]
    ordering_fields = ["name", "created_at"]

    def get_queryset(self) -> QuerySet[EmergencyContact]:
        return EmergencyContact.objects.filter(
            is_deleted=False, employee__in=private_employee_scope(request_user(self.request))
        ).select_related("employee", "employee__user")

    def perform_create(self, serializer: BaseSerializer[EmergencyContact]) -> None:
        employee = serializer.validated_data["employee"]
        if not private_employee_scope(request_user(self.request)).filter(pk=employee.pk).exists():
            raise PermissionDenied("You cannot manage contacts for this employee.")
        actor = request_user(self.request)
        serializer.save(created_by=actor, updated_by=actor)

    def perform_update(self, serializer: BaseSerializer[EmergencyContact]) -> None:
        if serializer.instance is None:
            raise ValidationError("An emergency contact is required for this update.")
        employee = serializer.validated_data.get("employee", serializer.instance.employee)
        if not private_employee_scope(request_user(self.request)).filter(pk=employee.pk).exists():
            raise PermissionDenied("You cannot manage contacts for this employee.")
        serializer.save(updated_by=request_user(self.request))

    def perform_destroy(self, instance: EmergencyContact) -> None:
        instance.delete()


class EmployeeDocumentViewSet(viewsets.ModelViewSet[EmployeeDocument]):
    serializer_class = EmployeeDocumentSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["employee", "document_type", "expires_on"]
    search_fields = ["title", "document_type", "employee__employee_number"]
    ordering_fields = ["created_at", "expires_on", "title"]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self) -> QuerySet[EmployeeDocument]:
        return EmployeeDocument.objects.filter(
            is_deleted=False, employee__in=private_employee_scope(request_user(self.request))
        ).select_related("employee", "employee__user")

    def perform_create(self, serializer: BaseSerializer[EmployeeDocument]) -> None:
        employee = serializer.validated_data["employee"]
        if not private_employee_scope(request_user(self.request)).filter(pk=employee.pk).exists():
            raise PermissionDenied("You cannot upload documents for this employee.")
        actor = request_user(self.request)
        serializer.save(created_by=actor, updated_by=actor)

    def perform_destroy(self, instance: EmployeeDocument) -> None:
        instance.delete()

    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request: Request, pk: str | None = None) -> FileResponse:
        document = self.get_object()
        return FileResponse(
            document.file.open("rb"),
            as_attachment=True,
            filename=Path(document.file.name).name,
        )


class AttendanceViewSet(mixins.ListModelMixin, viewsets.GenericViewSet[Attendance]):
    serializer_class = AttendanceSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["employee", "date", "is_late", "left_early"]
    search_fields = [
        "employee__employee_number",
        "employee__user__first_name",
        "employee__user__last_name",
    ]
    ordering_fields = ["date", "check_in", "check_out"]

    def get_queryset(self) -> QuerySet[Attendance]:
        return Attendance.objects.filter(
            is_deleted=False, employee__in=employee_scope(request_user(self.request))
        ).select_related("employee", "employee__user")

    @extend_schema(request=None, responses=AttendanceSerializer)
    @action(detail=False, methods=["post"], url_path="check-in")
    def check_in_today(self, request: Request) -> Response:
        employee = self._current_employee()
        record = check_in(employee)
        return Response(self.get_serializer(record).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses=AttendanceSerializer)
    @action(detail=False, methods=["post"], url_path="check-out")
    def check_out_today(self, request: Request) -> Response:
        employee = self._current_employee()
        record = check_out(employee)
        return Response(self.get_serializer(record).data)

    @action(detail=False, methods=["get"], url_path="monthly-summary")
    @extend_schema(
        parameters=[
            OpenApiParameter(name="year", type=int, required=False),
            OpenApiParameter(name="month", type=int, required=False),
        ],
        responses=AttendanceMonthlySummarySerializer(many=True),
    )
    def monthly_summary(self, request: Request) -> Response:
        today = timezone.localdate()
        try:
            year = int(request.query_params.get("year", today.year))
            month = int(request.query_params.get("month", today.month))
        except ValueError as error:
            raise ValidationError({"month": "Year and month must be whole numbers."}) from error
        if year < 1 or year >= 9999 or month < 1 or month > 12:
            raise ValidationError({"month": "Choose a valid year and month."})
        start = date(year, month, 1)
        end = date(year + int(month == 12), month % 12 + 1, 1)
        rows = list(
            self.get_queryset()
            .filter(date__gte=start, date__lt=end)
            .values(
                "employee_id",
                "employee__employee_number",
                "employee__user__first_name",
                "employee__user__last_name",
                "employee__user__email",
            )
            .annotate(
                days_present=Count("id"),
                late_days=Count("id", filter=Q(is_late=True)),
                early_departure_days=Count("id", filter=Q(left_early=True)),
            )
            .order_by("employee__employee_number")
        )
        records = [
            {
                "employee_id": row["employee_id"],
                "employee_number": row["employee__employee_number"],
                "employee_name": (
                    " ".join(
                        name
                        for name in (
                            row["employee__user__first_name"],
                            row["employee__user__last_name"],
                        )
                        if name
                    )
                    or row["employee__user__email"]
                ),
                "days_present": row["days_present"],
                "late_days": row["late_days"],
                "early_departure_days": row["early_departure_days"],
            }
            for row in rows
        ]
        paginator = self.paginator
        if paginator is None:
            return Response([AttendanceMonthlySummarySerializer(row).data for row in records])
        page = paginator.paginate_queryset(cast(Any, records), request, view=self)
        serialized_page = [
            AttendanceMonthlySummarySerializer(cast(Any, row)).data for row in (page or records)
        ]
        return paginator.get_paginated_response(serialized_page)

    def _current_employee(self) -> EmployeeProfile:
        employee = EmployeeProfile.objects.filter(user=request_user(self.request)).first()
        if employee is None:
            raise PermissionDenied("An employee profile is required for attendance.")
        return employee


class LeaveTypeViewSet(viewsets.ModelViewSet[LeaveType]):
    serializer_class = LeaveTypeSerializer
    permission_classes = [HRReadWritePermission]
    search_fields = ["name"]
    ordering_fields = ["name", "annual_allowance_days"]

    def get_queryset(self) -> QuerySet[LeaveType]:
        return LeaveType.objects.filter(is_deleted=False)

    def perform_destroy(self, instance: LeaveType) -> None:
        if (
            instance.requests.filter(is_deleted=False).exists()
            or instance.balances.filter(is_deleted=False).exists()
        ):
            raise ValidationError(
                {"detail": "A leave type with requests or balances cannot be deleted."}
            )
        instance.delete()


class LeaveBalanceViewSet(mixins.ListModelMixin, viewsets.GenericViewSet[LeaveBalance]):
    serializer_class = LeaveBalanceSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["employee", "leave_type", "year"]
    search_fields = ["employee__employee_number", "employee__user__first_name", "leave_type__name"]
    ordering_fields = ["year", "accrued_days", "used_days"]

    def get_queryset(self) -> QuerySet[LeaveBalance]:
        return LeaveBalance.objects.filter(
            is_deleted=False, employee__in=employee_scope(request_user(self.request))
        ).select_related("employee", "employee__user", "leave_type")

    @action(detail=True, methods=["post"], url_path="adjust")
    @extend_schema(request=LeaveAdjustmentSerializer, responses=LeaveBalanceSerializer)
    @transaction.atomic
    def adjust(self, request: Request, pk: str | None = None) -> Response:
        if not has_any_role(request_user(request), "Admin", "HR"):
            raise PermissionDenied("Only HR or Admin can adjust leave balances.")
        adjustment = LeaveAdjustmentSerializer(data=request.data)
        adjustment.is_valid(raise_exception=True)
        if pk is None:
            raise ValidationError({"detail": "A leave balance identifier is required."})
        balance = self.get_queryset().select_for_update().get(pk=pk)
        updated_adjustment = balance.adjustment_days + adjustment.validated_data["amount"]
        if balance.accrued_days + updated_adjustment - balance.used_days < 0:
            raise ValidationError(
                {"amount": "An adjustment cannot reduce the available balance below zero."}
            )
        balance.adjustment_days = updated_adjustment
        balance.updated_by = request_user(request)
        balance.save(update_fields=["adjustment_days", "updated_by", "updated_at"])
        return Response(self.get_serializer(balance).data)


class LeaveRequestViewSet(viewsets.ModelViewSet[LeaveRequest]):
    serializer_class = LeaveRequestSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "delete", "head", "options"]
    filterset_fields = ["employee", "leave_type", "status", "start_date", "end_date"]
    search_fields = ["employee__employee_number", "employee__user__first_name", "reason"]
    ordering_fields = ["created_at", "start_date", "end_date", "status"]

    def get_queryset(self) -> QuerySet[LeaveRequest]:
        return LeaveRequest.objects.filter(
            is_deleted=False, employee__in=employee_scope(request_user(self.request))
        ).select_related("employee", "employee__user", "leave_type", "approver")

    def perform_destroy(self, instance: LeaveRequest) -> None:
        if instance.employee.user_id != request_user(self.request).pk:
            raise PermissionDenied("Employees can only cancel their own leave requests.")
        if instance.status != LeaveRequest.Status.PENDING:
            raise ValidationError({"detail": "Only pending requests can be cancelled."})
        instance.status = LeaveRequest.Status.CANCELLED
        instance.updated_by = request_user(self.request)
        instance.save(update_fields=["status", "updated_by", "updated_at"])

    @action(detail=True, methods=["post"], url_path="approve")
    @extend_schema(request=LeaveDecisionSerializer, responses=LeaveRequestSerializer)
    def approve(self, request: Request, pk: str | None = None) -> Response:
        leave_request = self.get_object()
        decision = LeaveDecisionSerializer(data=request.data)
        decision.is_valid(raise_exception=True)
        updated = decide_leave_request(
            leave_request.pk,
            request_user(request),
            approve=True,
            decision_note=decision.validated_data.get("decision_note", ""),
        )
        return Response(self.get_serializer(updated).data)

    @action(detail=True, methods=["post"], url_path="reject")
    @extend_schema(request=LeaveDecisionSerializer, responses=LeaveRequestSerializer)
    def reject(self, request: Request, pk: str | None = None) -> Response:
        leave_request = self.get_object()
        decision = LeaveDecisionSerializer(data=request.data)
        decision.is_valid(raise_exception=True)
        updated = decide_leave_request(
            leave_request.pk,
            request_user(request),
            approve=False,
            decision_note=decision.validated_data.get("decision_note", ""),
        )
        return Response(self.get_serializer(updated).data)

    @action(detail=False, methods=["get"], url_path="calendar")
    @extend_schema(
        parameters=[
            OpenApiParameter(name="year", type=int, required=False),
            OpenApiParameter(name="month", type=int, required=False),
        ]
    )
    def calendar(self, request: Request) -> Response:
        today = timezone.localdate()
        try:
            year = int(request.query_params.get("year", today.year))
            month = int(request.query_params.get("month", today.month))
        except ValueError as error:
            raise ValidationError({"month": "Year and month must be whole numbers."}) from error
        if year < 1 or year >= 9999 or month < 1 or month > 12:
            raise ValidationError({"month": "Choose a valid year and month."})
        start = date(year, month, 1)
        end = date(year, month, monthrange(year, month)[1])
        requests = self.filter_queryset(self.get_queryset()).filter(
            status__in=[LeaveRequest.Status.PENDING, LeaveRequest.Status.APPROVED],
            start_date__lte=end,
            end_date__gte=start,
        )
        page = self.paginate_queryset(requests)
        serializer = self.get_serializer(page or requests, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


class HolidayViewSet(viewsets.ModelViewSet[Holiday]):
    serializer_class = HolidaySerializer
    permission_classes = [HRReadWritePermission]
    filterset_fields = ["date", "is_recurring"]
    search_fields = ["name", "description"]
    ordering_fields = ["date", "name"]

    def get_queryset(self) -> QuerySet[Holiday]:
        return Holiday.objects.filter(is_deleted=False)

    def perform_destroy(self, instance: Holiday) -> None:
        instance.delete()
