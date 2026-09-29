"""Audit changes to client portal access assignments."""

from typing import Any

from django.db.models import Model
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from django.utils import timezone

from apps.core.audit_context import actor_for_audit
from apps.core.models import ActivityFeedItem, AuditLog
from apps.projects.models import Client

_portal_assignments_before_clear: dict[tuple[int, bool], list[int]] = {}


def _record_portal_change(client_id: int, user_ids: list[int], operation: str) -> None:
    actor = actor_for_audit()
    changes = {"operation": operation, "portal_user_ids": user_ids}
    AuditLog.objects.create(
        actor=actor,
        action="portal_access",
        model_label="projects.Client.portal_users",
        object_id=str(client_id),
        changes=changes,
        occurred_at=timezone.now(),
    )
    ActivityFeedItem.objects.create(
        actor=actor,
        verb=f"Changed portal access for client {client_id}",
        target_type="projects.Client",
        target_id=str(client_id),
        metadata=changes,
        created_by=actor,
        updated_by=actor,
    )


@receiver(m2m_changed, sender=Client.portal_users.through)
def audit_client_portal_users(
    sender: type[Model],
    instance: Any,
    action: str,
    pk_set: set[int] | None,
    reverse: bool,
    **kwargs: Any,
) -> None:
    if action == "pre_clear":
        key = (instance.pk, reverse)
        if reverse:
            _portal_assignments_before_clear[key] = list(
                instance.project_clients.values_list("pk", flat=True)
            )
        else:
            _portal_assignments_before_clear[key] = list(
                instance.portal_users.values_list("pk", flat=True)
            )
        return
    if action not in {"post_add", "post_remove", "post_clear"}:
        return
    operation = "clear" if action == "post_clear" else action.removeprefix("post_")
    if reverse:
        client_ids = (
            sorted(pk_set or ())
            if action != "post_clear"
            else _portal_assignments_before_clear.pop((instance.pk, True), [])
        )
        for client_id in client_ids:
            _record_portal_change(client_id, [instance.pk], operation)
        return
    user_ids = (
        sorted(pk_set or ())
        if action != "post_clear"
        else _portal_assignments_before_clear.pop((instance.pk, False), [])
    )
    _record_portal_change(instance.pk, user_ids, operation)
