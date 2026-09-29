"""Core identity, authorization, audit, and tenant configuration models."""

from __future__ import annotations

from typing import Any, ClassVar

from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class AuditedModel(models.Model):
    """Base for application records with actor tracking and soft deletion."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_created",
        on_delete=models.SET_NULL,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_updated",
        on_delete=models.SET_NULL,
    )
    is_deleted = models.BooleanField(default=False, db_index=True)

    class Meta:
        abstract = True

    def delete(
        self, using: str | None = None, keep_parents: bool = False
    ) -> tuple[int, dict[str, int]]:
        """Mark the record deleted rather than removing its history."""
        self.is_deleted = True
        self.save(using=using, update_fields=["is_deleted", "updated_at", "updated_by"])
        return 1, {self._meta.label: 1}

    def hard_delete(self, using: str | None = None) -> tuple[int, dict[str, int]]:
        """Permanently remove a record when explicitly required."""
        return super().delete(using=using)


class UserManager(BaseUserManager["User"]):
    """Email-based user manager."""

    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra_fields: Any) -> User:
        if not email:
            raise ValueError("An email address is required.")
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields: Any) -> User:
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(
        self, email: str, password: str | None = None, **extra_fields: Any
    ) -> User:
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if extra_fields.get("is_staff") is not True or extra_fields.get("is_superuser") is not True:
            raise ValueError("A superuser must have is_staff=True and is_superuser=True.")
        user = self._create_user(email, password, **extra_fields)
        admin_role = Role.objects.filter(name="Admin").first()
        if admin_role is not None:
            user.roles.add(admin_role)
        return user


class User(AbstractUser):
    """Custom email-login user with explicit ERP role assignments."""

    username = None  # type: ignore[assignment]
    email = models.EmailField(unique=True)
    roles: models.ManyToManyField[Role, Any] = models.ManyToManyField(
        "Role", related_name="users", blank=True
    )
    is_deleted = models.BooleanField(default=False, db_index=True)
    totp_required = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="users_created"
    )
    updated_by = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="users_updated"
    )
    USERNAME_FIELD: str = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = []
    objects: ClassVar[UserManager] = UserManager()  # type: ignore[assignment]

    class Meta:
        ordering = ["email"]

    def __str__(self) -> str:
        return self.email

    def soft_delete(self) -> None:
        self.is_deleted = True
        self.is_active = False
        self.save(update_fields=["is_deleted", "is_active", "updated_by", "updated_at"])


class Role(AuditedModel):
    """Named role used by API permissions."""

    name = models.CharField(max_length=40, unique=True)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class AuditLog(models.Model):
    """Append-only record of changes to identity and audited application data."""

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_events",
    )
    action = models.CharField(max_length=20)
    model_label = models.CharField(max_length=100, db_index=True)
    object_id = models.CharField(max_length=64, db_index=True)
    changes = models.JSONField(default=dict)
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-occurred_at", "-id"]
        indexes = [models.Index(fields=["model_label", "object_id"])]

    def __str__(self) -> str:
        return f"{self.action} {self.model_label} {self.object_id}"


class Notification(AuditedModel):
    """In-app notification addressed to one user."""

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        db_index=True,
    )
    category = models.CharField(max_length=40, default="general")
    title = models.CharField(max_length=160)
    body = models.TextField(blank=True)
    target_url = models.CharField(max_length=500, blank=True)
    read_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "read_at", "-created_at"])]

    @property
    def is_read(self) -> bool:
        return self.read_at is not None


class CompanySetting(AuditedModel):
    """Company-level typed setting stored as JSON."""

    key = models.CharField(max_length=100, unique=True)
    value = models.JSONField()
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["key"]

    def __str__(self) -> str:
        return self.key


class SavedFilter(AuditedModel):
    """Reusable, optionally shared list filter owned by a user."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_filters"
    )
    module = models.CharField(max_length=60)
    name = models.CharField(max_length=100)
    definition = models.JSONField(default=dict)
    is_shared = models.BooleanField(default=False)

    class Meta:
        ordering = ["module", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "module", "name"], name="unique_saved_filter_per_owner"
            )
        ]


class ActivityFeedItem(AuditedModel):
    """Human-readable activity associated with a user action."""

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="activity_items",
    )
    verb = models.CharField(max_length=100)
    target_type = models.CharField(max_length=100, blank=True)
    target_id = models.CharField(max_length=64, blank=True)
    metadata = models.JSONField(default=dict)

    class Meta:
        ordering = ["-created_at"]
