"""Permission, workflow, validation, and auditing tests for HR."""

from datetime import date, datetime
from decimal import Decimal
from tempfile import TemporaryDirectory

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError as APIValidationError
from rest_framework.test import APITestCase

from apps.core.models import AuditLog, CompanySetting, Role, User
from apps.hr.models import (
    Attendance,
    Department,
    Designation,
    EmployeeDocument,
    EmployeeProfile,
    Holiday,
    LeaveBalance,
    LeaveRequest,
    LeaveType,
)
from apps.hr.services import (
    accrue_monthly_leave_balances,
    business_days,
    check_in,
    check_out,
)


class HRApiTests(APITestCase):
    def setUp(self) -> None:
        self.admin = User.objects.create_user(
            email="admin@hr.test", password="Strong-Password-123!"
        )
        self.hr_user = User.objects.create_user(email="hr@hr.test", password="Strong-Password-123!")
        self.manager_user = User.objects.create_user(
            email="manager@hr.test", password="Strong-Password-123!"
        )
        self.employee_user = User.objects.create_user(
            email="employee@hr.test", password="Strong-Password-123!"
        )
        self.outsider_user = User.objects.create_user(
            email="outsider@hr.test", password="Strong-Password-123!"
        )
        for name in ("Admin", "HR", "Manager", "Employee"):
            Role.objects.get_or_create(name=name)
        self.admin.roles.add(Role.objects.get(name="Admin"))
        self.hr_user.roles.add(Role.objects.get(name="HR"))
        self.manager_user.roles.add(Role.objects.get(name="Manager"))
        self.employee_user.roles.add(Role.objects.get(name="Employee"))
        self.outsider_user.roles.add(Role.objects.get(name="Employee"))

        self.department = Department.objects.create(name="Engineering", code="ENG")
        self.designation = Designation.objects.create(
            title="Software Engineer", department=self.department
        )
        self.manager = EmployeeProfile.objects.create(
            user=self.manager_user,
            employee_number="E-100",
            department=self.department,
            designation=self.designation,
            hire_date=date(2020, 1, 1),
        )
        self.employee = EmployeeProfile.objects.create(
            user=self.employee_user,
            employee_number="E-101",
            department=self.department,
            designation=self.designation,
            manager=self.manager,
            hire_date=date(2021, 1, 1),
        )
        self.outsider = EmployeeProfile.objects.create(
            user=self.outsider_user,
            employee_number="E-102",
            department=self.department,
            designation=self.designation,
            hire_date=date(2021, 1, 1),
        )
        self.leave_type = LeaveType.objects.create(
            name="Annual leave", annual_allowance_days=Decimal("24.00")
        )
        self.balance = LeaveBalance.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            year=2026,
            accrued_days=Decimal("20.00"),
        )
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)

    def authenticate(self, user: User) -> None:
        self.client.force_authenticate(user)

    def test_hr_lists_require_auth_and_writes_require_hr_or_admin(self) -> None:
        self.assertEqual(self.client.get("/api/v1/hr/departments/").status_code, 401)
        self.authenticate(self.employee_user)
        self.assertEqual(self.client.get("/api/v1/hr/departments/").status_code, 200)
        self.assertEqual(
            self.client.post(
                "/api/v1/hr/departments/",
                {"name": "Finance", "code": "FIN"},
                format="json",
            ).status_code,
            403,
        )
        self.authenticate(self.hr_user)
        response = self.client.post(
            "/api/v1/hr/departments/",
            {"name": "Finance", "code": "FIN", "description": "Business operations"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(
            AuditLog.objects.filter(
                model_label="hr.Department",
                object_id=str(response.data["id"]),
                action="create",
            ).exists()
        )
        client_user = User.objects.create(email="client@hr.test", password="unused-test-password")
        Role.objects.get_or_create(name="Client")
        client_user.roles.add(Role.objects.get(name="Client"))
        self.authenticate(client_user)
        self.assertEqual(self.client.get("/api/v1/hr/departments/").status_code, 403)

    def test_department_deletion_is_blocked_when_designations_or_employees_exist(self) -> None:
        self.authenticate(self.hr_user)
        response = self.client.delete(f"/api/v1/hr/departments/{self.department.pk}/")
        self.assertEqual(response.status_code, 400)
        self.assertTrue(Department.objects.filter(pk=self.department.pk).exists())

    def test_employee_directory_is_scoped_to_self_and_direct_reports(self) -> None:
        self.authenticate(self.manager_user)
        response = self.client.get("/api/v1/hr/employees/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        self.authenticate(self.employee_user)
        response = self.client.get("/api/v1/hr/employees/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.authenticate(self.hr_user)
        self.assertEqual(self.client.get("/api/v1/hr/employees/").data["count"], 3)

    def test_employee_profile_create_and_reporting_cycle_validation(self) -> None:
        new_user = User.objects.create_user(
            email="new-person@hr.test", password="Strong-Password-123!"
        )
        new_user.roles.add(Role.objects.get(name="Employee"))
        self.authenticate(self.hr_user)
        eligible = self.client.get("/api/v1/hr/employees/eligible-users/")
        self.assertEqual(eligible.status_code, 200)
        self.assertEqual([user["email"] for user in eligible.data["results"]], [new_user.email])
        self.authenticate(self.employee_user)
        self.assertEqual(self.client.get("/api/v1/hr/employees/eligible-users/").status_code, 403)
        self.authenticate(self.hr_user)
        response = self.client.post(
            "/api/v1/hr/employees/",
            {
                "user": new_user.pk,
                "employee_number": "E-103",
                "department": self.department.pk,
                "designation": self.designation.pk,
                "manager": self.manager.pk,
                "hire_date": "2026-01-01",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self.client.get("/api/v1/hr/employees/eligible-users/").data["count"], 0)
        manager_cycle = self.client.patch(
            f"/api/v1/hr/employees/{self.manager.pk}/",
            {"manager": self.employee.pk},
            format="json",
        )
        self.assertEqual(manager_cycle.status_code, 400)
        self.assertIn("cycle", str(manager_cycle.data).lower())

    def test_org_chart_is_scoped_and_paginated(self) -> None:
        self.authenticate(self.manager_user)
        response = self.client.get("/api/v1/hr/employees/org-chart/?page_size=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertIn("full_name", response.data["results"][0])

    def test_employee_can_manage_own_emergency_contacts_only(self) -> None:
        self.authenticate(self.employee_user)
        response = self.client.post(
            "/api/v1/hr/emergency-contacts/",
            {
                "employee": self.employee.pk,
                "name": "Alex Example",
                "relationship": "Sibling",
                "phone": "+15551234567",
                "email": "alex@example.test",
                "is_primary": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self.client.get("/api/v1/hr/emergency-contacts/").data["count"], 1)
        unauthorized = self.client.post(
            "/api/v1/hr/emergency-contacts/",
            {
                "employee": self.outsider.pk,
                "name": "Other Contact",
                "relationship": "Friend",
                "phone": "+15557654321",
            },
            format="json",
        )
        self.assertEqual(unauthorized.status_code, 403)
        self.authenticate(self.manager_user)
        scoped = self.client.get(f"/api/v1/hr/emergency-contacts/?employee={self.employee.pk}")
        self.assertEqual(scoped.data["count"], 0)

    def test_employee_document_upload_download_and_scope(self) -> None:
        self.authenticate(self.employee_user)
        with override_settings(MEDIA_ROOT=self.media.name):
            uploaded = SimpleUploadedFile("identity.pdf", b"%PDF-1.7 test-document")
            response = self.client.post(
                "/api/v1/hr/employee-documents/",
                {
                    "employee": self.employee.pk,
                    "title": "Identity document",
                    "document_type": "identity",
                    "file": uploaded,
                },
                format="multipart",
            )
            self.assertEqual(response.status_code, 201, response.data)
            document_id = response.data["id"]
            download = self.client.get(f"/api/v1/hr/employee-documents/{document_id}/download/")
            self.assertEqual(download.status_code, 200)
            self.assertIn("attachment", download["Content-Disposition"])
            download.close()

            invalid = self.client.post(
                "/api/v1/hr/employee-documents/",
                {
                    "employee": self.employee.pk,
                    "title": "Bad file",
                    "document_type": "identity",
                    "file": SimpleUploadedFile("bad.pdf", b"not a PDF"),
                },
                format="multipart",
            )
            self.assertEqual(invalid.status_code, 400)
            self.authenticate(self.outsider_user)
            self.assertEqual(
                self.client.get(
                    f"/api/v1/hr/employee-documents/{document_id}/download/"
                ).status_code,
                404,
            )
            self.authenticate(self.manager_user)
            self.assertEqual(
                self.client.get(
                    f"/api/v1/hr/employee-documents/{document_id}/download/"
                ).status_code,
                404,
            )

    def test_employee_document_size_limit_and_empty_upload(self) -> None:
        empty = EmployeeDocument(
            employee=self.employee,
            title="Empty document",
            document_type="other",
            file=SimpleUploadedFile("empty.pdf", b""),
        )
        with self.assertRaises(DjangoValidationError):
            empty.full_clean()
        oversized = EmployeeDocument(
            employee=self.employee,
            title="Large document",
            document_type="other",
            file=SimpleUploadedFile("large.pdf", b"%PDF-" + b"x" * (10 * 1024 * 1024)),
        )
        with self.assertRaises(DjangoValidationError):
            oversized.full_clean()

    def test_attendance_check_in_out_flags_and_duplicate_protection(self) -> None:
        start = timezone.make_aware(datetime(2026, 6, 10, 10, 0))
        end = timezone.make_aware(datetime(2026, 6, 10, 16, 0))
        CompanySetting.objects.update_or_create(key="workday_start", defaults={"value": "09:00"})
        CompanySetting.objects.update_or_create(key="workday_end", defaults={"value": "17:00"})
        record = check_in(self.employee, start)
        self.assertTrue(record.is_late)
        with self.assertRaises(APIValidationError):
            check_in(self.employee, start)
        record = check_out(self.employee, end)
        self.assertTrue(record.left_early)
        with self.assertRaises(APIValidationError):
            check_out(self.employee, end)

    def test_attendance_api_is_self_scoped_and_requires_check_in_before_checkout(self) -> None:
        self.authenticate(self.employee_user)
        self.assertEqual(self.client.post("/api/v1/hr/attendance/check-out/").status_code, 400)
        check_in(self.employee)
        self.assertEqual(self.client.post("/api/v1/hr/attendance/check-in/").status_code, 400)
        self.authenticate(self.outsider_user)
        self.assertEqual(self.client.get("/api/v1/hr/attendance/").data["count"], 0)

    def test_monthly_attendance_summary_and_invalid_period(self) -> None:
        Attendance.objects.create(
            employee=self.employee,
            date=date(2026, 7, 6),
            is_late=True,
            left_early=False,
        )
        Attendance.objects.create(
            employee=self.employee,
            date=date(2026, 7, 7),
            is_late=False,
            left_early=True,
        )
        Attendance.objects.create(
            employee=self.outsider,
            date=date(2026, 7, 7),
            is_late=True,
        )
        self.authenticate(self.manager_user)
        response = self.client.get("/api/v1/hr/attendance/monthly-summary/?year=2026&month=7")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        summary = response.data["results"][0]
        self.assertEqual(summary["employee_number"], self.employee.employee_number)
        self.assertEqual(summary["days_present"], 2)
        self.assertEqual(summary["late_days"], 1)
        self.assertEqual(summary["early_departure_days"], 1)
        invalid = self.client.get("/api/v1/hr/attendance/monthly-summary/?year=2026&month=13")
        self.assertEqual(invalid.status_code, 400)

    def test_team_leave_calendar_is_month_scoped_and_permission_scoped(self) -> None:
        request = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            start_date=date(2026, 7, 13),
            end_date=date(2026, 7, 14),
            requested_days=Decimal("2.00"),
            reason="Team leave",
        )
        LeaveRequest.objects.create(
            employee=self.outsider,
            leave_type=self.leave_type,
            start_date=date(2026, 7, 20),
            end_date=date(2026, 7, 20),
            requested_days=Decimal("1.00"),
            reason="Private to other team",
        )
        self.authenticate(self.manager_user)
        response = self.client.get("/api/v1/hr/leave-requests/calendar/?year=2026&month=7")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], request.pk)
        self.authenticate(self.outsider_user)
        response = self.client.get("/api/v1/hr/leave-requests/calendar/?year=2026&month=8")
        self.assertEqual(response.data["count"], 0)

    def test_attendance_rejects_users_without_employee_profile(self) -> None:
        user = User.objects.create_user(email="no-profile@hr.test", password="Strong-Password-123!")
        self.authenticate(user)
        response = self.client.post("/api/v1/hr/attendance/check-in/")
        self.assertEqual(response.status_code, 403)

    def test_leave_request_is_calculated_checked_and_approved_transactionally(self) -> None:
        self.authenticate(self.employee_user)
        response = self.client.post(
            "/api/v1/hr/leave-requests/",
            {
                "leave_type": self.leave_type.pk,
                "start_date": "2026-10-12",
                "end_date": "2026-10-14",
                "reason": "Family plans",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["requested_days"], "3.00")
        request_id = response.data["id"]
        overlap = self.client.post(
            "/api/v1/hr/leave-requests/",
            {
                "leave_type": self.leave_type.pk,
                "start_date": "2026-10-13",
                "end_date": "2026-10-15",
                "reason": "Overlapping request",
            },
            format="json",
        )
        self.assertEqual(overlap.status_code, 400)
        self.authenticate(self.manager_user)
        decision = self.client.post(
            f"/api/v1/hr/leave-requests/{request_id}/approve/",
            {"decision_note": "Approved"},
            format="json",
        )
        self.assertEqual(decision.status_code, 200, decision.data)
        self.assertEqual(decision.data["status"], LeaveRequest.Status.APPROVED)
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.used_days, Decimal("3.00"))
        second_decision = self.client.post(
            f"/api/v1/hr/leave-requests/{request_id}/approve/", {}, format="json"
        )
        self.assertEqual(second_decision.status_code, 400)

    def test_leave_request_requires_balance_and_cannot_cross_years(self) -> None:
        self.authenticate(self.employee_user)
        self.balance.accrued_days = Decimal("0.00")
        self.balance.save()
        insufficient = self.client.post(
            "/api/v1/hr/leave-requests/",
            {
                "leave_type": self.leave_type.pk,
                "start_date": "2026-10-12",
                "end_date": "2026-10-12",
                "reason": "No balance",
            },
            format="json",
        )
        self.assertEqual(insufficient.status_code, 400)
        cross_year = self.client.post(
            "/api/v1/hr/leave-requests/",
            {
                "leave_type": self.leave_type.pk,
                "start_date": "2026-12-31",
                "end_date": "2027-01-04",
                "reason": "Cross-year",
            },
            format="json",
        )
        self.assertEqual(cross_year.status_code, 400)

    def test_only_hr_or_reporting_manager_can_decide_leave(self) -> None:
        request = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            start_date=date(2026, 10, 12),
            end_date=date(2026, 10, 12),
            requested_days=Decimal("1.00"),
            reason="Appointment",
        )
        self.authenticate(self.employee_user)
        self.assertEqual(
            self.client.post(
                f"/api/v1/hr/leave-requests/{request.pk}/approve/", {}, format="json"
            ).status_code,
            403,
        )
        self.authenticate(self.outsider_user)
        self.assertEqual(
            self.client.post(
                f"/api/v1/hr/leave-requests/{request.pk}/approve/", {}, format="json"
            ).status_code,
            404,
        )

    def test_hr_can_reject_leave_and_employee_can_cancel_own_pending_request(self) -> None:
        request = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            start_date=date(2026, 10, 12),
            end_date=date(2026, 10, 12),
            requested_days=Decimal("1.00"),
            reason="Appointment",
        )
        self.authenticate(self.hr_user)
        response = self.client.post(
            f"/api/v1/hr/leave-requests/{request.pk}/reject/",
            {"decision_note": "Please choose another day."},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], LeaveRequest.Status.REJECTED)

        pending = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            start_date=date(2026, 10, 13),
            end_date=date(2026, 10, 13),
            requested_days=Decimal("1.00"),
            reason="Another appointment",
        )
        self.authenticate(self.employee_user)
        self.assertEqual(
            self.client.delete(f"/api/v1/hr/leave-requests/{pending.pk}/").status_code, 204
        )
        pending.refresh_from_db()
        self.assertEqual(pending.status, LeaveRequest.Status.CANCELLED)

    def test_leave_balance_adjustment_is_hr_only_and_audited(self) -> None:
        self.authenticate(self.employee_user)
        self.assertEqual(
            self.client.post(
                f"/api/v1/hr/leave-balances/{self.balance.pk}/adjust/",
                {"amount": "2.50"},
                format="json",
            ).status_code,
            403,
        )
        self.authenticate(self.hr_user)
        response = self.client.post(
            f"/api/v1/hr/leave-balances/{self.balance.pk}/adjust/",
            {"amount": "2.50"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["available_days"], "22.50")
        negative = self.client.post(
            f"/api/v1/hr/leave-balances/{self.balance.pk}/adjust/",
            {"amount": "-30.00"},
            format="json",
        )
        self.assertEqual(negative.status_code, 400)
        self.assertTrue(
            AuditLog.objects.filter(
                model_label="hr.LeaveBalance",
                object_id=str(self.balance.pk),
                action="update",
            ).exists()
        )

    def test_leave_types_and_holidays_can_only_be_changed_by_hr(self) -> None:
        self.authenticate(self.employee_user)
        self.assertEqual(
            self.client.post(
                "/api/v1/hr/holidays/",
                {"name": "Founders Day", "date": "2026-11-02"},
                format="json",
            ).status_code,
            403,
        )
        self.authenticate(self.hr_user)
        response = self.client.post(
            "/api/v1/hr/holidays/",
            {
                "name": "Founders Day",
                "date": "2026-11-02",
                "description": "Company holiday",
                "is_recurring": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)

    def test_business_day_count_excludes_weekends_and_recurring_holidays(self) -> None:
        Holiday.objects.create(name="Founders Day", date=date(2020, 10, 13), is_recurring=True)
        self.assertEqual(business_days(date(2026, 10, 12), date(2026, 10, 16)), 4)
        with self.assertRaises(APIValidationError):
            business_days(date(2026, 10, 16), date(2026, 10, 12))

    def test_monthly_leave_accrual_is_prorated_and_idempotent(self) -> None:
        self.leave_type.annual_allowance_days = Decimal("18.00")
        self.leave_type.save()
        first_run = accrue_monthly_leave_balances(2026, 7)
        second_run = accrue_monthly_leave_balances(2026, 7)
        self.assertEqual(first_run, 3)
        self.assertEqual(second_run, 0)
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.accrued_days, Decimal("21.50"))

    def test_accrual_management_command_rejects_invalid_month(self) -> None:
        from django.core.management import call_command
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command("accrue_leave_balances", "--year=2026", "--month=13")


class HRModelTests(TestCase):
    def test_employee_profile_requires_valid_termination_date(self) -> None:
        user = User.objects.create_user(email="terminated@hr.test", password="Strong-Password-123!")
        department = Department.objects.create(name="Support", code="SUP")
        designation = Designation.objects.create(title="Agent", department=department)
        employee = EmployeeProfile(
            user=user,
            employee_number="E-900",
            department=department,
            designation=designation,
            hire_date=date(2020, 1, 1),
            employment_status=EmployeeProfile.EmploymentStatus.TERMINATED,
        )
        with self.assertRaises(DjangoValidationError):
            employee.full_clean()

    def test_employee_document_validator_accepts_real_pdf_signature(self) -> None:
        document_file = SimpleUploadedFile("contract.pdf", b"%PDF-1.7 valid test")
        document = EmployeeDocument(
            employee=self._employee(),
            title="Employment contract",
            document_type="contract",
            file=document_file,
        )
        document.full_clean()

    @staticmethod
    def _employee() -> EmployeeProfile:
        user = User.objects.create_user(email="document@hr.test", password="Strong-Password-123!")
        department = Department.objects.create(name="Operations", code="OPS")
        designation = Designation.objects.create(title="Coordinator", department=department)
        return EmployeeProfile.objects.create(
            user=user,
            employee_number="E-901",
            department=department,
            designation=designation,
        )
