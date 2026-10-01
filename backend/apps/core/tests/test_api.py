"""Tests for identity, access control, and core API behavior."""

from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice
from openpyxl import Workbook
from rest_framework.test import APITestCase
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import (
    ActivityFeedItem,
    AuditLog,
    CompanySetting,
    Notification,
    Role,
    SavedFilter,
    User,
)


class CoreApiTests(APITestCase):
    def setUp(self) -> None:
        self.admin = User.objects.create_user(
            email="admin@example.com", password="Very-Secure-Password-123"
        )
        self.admin_role, _ = Role.objects.get_or_create(name="Admin")
        self.admin.roles.add(self.admin_role)
        self.employee = User.objects.create_user(
            email="staff@example.com", password="Another-Secure-Password-123"
        )

    def authenticate(self, user: User) -> None:
        self.client.force_authenticate(user)

    def test_user_list_requires_admin_role_and_is_paginated(self) -> None:
        self.authenticate(self.employee)
        self.assertEqual(self.client.get("/api/v1/users/").status_code, 403)
        self.authenticate(self.admin)
        response = self.client.get("/api/v1/users/?page_size=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(len(response.data["results"]), 1)
        target = self.employee
        response = self.client.put(
            f"/api/v1/users/{target.pk}/roles/",
            {"roles": ["Employee", "Manager"]},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data["roles"]), {"Employee", "Manager"})

    def test_current_user_profile_is_limited_to_authenticated_user(self) -> None:
        self.authenticate(self.employee)
        response = self.client.get("/api/v1/users/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["email"], self.employee.email)
        self.assertNotIn("is_active", response.data)
        self.assertEqual(
            self.client.patch("/api/v1/users/me/", {"roles": ["Admin"]}).status_code, 200
        )
        self.assertFalse(self.employee.roles.filter(name="Admin").exists())
        self.assertEqual(
            self.client.patch("/api/v1/users/me/", {"first_name": "Self"}).status_code, 200
        )

    def test_login_returns_access_and_refresh_tokens(self) -> None:
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.employee.email, "password": "Another-Secure-Password-123"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["email"], self.employee.email)

    def test_refresh_requires_a_refresh_token_and_returns_access(self) -> None:
        self.assertEqual(self.client.post("/api/v1/auth/token/refresh/", {}).status_code, 400)
        refresh = str(RefreshToken.for_user(self.employee))
        response = self.client.post("/api/v1/auth/token/refresh/", {"refresh": refresh})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("access", response.data)

    def test_health_endpoint_is_public(self) -> None:
        response = self.client.get("/api/v1/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "ok")

    def test_totp_is_enforced_for_login_and_valid_code_succeeds(self) -> None:
        device = TOTPDevice.objects.create(user=self.employee, name="test", confirmed=True)
        self.employee.totp_required = True
        self.employee.save(update_fields=["totp_required"])
        payload = {"email": self.employee.email, "password": "Another-Secure-Password-123"}
        self.assertEqual(self.client.post("/api/v1/auth/login/", payload).status_code, 400)
        payload["otp_code"] = str(
            totp(
                device.bin_key,
                step=device.step,
                t0=device.t0,
                digits=device.digits,
                drift=device.drift,
            )
        )
        response = self.client.post("/api/v1/auth/login/", payload)
        self.assertEqual(response.status_code, 200)

    def test_admin_can_manage_company_settings(self) -> None:
        self.authenticate(self.employee)
        self.assertEqual(self.client.post("/api/v1/company-settings/", {}).status_code, 403)
        self.authenticate(self.admin)
        response = self.client.post(
            "/api/v1/company-settings/",
            {"key": "working_days", "value": ["Monday", "Tuesday"], "description": "Work week"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(
            CompanySetting.objects.get(key="working_days").value, ["Monday", "Tuesday"]
        )

    def test_notifications_are_private_and_can_be_read(self) -> None:
        own = Notification.objects.create(recipient=self.employee, title="Private")
        Notification.objects.create(recipient=self.admin, title="Admin private")
        self.authenticate(self.employee)
        self.assertEqual(
            self.client.get("/api/v1/notifications/unread-count/").data["unread_count"], 1
        )
        response = self.client.post(f"/api/v1/notifications/{own.pk}/read/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_read"])
        self.assertEqual(self.client.get("/api/v1/notifications/").data["count"], 1)

    def test_audit_logs_are_admin_only_and_capture_model_changes(self) -> None:
        setting = CompanySetting.objects.create(key="currency", value="USD")
        setting.value = "EUR"
        setting.save()
        self.authenticate(self.employee)
        self.assertEqual(self.client.get("/api/v1/audit-logs/").status_code, 403)
        self.authenticate(self.admin)
        response = self.client.get("/api/v1/audit-logs/?model_label=core.CompanySetting")
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data["count"], 2)
        self.assertTrue(
            AuditLog.objects.filter(object_id=str(setting.pk), action="update").exists()
        )

    def test_logout_blacklists_refresh_token(self) -> None:
        self.authenticate(self.employee)
        refresh = str(RefreshToken.for_user(self.employee))
        response = self.client.post("/api/v1/auth/logout/", {"refresh": refresh})
        self.assertEqual(response.status_code, 204)

    def test_search_requires_minimum_query_length(self) -> None:
        self.authenticate(self.admin)
        self.assertEqual(self.client.get("/api/v1/search/?q=a").status_code, 400)
        response = self.client.get("/api/v1/search/?q=staff")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["entity"], "user")
        self.assertIn("display_name", response.data["results"][0])

    def test_user_csv_and_xlsx_import_export(self) -> None:
        self.authenticate(self.admin)
        csv_data = (
            "email,first_name,last_name,password,roles\n"
            "new@example.com,New,Person,Very-Strong-Password-123!,Employee\n"
        )
        response = self.client.post(
            "/api/v1/users/import/",
            {"file": SimpleUploadedFile("users.csv", csv_data.encode())},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["created"], 1)
        self.assertTrue(
            User.objects.get(email="new@example.com").roles.filter(name="Employee").exists()
        )

        csv_export = self.client.get("/api/v1/users/export/?file_format=csv")
        self.assertEqual(csv_export.status_code, 200)
        self.assertIn("new@example.com", csv_export.content.decode())
        xlsx_export = self.client.get("/api/v1/users/export/?file_format=xlsx")
        self.assertEqual(xlsx_export.status_code, 200)
        self.assertIn("spreadsheetml", xlsx_export["Content-Type"])
        self.assertEqual(self.client.get("/api/v1/users/export/?file_format=pdf").status_code, 400)

        invalid = self.client.post(
            "/api/v1/users/import/",
            {"file": SimpleUploadedFile("invalid.csv", b"email,first_name\nbad@example.com,Bad\n")},
            format="multipart",
        )
        self.assertEqual(invalid.status_code, 400)
        unsupported = self.client.post(
            "/api/v1/users/import/",
            {"file": SimpleUploadedFile("users.txt", b"not a supported file")},
            format="multipart",
        )
        self.assertEqual(unsupported.status_code, 400)

    def test_user_import_xlsx_and_rejects_invalid_uploads(self) -> None:
        self.authenticate(self.admin)
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["email", "first_name", "last_name", "password"])
        sheet.append(["xlsx@example.com", "Xlsx", "Person", "Another-Strong-Password-123!"])
        buffer = BytesIO()
        workbook.save(buffer)
        response = self.client.post(
            "/api/v1/users/import/",
            {
                "file": SimpleUploadedFile(
                    "users.xlsx",
                    buffer.getvalue(),
                    content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.data)

        missing = self.client.post("/api/v1/users/import/", {}, format="multipart")
        self.assertEqual(missing.status_code, 400)
        empty = self.client.post(
            "/api/v1/users/import/",
            {"file": SimpleUploadedFile("empty.csv", b"")},
            format="multipart",
        )
        self.assertEqual(empty.status_code, 400)
        malformed = self.client.post(
            "/api/v1/users/import/",
            {"file": SimpleUploadedFile("broken.xlsx", b"not an xlsx file")},
            format="multipart",
        )
        self.assertEqual(malformed.status_code, 400)

    def test_saved_filters_are_scoped_and_shared_filters_are_read_only_for_others(self) -> None:
        shared = SavedFilter.objects.create(
            owner=self.admin, module="projects", name="Shared", is_shared=True
        )
        private = SavedFilter.objects.create(
            owner=self.admin, module="projects", name="Private", is_shared=False
        )
        self.authenticate(self.employee)
        response = self.client.get("/api/v1/saved-filters/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["name"] for item in response.data["results"]], ["Shared"])
        self.assertEqual(
            self.client.patch(f"/api/v1/saved-filters/{shared.pk}/", {}).status_code, 403
        )
        self.assertEqual(self.client.delete(f"/api/v1/saved-filters/{shared.pk}/").status_code, 403)
        self.assertFalse(SavedFilter.objects.get(pk=private.pk).is_deleted)

        response = self.client.post(
            "/api/v1/saved-filters/",
            {
                "module": "projects",
                "name": "Mine",
                "definition": {"status": "active"},
                "is_shared": False,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(
            self.client.patch(
                f"/api/v1/saved-filters/{response.data['id']}/",
                {"name": "Updated"},
                format="json",
            ).status_code,
            200,
        )

    def test_activity_feed_and_mark_all_notifications_read(self) -> None:
        ActivityFeedItem.objects.create(actor=self.admin, verb="created a project")
        own = Notification.objects.create(recipient=self.employee, title="First")
        Notification.objects.create(recipient=self.employee, title="Second")
        self.authenticate(self.employee)
        response = self.client.get(f"/api/v1/activity-feed/?actor={self.admin.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            any(item["verb"] == "created a project" for item in response.data["results"])
        )
        response = self.client.post("/api/v1/notifications/read-all/")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(
            self.client.get("/api/v1/notifications/unread-count/").data["unread_count"], 0
        )
        own.refresh_from_db()
        self.assertTrue(own.is_read)

    def test_totp_setup_confirm_disable_and_reject_invalid_code(self) -> None:
        self.authenticate(self.employee)
        setup = self.client.post("/api/v1/auth/2fa/setup/", {}, format="json")
        self.assertEqual(setup.status_code, 200)
        self.assertIn("provisioning_uri", setup.data)

        device = TOTPDevice.objects.get(user=self.employee, confirmed=False)
        code = f"{
            totp(
                device.bin_key,
                step=device.step,
                t0=device.t0,
                digits=device.digits,
                drift=device.drift + 1,
            ):06d}"
        response = self.client.post("/api/v1/auth/2fa/confirm/", {"code": code})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(User.objects.get(pk=self.employee.pk).totp_required)
        self.assertEqual(self.client.post("/api/v1/auth/2fa/setup/", {}).status_code, 400)
        device.refresh_from_db()
        code = f"{
            totp(
                device.bin_key,
                step=device.step,
                t0=device.t0,
                digits=device.digits,
                drift=device.drift + 1,
            ):06d}"
        self.assertEqual(
            self.client.post("/api/v1/auth/2fa/disable/", {"code": code}).status_code, 200
        )
        self.assertFalse(User.objects.get(pk=self.employee.pk).totp_required)

    def test_totp_confirmation_rejects_invalid_code(self) -> None:
        self.authenticate(self.employee)
        self.assertEqual(self.client.post("/api/v1/auth/2fa/setup/", {}).status_code, 200)
        response = self.client.post("/api/v1/auth/2fa/confirm/", {"code": "000000"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("invalid", response.data["code"][0].lower())

    def test_password_reset_confirm_invalidates_outstanding_refresh_tokens(self) -> None:
        refresh = RefreshToken.for_user(self.employee)
        from django.contrib.auth.tokens import default_token_generator

        response = self.client.post(
            "/api/v1/auth/password/reset/confirm/",
            {
                "uid": urlsafe_base64_encode(force_bytes(self.employee.pk)),
                "token": default_token_generator.make_token(self.employee),
                "new_password": "Reset-Password-Strong-456!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.employee.refresh_from_db()
        self.assertTrue(self.employee.check_password("Reset-Password-Strong-456!"))
        self.assertTrue(BlacklistedToken.objects.filter(token__jti=refresh["jti"]).exists())

        invalid = self.client.post(
            "/api/v1/auth/password/reset/confirm/",
            {"uid": "invalid", "token": "invalid", "new_password": "Another-Strong-Password-123!"},
            format="json",
        )
        self.assertEqual(invalid.status_code, 400)
