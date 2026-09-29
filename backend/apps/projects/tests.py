"""Focused API coverage for project scoping and delivery workflows."""

from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.core.models import Role, User
from apps.hr.models import Department, Designation, EmployeeProfile
from apps.projects.models import (
    Client,
    EmployeeHourlyCost,
    Milestone,
    Project,
    ResourceAllocation,
    Sprint,
    Task,
    TaskAttachment,
    validate_private_attachment,
)


class ProjectsApiTests(APITestCase):
    def setUp(self) -> None:
        self.admin_role = Role.objects.get_or_create(name="Admin")[0]
        self.manager_role = Role.objects.get_or_create(name="Manager")[0]
        self.employee_role = Role.objects.get_or_create(name="Employee")[0]
        self.client_role = Role.objects.get_or_create(name="Client")[0]
        self.manager_user = User.objects.create_user(
            email="manager-projects@example.com", password="Long-Secure-Password-123!"
        )
        self.manager_user.roles.add(self.manager_role)
        self.employee_user = User.objects.create_user(
            email="employee-projects@example.com", password="Long-Secure-Password-123!"
        )
        self.employee_user.roles.add(self.employee_role)
        self.colleague_user = User.objects.create_user(
            email="colleague-projects@example.com", password="Long-Secure-Password-123!"
        )
        self.colleague_user.roles.add(self.employee_role)
        self.hr_user = User.objects.create_user(
            email="hr-projects@example.com", password="Long-Secure-Password-123!"
        )
        self.hr_user.roles.add(Role.objects.get_or_create(name="HR")[0])
        self.client_user = User.objects.create_user(
            email="portal-projects@example.com", password="Long-Secure-Password-123!"
        )
        self.client_user.roles.add(self.client_role)
        self.finance_user = User.objects.create_user(
            email="finance-projects@example.com", password="Long-Secure-Password-123!"
        )
        self.finance_user.roles.add(Role.objects.get_or_create(name="Finance")[0])

        department = Department.objects.create(name="Delivery", code="DEL")
        designation = Designation.objects.create(title="Consultant", department=department)
        self.manager = EmployeeProfile.objects.create(
            user=self.manager_user,
            employee_number="M-100",
            department=department,
            designation=designation,
            hire_date=date.today() - timedelta(days=400),
        )
        self.employee = EmployeeProfile.objects.create(
            user=self.employee_user,
            employee_number="E-100",
            department=department,
            designation=designation,
            manager=self.manager,
            hire_date=date.today() - timedelta(days=200),
        )
        self.colleague = EmployeeProfile.objects.create(
            user=self.colleague_user,
            employee_number="E-101",
            department=department,
            designation=designation,
            manager=self.manager,
            hire_date=date.today() - timedelta(days=100),
        )
        self.hr_profile = EmployeeProfile.objects.create(
            user=self.hr_user,
            employee_number="H-100",
            department=department,
            designation=designation,
            hire_date=date.today() - timedelta(days=800),
        )
        self.own_client = Client.objects.create(name="Scoped Client")
        self.other_client = Client.objects.create(name="Other Client")
        self.own_client.portal_users.add(self.client_user)
        today = date.today()
        self.project = Project.objects.create(
            client=self.own_client,
            name="Portal project",
            code="PORTAL-1",
            manager=self.manager,
            start_date=today - timedelta(days=7),
            budget=Decimal("12500.00"),
        )
        self.other_project = Project.objects.create(
            client=self.other_client,
            name="Private project",
            code="PRIVATE-1",
            manager=self.hr_profile,
            start_date=today - timedelta(days=3),
            budget=Decimal("9000.00"),
        )
        self.task = Task.objects.create(
            project=self.project,
            title="Prepare delivery plan",
            assignee=self.employee,
            estimate_hours=Decimal("4.50"),
        )
        self.colleague_task = Task.objects.create(
            project=self.project,
            title="Review delivery plan",
            assignee=self.colleague,
            estimate_hours=Decimal("2.00"),
        )
        self.private_task = Task.objects.create(
            project=self.other_project,
            title="Internal work",
            assignee=self.hr_profile,
        )
        self.other_milestone = Milestone.objects.create(
            project=self.other_project,
            name="Private milestone",
            due_date=today + timedelta(days=30),
        )

    def authenticate(self, user: User) -> None:
        self.client.force_authenticate(user=user)

    def test_employee_sees_only_own_assigned_tasks_and_manager_sees_team_projects(self) -> None:
        self.authenticate(self.employee_user)
        response = self.client.get("/api/v1/projects/tasks/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], self.task.pk)
        comment = self.client.post(
            "/api/v1/projects/task-comments/",
            {"task": self.task.pk, "body": "Starting work"},
            format="json",
        )
        self.assertEqual(comment.status_code, 201, comment.data)
        self.assertEqual(comment.data["author"], self.employee_user.pk)

        self.authenticate(self.manager_user)
        response = self.client.get("/api/v1/projects/projects/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual({row["id"] for row in response.data["results"]}, {self.project.pk})

    def test_client_portal_is_limited_to_associated_client_and_projects(self) -> None:
        self.authenticate(self.client_user)
        clients = self.client.get("/api/v1/projects/clients/")
        self.assertEqual(clients.status_code, 200)
        self.assertEqual(clients.data["count"], 1)
        self.assertEqual(clients.data["results"][0]["id"], self.own_client.pk)

        projects = self.client.get("/api/v1/projects/projects/")
        self.assertEqual(projects.status_code, 200)
        self.assertEqual(projects.data["count"], 1)
        self.assertEqual(projects.data["results"][0]["id"], self.project.pk)
        self.assertEqual(
            self.client.get("/api/v1/projects/tasks/").status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                "/api/v1/projects/projects/",
                {"name": "Injected", "client": self.other_client.pk},
                format="json",
            ).status_code,
            403,
        )

    def test_task_relationships_are_validated_and_project_completion_requires_closed_tasks(
        self,
    ) -> None:
        self.authenticate(self.manager_user)
        invalid_task = self.client.post(
            "/api/v1/projects/tasks/",
            {
                "project": self.project.pk,
                "milestone": self.other_milestone.pk,
                "title": "Invalid milestone link",
                "assignee": self.employee.pk,
            },
            format="json",
        )
        self.assertEqual(invalid_task.status_code, 400)

        start = self.client.post(
            f"/api/v1/projects/projects/{self.project.pk}/transition/",
            {"status": "active"},
            format="json",
        )
        self.assertEqual(start.status_code, 200, start.data)
        complete = self.client.post(
            f"/api/v1/projects/projects/{self.project.pk}/transition/",
            {"status": "completed"},
            format="json",
        )
        self.assertEqual(complete.status_code, 400)
        self.assertIn("Complete or cancel all project tasks first.", str(complete.data))
        for task in (self.task, self.colleague_task):
            for next_status in ("ready", "in_progress", "done"):
                response = self.client.post(
                    f"/api/v1/projects/tasks/{task.pk}/status/",
                    {"status": next_status},
                    format="json",
                )
                self.assertEqual(response.status_code, 200, response.data)
        complete = self.client.post(
            f"/api/v1/projects/projects/{self.project.pk}/transition/",
            {"status": "completed"},
            format="json",
        )
        self.assertEqual(complete.status_code, 200, complete.data)

    def test_employee_submits_own_time_and_manager_approves_with_audit_state(self) -> None:
        self.authenticate(self.employee_user)
        created = self.client.post(
            "/api/v1/projects/time-entries/",
            {
                "task": self.task.pk,
                "work_date": timezone.localdate().isoformat(),
                "hours": "3.25",
                "description": "Implementation",
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)
        entry_id = created.data["id"]
        submitted = self.client.post(
            f"/api/v1/projects/time-entries/{entry_id}/submit/", {}, format="json"
        )
        self.assertEqual(submitted.status_code, 200, submitted.data)
        self.assertEqual(submitted.data["status"], "submitted")

        self.authenticate(self.manager_user)
        approved = self.client.post(
            f"/api/v1/projects/time-entries/{entry_id}/approve/",
            {"decision_note": "Reviewed"},
            format="json",
        )
        self.assertEqual(approved.status_code, 200, approved.data)
        self.assertEqual(approved.data["status"], "approved")
        self.assertEqual(approved.data["approver"], self.manager_user.pk)
        self.assertEqual(
            self.client.patch(
                f"/api/v1/projects/time-entries/{entry_id}/",
                {"hours": "4.00"},
                format="json",
            ).status_code,
            400,
        )

    def test_task_labels_are_assignable_and_upload_signatures_are_validated(self) -> None:
        self.authenticate(self.manager_user)
        label_response = self.client.post(
            "/api/v1/projects/task-labels/",
            {"name": "Frontend", "color": "#00AAFF"},
            format="json",
        )
        self.assertEqual(label_response.status_code, 201, label_response.data)
        response = self.client.patch(
            f"/api/v1/projects/tasks/{self.task.pk}/",
            {"labels": [label_response.data["id"]]},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["labels"], [label_response.data["id"]])

        invalid = SimpleUploadedFile("spoofed.pdf", b"not a pdf")
        with self.assertRaises(DjangoValidationError):
            validate_private_attachment(invalid)

        valid = SimpleUploadedFile("spec.pdf", b"%PDF-1.7 private project spec")
        uploaded = self.client.post(
            "/api/v1/projects/task-attachments/",
            {"task": self.task.pk, "file": valid},
            format="multipart",
        )
        self.assertEqual(uploaded.status_code, 201, uploaded.data)
        attachment = TaskAttachment.objects.get(pk=uploaded.data["id"])
        self.assertEqual(attachment.file_name, "spec.pdf")
        attachment.file.delete(save=False)

    def test_sprint_backlog_and_burndown_are_exposed(self) -> None:
        self.authenticate(self.manager_user)
        today = timezone.localdate()
        sprint = Sprint.objects.create(
            project=self.project,
            name="Sprint 1",
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=5),
        )
        self.task.sprint = sprint
        self.task.save(update_fields=["sprint", "updated_at"])
        backlog = self.client.get(f"/api/v1/projects/sprints/{sprint.pk}/backlog/")
        self.assertEqual(backlog.status_code, 200)
        self.assertEqual(backlog.data["count"], 1)
        status_response = self.client.post(
            f"/api/v1/projects/tasks/{self.task.pk}/status/",
            {"status": "ready"},
            format="json",
        )
        self.assertEqual(status_response.status_code, 200, status_response.data)
        self.client.post(
            f"/api/v1/projects/tasks/{self.task.pk}/status/",
            {"status": "in_progress"},
            format="json",
        )
        self.client.post(
            f"/api/v1/projects/tasks/{self.task.pk}/status/",
            {"status": "done"},
            format="json",
        )
        burndown = self.client.get(f"/api/v1/projects/sprints/{sprint.pk}/burndown/")
        self.assertEqual(burndown.status_code, 200)
        self.assertEqual(burndown.data[-1]["completed_estimate_hours"], "4.50")
        self.assertEqual(burndown.data[-1]["remaining_estimate_hours"], "0.00")

    def test_weekly_time_submission_approval_and_budget_cost_summary(self) -> None:
        self.authenticate(self.finance_user)
        rate = EmployeeHourlyCost.objects.create(
            employee=self.employee,
            hourly_cost=Decimal("25.00"),
            currency="USD",
            effective_from=date.today() - timedelta(days=30),
        )
        self.assertEqual(rate.hourly_cost, Decimal("25.00"))
        self.authenticate(self.employee_user)
        today = timezone.localdate()
        week_start = today - timedelta(days=today.weekday())
        entry = self.client.post(
            "/api/v1/projects/time-entries/",
            {
                "task": self.task.pk,
                "work_date": today.isoformat(),
                "hours": "3.50",
                "is_billable": False,
            },
            format="json",
        )
        self.assertEqual(entry.status_code, 201, entry.data)
        self.assertEqual(entry.data["hourly_cost_snapshot"], "25.00")
        self.assertEqual(entry.data["hourly_cost_currency_snapshot"], "USD")
        submission = self.client.post(
            "/api/v1/projects/time-submissions/",
            {
                "period_type": "weekly",
                "period_start": week_start.isoformat(),
                "period_end": (week_start + timedelta(days=6)).isoformat(),
                "entries": [entry.data["id"]],
            },
            format="json",
        )
        self.assertEqual(submission.status_code, 201, submission.data)
        self.assertEqual(submission.data["status"], "submitted")

        self.authenticate(self.manager_user)
        decision = self.client.post(
            f"/api/v1/projects/time-submissions/{submission.data['id']}/approve/",
            {"decision_note": "Weekly review"},
            format="json",
        )
        self.assertEqual(decision.status_code, 200, decision.data)
        self.assertEqual(decision.data["status"], "approved")
        self.authenticate(self.employee_user)
        daily_entry = self.client.post(
            "/api/v1/projects/time-entries/",
            {
                "task": self.task.pk,
                "work_date": today.isoformat(),
                "hours": "1.75",
                "is_billable": True,
            },
            format="json",
        )
        self.assertEqual(daily_entry.status_code, 201, daily_entry.data)
        daily = self.client.post(
            "/api/v1/projects/time-submissions/",
            {
                "period_type": "daily",
                "period_start": today.isoformat(),
                "period_end": today.isoformat(),
                "entries": [daily_entry.data["id"]],
            },
            format="json",
        )
        self.assertEqual(daily.status_code, 201, daily.data)
        self.authenticate(self.manager_user)
        daily_decision = self.client.post(
            f"/api/v1/projects/time-submissions/{daily.data['id']}/approve/",
            {"decision_note": "Daily review"},
            format="json",
        )
        self.assertEqual(daily_decision.status_code, 200, daily_decision.data)
        summary = self.client.get(f"/api/v1/projects/projects/{self.project.pk}/budget-summary/")
        self.assertEqual(summary.status_code, 200, summary.data)
        self.assertEqual(summary.data["actual_cost"], "131.25")
        self.assertEqual(summary.data["currency"], "USD")
        self.assertEqual(summary.data["billable_hours"], "1.75")

    def test_resource_capacity_and_bug_release_wiki_surfaces(self) -> None:
        self.authenticate(self.manager_user)
        today = timezone.localdate()
        ResourceAllocation.objects.create(
            project=self.project,
            employee=self.employee,
            role="Developer",
            allocation_percent=Decimal("70.00"),
            start_date=today,
            end_date=today + timedelta(days=1),
        )
        ResourceAllocation.objects.create(
            project=self.project,
            employee=self.employee,
            role="Reviewer",
            allocation_percent=Decimal("50.00"),
            start_date=today,
            end_date=today,
        )
        capacity = self.client.get(
            "/api/v1/projects/resource-allocations/capacity/",
            {"start_date": today.isoformat(), "end_date": today.isoformat()},
        )
        self.assertEqual(capacity.status_code, 200, capacity.data)
        row = next(item for item in capacity.data if item["employee_id"] == self.employee.pk)
        self.assertEqual(row["allocation_percent"], "120.00")
        self.assertTrue(row["overallocated"])

        bug = self.client.post(
            "/api/v1/projects/bugs/",
            {
                "project": self.project.pk,
                "title": "Broken output",
                "description": "Observed failure",
                "severity": "high",
                "assignee": self.employee.pk,
            },
            format="json",
        )
        self.assertEqual(bug.status_code, 201, bug.data)
        self.authenticate(self.employee_user)
        fixed = self.client.post(
            f"/api/v1/projects/bugs/{bug.data['id']}/status/",
            {"status": "triaged"},
            format="json",
        )
        self.assertEqual(fixed.status_code, 200, fixed.data)

        self.authenticate(self.manager_user)
        note = self.client.post(
            "/api/v1/projects/release-notes/",
            {
                "project": self.project.pk,
                "version": "1.0",
                "title": "First release",
                "content": "Feature launch",
                "release_date": today.isoformat(),
                "is_published": True,
            },
            format="json",
        )
        self.assertEqual(note.status_code, 201, note.data)
        wiki = self.client.post(
            "/api/v1/projects/wiki-pages/",
            {
                "project": self.project.pk,
                "title": "Getting started",
                "slug": "getting-started",
                "content": "# Welcome",
            },
            format="json",
        )
        self.assertEqual(wiki.status_code, 201, wiki.data)
        self.authenticate(self.client_user)
        notes = self.client.get("/api/v1/projects/release-notes/")
        self.assertEqual(notes.status_code, 200)
        self.assertEqual(notes.data["count"], 1)
        self.assertEqual(self.client.get("/api/v1/projects/wiki-pages/").status_code, 403)
