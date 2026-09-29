"""Versioned project delivery API routes."""

from rest_framework.routers import DefaultRouter

from apps.projects.views import (
    BugViewSet,
    ClientViewSet,
    EmployeeHourlyCostViewSet,
    MilestoneViewSet,
    ProjectDocumentViewSet,
    ProjectViewSet,
    ProjectWikiPageViewSet,
    ReleaseNoteViewSet,
    ResourceAllocationViewSet,
    SprintViewSet,
    TaskAttachmentViewSet,
    TaskCommentViewSet,
    TaskLabelViewSet,
    TaskViewSet,
    TimeEntryViewSet,
    TimeSubmissionViewSet,
)

router = DefaultRouter()
router.register("clients", ClientViewSet, basename="project-client")
router.register("projects", ProjectViewSet, basename="project")
router.register("milestones", MilestoneViewSet, basename="project-milestone")
router.register("sprints", SprintViewSet, basename="project-sprint")
router.register("tasks", TaskViewSet, basename="project-task")
router.register("task-labels", TaskLabelViewSet, basename="project-task-label")
router.register("task-attachments", TaskAttachmentViewSet, basename="project-task-attachment")
router.register("task-comments", TaskCommentViewSet, basename="project-task-comment")
router.register("time-entries", TimeEntryViewSet, basename="project-time-entry")
router.register("time-submissions", TimeSubmissionViewSet, basename="project-time-submission")
router.register(
    "resource-allocations", ResourceAllocationViewSet, basename="project-resource-allocation"
)
router.register("bugs", BugViewSet, basename="project-bug")
router.register("release-notes", ReleaseNoteViewSet, basename="project-release-note")
router.register("wiki-pages", ProjectWikiPageViewSet, basename="project-wiki-page")
router.register("documents", ProjectDocumentViewSet, basename="project-document")
router.register("hourly-costs", EmployeeHourlyCostViewSet, basename="project-hourly-cost")

urlpatterns = router.urls
