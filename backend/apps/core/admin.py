"""Admin registrations for platform configuration and identity."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.http import HttpRequest

from apps.core.models import AuditLog, CompanySetting, Notification, Role, SavedFilter, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):  # type: ignore[type-arg]
    ordering = ["email"]
    list_display = ["email", "first_name", "last_name", "is_staff", "is_active", "is_deleted"]
    search_fields = ["email", "first_name", "last_name"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                    "roles",
                )
            },
        ),
        ("Security", {"fields": ("totp_required",)}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),)
    filter_horizontal = ["groups", "user_permissions", "roles"]


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["name", "description"]
    search_fields = ["name"]


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["occurred_at", "actor", "action", "model_label", "object_id"]
    list_filter = ["action", "model_label"]
    readonly_fields = ["actor", "action", "model_label", "object_id", "changes", "occurred_at"]

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: AuditLog | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: AuditLog | None = None) -> bool:
        return False


admin.site.register([CompanySetting, Notification, SavedFilter])
