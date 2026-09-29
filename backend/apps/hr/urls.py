"""Versioned HR API routes."""

from rest_framework.routers import DefaultRouter

from apps.hr.views import (
    AttendanceViewSet,
    DepartmentViewSet,
    DesignationViewSet,
    EmergencyContactViewSet,
    EmployeeDocumentViewSet,
    EmployeeProfileViewSet,
    HolidayViewSet,
    LeaveBalanceViewSet,
    LeaveRequestViewSet,
    LeaveTypeViewSet,
)

router = DefaultRouter()
router.register("departments", DepartmentViewSet, basename="hr-department")
router.register("designations", DesignationViewSet, basename="hr-designation")
router.register("employees", EmployeeProfileViewSet, basename="hr-employee")
router.register("emergency-contacts", EmergencyContactViewSet, basename="hr-emergency-contact")
router.register("employee-documents", EmployeeDocumentViewSet, basename="hr-employee-document")
router.register("attendance", AttendanceViewSet, basename="hr-attendance")
router.register("leave-types", LeaveTypeViewSet, basename="hr-leave-type")
router.register("leave-balances", LeaveBalanceViewSet, basename="hr-leave-balance")
router.register("leave-requests", LeaveRequestViewSet, basename="hr-leave-request")
router.register("holidays", HolidayViewSet, basename="hr-holiday")

urlpatterns = router.urls
