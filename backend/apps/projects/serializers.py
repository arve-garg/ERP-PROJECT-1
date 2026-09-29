"""Validated API representations for project delivery records."""

from typing import Any

from django.utils import timezone
from rest_framework import serializers

from apps.core.models import User
from apps.hr.models import EmployeeProfile
from apps.projects.models import (
    Bug,
    Client,
    EmployeeHourlyCost,
    Milestone,
    Project,
    ProjectDocument,
    ProjectWikiPage,
    ReleaseNote,
    ResourceAllocation,
    Sprint,
    Task,
    TaskAttachment,
    TaskComment,
    TaskLabel,
    TimeEntry,
    TimeSubmission,
)


class ClientSerializer(serializers.ModelSerializer[Client]):
    portal_users = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(
            is_active=True,
            is_deleted=False,
            roles__name="Client",
        ).distinct(),
        many=True,
        required=False,
    )

    class Meta:
        model = Client
        fields = [
            "id",
            "name",
            "email",
            "phone",
            "website",
            "address",
            "notes",
            "status",
            "portal_users",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ClientPortalSerializer(serializers.ModelSerializer[Client]):
    class Meta:
        model = Client
        fields = ["id", "name", "email", "phone", "website", "address", "status"]
        read_only_fields = fields


class ProjectSerializer(serializers.ModelSerializer[Project]):
    client_name = serializers.CharField(source="client.name", read_only=True)
    manager_name = serializers.CharField(source="manager.user.get_full_name", read_only=True)

    class Meta:
        model = Project
        fields = [
            "id",
            "client",
            "client_name",
            "name",
            "code",
            "description",
            "manager",
            "manager_name",
            "start_date",
            "end_date",
            "estimated_hours",
            "budget",
            "budget_currency",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "status", "created_at", "updated_at"]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end_date = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({"end_date": "End date cannot precede start date."})
        return attrs


class ProjectPortalSerializer(serializers.ModelSerializer[Project]):
    client_name = serializers.CharField(source="client.name", read_only=True)

    class Meta:
        model = Project
        fields = [
            "id",
            "client_name",
            "name",
            "code",
            "description",
            "start_date",
            "end_date",
            "status",
        ]
        read_only_fields = fields


class MilestoneSerializer(serializers.ModelSerializer[Milestone]):
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = Milestone
        fields = [
            "id",
            "project",
            "project_name",
            "name",
            "description",
            "due_date",
            "status",
            "completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "status", "completed_at", "created_at", "updated_at"]


class SprintSerializer(serializers.ModelSerializer[Sprint]):
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = Sprint
        fields = [
            "id",
            "project",
            "project_name",
            "name",
            "goal",
            "start_date",
            "end_date",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "status", "created_at", "updated_at"]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError(
                {"end_date": "Sprint end date must be on or after its start."}
            )
        return attrs


class TaskSerializer(serializers.ModelSerializer[Task]):
    project_name = serializers.CharField(source="project.name", read_only=True)
    assignee_name = serializers.CharField(
        source="assignee.user.get_full_name", read_only=True, allow_null=True
    )
    labels = serializers.PrimaryKeyRelatedField(
        queryset=TaskLabel.objects.filter(is_deleted=False), many=True, required=False
    )

    class Meta:
        model = Task
        fields = [
            "id",
            "project",
            "project_name",
            "milestone",
            "sprint",
            "title",
            "description",
            "assignee",
            "assignee_name",
            "labels",
            "estimate_hours",
            "priority",
            "status",
            "due_date",
            "completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "status", "completed_at", "created_at", "updated_at"]


class TaskCommentSerializer(serializers.ModelSerializer[TaskComment]):
    author_name = serializers.CharField(source="author.get_full_name", read_only=True)

    class Meta:
        model = TaskComment
        fields = ["id", "task", "author", "author_name", "body", "created_at", "updated_at"]
        read_only_fields = ["id", "author", "author_name", "created_at", "updated_at"]


class TaskLabelSerializer(serializers.ModelSerializer[TaskLabel]):
    class Meta:
        model = TaskLabel
        fields = ["id", "name", "color", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class TaskAttachmentSerializer(serializers.ModelSerializer[TaskAttachment]):
    file = serializers.FileField(write_only=True)

    class Meta:
        model = TaskAttachment
        fields = ["id", "task", "file", "file_name", "uploaded_by", "created_at"]
        read_only_fields = ["id", "file_name", "uploaded_by", "created_at"]


class TimeEntrySerializer(serializers.ModelSerializer[TimeEntry]):
    employee_number = serializers.CharField(source="employee.employee_number", read_only=True)
    employee_name = serializers.CharField(source="employee.user.get_full_name", read_only=True)
    task_title = serializers.CharField(source="task.title", read_only=True)
    project_name = serializers.CharField(source="task.project.name", read_only=True)
    approver_name = serializers.CharField(
        source="approver.get_full_name", read_only=True, allow_null=True
    )

    class Meta:
        model = TimeEntry
        fields = [
            "id",
            "task",
            "task_title",
            "project_name",
            "employee",
            "employee_number",
            "employee_name",
            "work_date",
            "hours",
            "description",
            "is_billable",
            "hourly_cost_snapshot",
            "hourly_cost_currency_snapshot",
            "status",
            "submitted_at",
            "decided_at",
            "approver",
            "approver_name",
            "decision_note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "employee",
            "hourly_cost_snapshot",
            "hourly_cost_currency_snapshot",
            "status",
            "submitted_at",
            "decided_at",
            "approver",
            "approver_name",
            "decision_note",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        task = attrs.get("task", getattr(self.instance, "task", None))
        user = self.context["request"].user
        employee = EmployeeProfile.objects.filter(user=user, is_deleted=False).first()
        if employee is None or task is None:
            raise serializers.ValidationError(
                {"task": "An employee profile and task are required."}
            )
        if task.assignee_id != employee.pk:
            raise serializers.ValidationError(
                {"task": "You can record time only on your assigned task."}
            )
        if task.is_deleted or task.project.is_deleted:
            raise serializers.ValidationError({"task": "Cannot record time on an archived task."})
        work_date = attrs.get("work_date", getattr(self.instance, "work_date", None))
        if work_date and work_date > timezone.localdate():
            raise serializers.ValidationError({"work_date": "Future time entries are not allowed."})
        if self.instance and self.instance.status not in {
            TimeEntry.Status.DRAFT,
            TimeEntry.Status.REJECTED,
        }:
            raise serializers.ValidationError(
                {"status": "Only draft or rejected time can be edited."}
            )
        return attrs


class TimeSubmissionSerializer(serializers.ModelSerializer[TimeSubmission]):
    entries = serializers.PrimaryKeyRelatedField(
        queryset=TimeEntry.objects.filter(is_deleted=False), many=True
    )
    employee_number = serializers.CharField(source="employee.employee_number", read_only=True)
    approver_name = serializers.CharField(
        source="approver.get_full_name", read_only=True, allow_null=True
    )

    class Meta:
        model = TimeSubmission
        fields = [
            "id",
            "employee",
            "employee_number",
            "period_type",
            "period_start",
            "period_end",
            "entries",
            "status",
            "submitted_at",
            "decided_at",
            "approver",
            "approver_name",
            "decision_note",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "employee",
            "status",
            "submitted_at",
            "decided_at",
            "approver",
            "approver_name",
            "decision_note",
            "created_at",
        ]


class ResourceAllocationSerializer(serializers.ModelSerializer[ResourceAllocation]):
    employee_name = serializers.CharField(source="employee.user.get_full_name", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = ResourceAllocation
        fields = [
            "id",
            "project",
            "project_name",
            "employee",
            "employee_name",
            "role",
            "allocation_percent",
            "start_date",
            "end_date",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class StatusTransitionSerializer(serializers.Serializer[dict[str, Any]]):
    status = serializers.CharField(max_length=16)


class TimeDecisionSerializer(serializers.Serializer[dict[str, Any]]):
    decision_note = serializers.CharField(required=False, allow_blank=True, max_length=1000)


class BugSerializer(serializers.ModelSerializer[Bug]):
    reporter_name = serializers.CharField(source="reporter.get_full_name", read_only=True)
    assignee_name = serializers.CharField(
        source="assignee.user.get_full_name", read_only=True, allow_null=True
    )

    class Meta:
        model = Bug
        fields = [
            "id",
            "project",
            "task",
            "title",
            "description",
            "steps_to_reproduce",
            "expected_behavior",
            "actual_behavior",
            "severity",
            "status",
            "reporter",
            "reporter_name",
            "assignee",
            "assignee_name",
            "resolved_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "reporter", "resolved_at", "created_at", "updated_at"]


class ReleaseNoteSerializer(serializers.ModelSerializer[ReleaseNote]):
    class Meta:
        model = ReleaseNote
        fields = [
            "id",
            "project",
            "version",
            "title",
            "content",
            "release_date",
            "is_published",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ProjectWikiPageSerializer(serializers.ModelSerializer[ProjectWikiPage]):
    class Meta:
        model = ProjectWikiPage
        fields = [
            "id",
            "project",
            "title",
            "slug",
            "content",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ProjectDocumentSerializer(serializers.ModelSerializer[ProjectDocument]):
    file = serializers.FileField(write_only=True)

    class Meta:
        model = ProjectDocument
        fields = [
            "id",
            "project",
            "title",
            "description",
            "file",
            "file_name",
            "client_visible",
            "uploaded_by",
            "created_at",
        ]
        read_only_fields = ["id", "file_name", "uploaded_by", "created_at"]


class EmployeeHourlyCostSerializer(serializers.ModelSerializer[EmployeeHourlyCost]):
    employee_number = serializers.CharField(source="employee.employee_number", read_only=True)
    employee_name = serializers.CharField(source="employee.user.get_full_name", read_only=True)

    class Meta:
        model = EmployeeHourlyCost
        fields = [
            "id",
            "employee",
            "employee_number",
            "employee_name",
            "hourly_cost",
            "currency",
            "effective_from",
            "effective_to",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SprintBurndownPointSerializer(serializers.Serializer[list[dict[str, Any]]]):
    date = serializers.DateField()
    remaining_estimate_hours = serializers.DecimalField(max_digits=12, decimal_places=2)
    completed_estimate_hours = serializers.DecimalField(max_digits=12, decimal_places=2)


class ProjectBudgetSummarySerializer(serializers.Serializer[dict[str, Any]]):
    project_id = serializers.IntegerField()
    budget = serializers.DecimalField(max_digits=14, decimal_places=2)
    currency = serializers.CharField()
    actual_cost = serializers.DecimalField(max_digits=14, decimal_places=2)
    remaining_budget = serializers.DecimalField(max_digits=14, decimal_places=2)
    approved_hours = serializers.DecimalField(max_digits=12, decimal_places=2)
    billable_hours = serializers.DecimalField(max_digits=12, decimal_places=2)
    unpriced_approved_hours = serializers.DecimalField(max_digits=12, decimal_places=2)


class ResourceCapacityRowSerializer(serializers.Serializer[list[dict[str, Any]]]):
    employee_id = serializers.IntegerField()
    employee_number = serializers.CharField()
    employee_name = serializers.CharField()
    date = serializers.DateField()
    allocation_percent = serializers.DecimalField(max_digits=8, decimal_places=2)
    capacity_hours = serializers.DecimalField(max_digits=8, decimal_places=2)
    overallocated = serializers.BooleanField()
