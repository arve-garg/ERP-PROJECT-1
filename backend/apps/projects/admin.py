"""Django admin configuration for project delivery."""

from django.contrib import admin

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


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["name", "email", "status", "created_at"]
    list_filter = ["status"]
    search_fields = ["name", "email", "phone"]
    filter_horizontal = ["portal_users"]


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["code", "name", "client", "manager", "status", "start_date", "end_date"]
    list_filter = ["status", "client"]
    search_fields = ["code", "name", "client__name", "manager__employee_number"]
    autocomplete_fields = ["client", "manager"]


@admin.register(Milestone)
class MilestoneAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["name", "project", "due_date", "status"]
    list_filter = ["status", "project"]
    search_fields = ["name", "project__name", "project__code"]
    autocomplete_fields = ["project"]


@admin.register(Sprint)
class SprintAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["name", "project", "start_date", "end_date", "status"]
    list_filter = ["status", "project"]
    search_fields = ["name", "project__name"]
    autocomplete_fields = ["project"]


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["title", "project", "assignee", "priority", "status", "due_date"]
    list_filter = ["status", "priority", "project"]
    search_fields = ["title", "project__name", "assignee__employee_number"]
    autocomplete_fields = ["project", "milestone", "sprint", "assignee"]
    filter_horizontal = ["labels"]


@admin.register(TaskLabel)
class TaskLabelAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["name", "color"]
    search_fields = ["name"]


@admin.register(TaskAttachment)
class TaskAttachmentAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["file_name", "task", "uploaded_by", "created_at"]
    search_fields = ["file_name", "task__title"]
    autocomplete_fields = ["task", "uploaded_by"]


@admin.register(TaskComment)
class TaskCommentAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["task", "author", "created_at"]
    search_fields = ["body", "task__title", "author__email"]
    autocomplete_fields = ["task", "author"]


@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["employee", "task", "work_date", "hours", "status", "approver"]
    list_filter = ["status", "work_date"]
    search_fields = ["employee__employee_number", "task__title", "task__project__name"]
    autocomplete_fields = ["task", "employee", "approver"]


@admin.register(TimeSubmission)
class TimeSubmissionAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = [
        "employee",
        "period_type",
        "period_start",
        "period_end",
        "status",
        "approver",
    ]
    list_filter = ["period_type", "status"]
    search_fields = ["employee__employee_number", "employee__user__email"]
    autocomplete_fields = ["employee", "approver"]
    filter_horizontal = ["entries"]


@admin.register(ResourceAllocation)
class ResourceAllocationAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["project", "employee", "role", "allocation_percent", "start_date", "end_date"]
    list_filter = ["project", "start_date"]
    search_fields = ["project__name", "employee__employee_number", "role"]
    autocomplete_fields = ["project", "employee"]


@admin.register(Bug)
class BugAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["title", "project", "severity", "status", "assignee"]
    list_filter = ["severity", "status", "project"]
    search_fields = ["title", "description", "project__name"]
    autocomplete_fields = ["project", "task", "reporter", "assignee"]


@admin.register(ReleaseNote)
class ReleaseNoteAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["version", "title", "project", "release_date", "is_published"]
    list_filter = ["is_published", "release_date"]
    search_fields = ["version", "title", "project__name"]
    autocomplete_fields = ["project"]


@admin.register(ProjectWikiPage)
class ProjectWikiPageAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["title", "project", "slug", "updated_at"]
    search_fields = ["title", "content", "project__name"]
    autocomplete_fields = ["project"]


@admin.register(ProjectDocument)
class ProjectDocumentAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["title", "project", "file_name", "client_visible", "uploaded_by"]
    list_filter = ["client_visible", "project"]
    search_fields = ["title", "file_name", "project__name"]
    autocomplete_fields = ["project", "uploaded_by"]


@admin.register(EmployeeHourlyCost)
class EmployeeHourlyCostAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["employee", "hourly_cost", "currency", "effective_from", "effective_to"]
    list_filter = ["currency", "effective_from"]
    search_fields = ["employee__employee_number", "employee__user__email"]
    autocomplete_fields = ["employee"]
