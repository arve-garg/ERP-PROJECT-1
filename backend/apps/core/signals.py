"""Audit signal handlers for changes to core audited models."""

from __future__ import annotations

import json
from typing import Any, cast

from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Model
from django.db.models.fields.files import FileField
from django.db.models.signals import m2m_changed, post_delete, post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from apps.core.audit_context import actor_for_audit
from apps.core.models import ActivityFeedItem, AuditedModel, AuditLog

DEFAULT_ROLES = {
    "Admin": "Manage users, roles, settings, and audit history.",
    "HR": "Manage employee and people operations.",
    "Manager": "Manage teams and project delivery.",
    "Finance": "Manage finance and accounting operations.",
    "Sales": "Manage clients, leads, deals, and quotes.",
    "Support": "Manage support requests and knowledge articles.",
    "Employee": "Access assigned employee self-service features.",
    "Client": "Access the client portal and own client records.",
}

_original_values: dict[tuple[str, str], dict[str, Any]] = {}
_roles_before_clear: dict[tuple[int, bool], list[int]] = {}


def _is_audited(instance: Model) -> bool:
    return isinstance(instance, (get_user_model(), AuditedModel)) and not isinstance(
        instance, (AuditLog, ActivityFeedItem)
    )


def _serialize(instance: Model) -> dict[str, Any]:
    """Serialize model values into JSON-safe audit values, excluding credentials."""
    values: dict[str, Any] = {}
    for field in instance._meta.concrete_fields:
        if field.name == "password":
            values["__password_hash"] = getattr(instance, field.attname)
        elif isinstance(field, FileField):
            file_value = getattr(instance, field.attname)
            values[field.name] = file_value.name if file_value else None
        else:
            values[field.name] = getattr(instance, field.attname)
    for field in instance._meta.many_to_many:
        values[field.name] = list(getattr(instance, field.name).values_list("pk", flat=True))
    return cast(dict[str, Any], json.loads(json.dumps(values, cls=DjangoJSONEncoder)))


@receiver(pre_save)
def capture_previous_values(sender: type[Model], instance: Model, **kwargs: Any) -> None:
    if not _is_audited(instance):
        return
    actor = actor_for_audit()
    if isinstance(instance, (AuditedModel, get_user_model())) and actor is not None:
        if instance._state.adding and instance.created_by_id is None:
            instance.created_by = actor
        if instance.updated_by_id is None or instance.updated_by_id != actor.pk:
            instance.updated_by = actor
    if instance.pk is not None:
        try:
            previous = sender._default_manager.get(pk=instance.pk)
        except ObjectDoesNotExist:
            return
        key = (sender._meta.label, str(instance.pk))
        _original_values[key] = _serialize(previous)


@receiver(post_save)
def record_model_change(
    sender: type[Model], instance: Model, created: bool, raw: bool = False, **kwargs: Any
) -> None:
    if raw or not _is_audited(instance):
        return
    label = sender._meta.label
    object_id = str(instance.pk)
    key = (label, object_id)
    current = _serialize(instance)
    previous = _original_values.pop(key, {})
    if created:
        action = "create"
        changes = {
            "after": {
                field: value for field, value in current.items() if field != "__password_hash"
            }
        }
    else:
        changed: dict[str, Any] = {}
        for field, value in current.items():
            if previous.get(field) == value:
                continue
            if field == "__password_hash":
                changed["password"] = {
                    "before": "set" if previous.get(field) else "unset",
                    "after": "changed",
                }
            else:
                changed[field] = {"before": previous.get(field), "after": value}
        if not changed:
            return
        action = "update"
        changes = changed
    actor = actor_for_audit()
    AuditLog.objects.create(
        actor=actor,
        action=action,
        model_label=label,
        object_id=object_id,
        changes=changes,
        occurred_at=timezone.now(),
    )
    ActivityFeedItem.objects.create(
        actor=actor,
        verb=f"{action.capitalize()} {sender._meta.verbose_name}",
        target_type=label,
        target_id=object_id,
        metadata={"action": action},
        created_by=actor,
        updated_by=actor,
    )


@receiver(post_delete)
def record_model_deletion(sender: type[Model], instance: Model, **kwargs: Any) -> None:
    if not _is_audited(instance):
        return
    AuditLog.objects.create(
        actor=actor_for_audit(),
        action="delete",
        model_label=sender._meta.label,
        object_id=str(instance.pk),
        changes={"before": _serialize(instance)},
        occurred_at=timezone.now(),
    )


@receiver(m2m_changed, sender=get_user_model().roles.through)
def record_user_role_change(
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
            _roles_before_clear[key] = list(instance.users.values_list("pk", flat=True))
        else:
            _roles_before_clear[key] = list(instance.roles.values_list("pk", flat=True))
        return
    if action not in {"post_add", "post_remove", "post_clear"}:
        return
    if reverse:
        user_ids = (
            sorted(pk_set or ())
            if action != "post_clear"
            else _roles_before_clear.pop((instance.pk, True), [])
        )
        role_ids = [instance.pk]
    else:
        user_ids = [instance.pk]
        role_ids = (
            sorted(pk_set or ())
            if action != "post_clear"
            else _roles_before_clear.pop((instance.pk, False), [])
        )
    operation = "clear" if action == "post_clear" else action.removeprefix("post_")
    actor = actor_for_audit()
    for user_id in user_ids:
        changes = {"operation": operation, "role_ids": role_ids}
        AuditLog.objects.create(
            actor=actor,
            action="role_assignment",
            model_label="core.user.roles",
            object_id=str(user_id),
            changes=changes,
            occurred_at=timezone.now(),
        )
        ActivityFeedItem.objects.create(
            actor=actor,
            verb=f"Changed roles for user {user_id}",
            target_type="core.User",
            target_id=str(user_id),
            metadata=changes,
            created_by=actor,
            updated_by=actor,
        )


def create_default_roles(sender: Any, **kwargs: Any) -> None:
    """Ensure built-in roles exist after migrations, then grant Admin to superusers."""
    from django.contrib.auth import get_user_model

    from apps.core.models import Role

    for name, description in DEFAULT_ROLES.items():
        Role.objects.get_or_create(name=name, defaults={"description": description})
    UserModel = get_user_model()
    admin_role = Role.objects.get(name="Admin")
    for superuser in UserModel.objects.filter(is_superuser=True).iterator():
        superuser.roles.add(admin_role)
