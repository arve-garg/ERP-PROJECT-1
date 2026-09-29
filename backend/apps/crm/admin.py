"""Django admin configuration for CRM models."""

from django.contrib import admin

from apps.crm.models import Activity, Contact, Deal, Lead


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "company_name",
        "contact_name",
        "status",
        "source",
        "estimated_value",
        "assigned_to",
    )
    list_filter = ("status", "source", "is_deleted")
    search_fields = ("company_name", "contact_name", "email", "phone")


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("first_name", "last_name", "organization", "email", "phone")
    search_fields = ("first_name", "last_name", "organization", "email")


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "title",
        "company_name",
        "stage",
        "expected_value",
        "currency",
        "probability",
        "assigned_to",
    )
    list_filter = ("stage", "currency", "is_deleted")
    search_fields = ("title", "company_name")


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("title", "activity_type", "due_date", "completed", "completed_at")
    list_filter = ("activity_type", "completed", "is_deleted")
    search_fields = ("title", "description")
