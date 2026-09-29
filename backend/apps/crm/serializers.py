"""API representations for CRM and sales pipeline records."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.crm.models import Activity, Contact, Deal, Lead


class LeadSerializer(serializers.ModelSerializer[Lead]):
    assigned_to_name = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = [
            "id",
            "company_name",
            "contact_name",
            "email",
            "phone",
            "source",
            "status",
            "estimated_value",
            "notes",
            "assigned_to",
            "assigned_to_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "assigned_to_name"]

    def get_assigned_to_name(self, obj: Lead) -> str:
        if not obj.assigned_to:
            return ""
        return obj.assigned_to.get_full_name() or obj.assigned_to.email


class ContactSerializer(serializers.ModelSerializer[Contact]):
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = Contact
        fields = [
            "id",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "phone",
            "organization",
            "title",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "full_name", "created_at", "updated_at"]


class DealSerializer(serializers.ModelSerializer[Deal]):
    lead_name = serializers.CharField(source="lead.company_name", read_only=True, default="")
    contact_name = serializers.CharField(source="contact.full_name", read_only=True, default="")
    assigned_to_name = serializers.SerializerMethodField()

    class Meta:
        model = Deal
        fields = [
            "id",
            "title",
            "lead",
            "lead_name",
            "contact",
            "contact_name",
            "company_name",
            "stage",
            "expected_value",
            "currency",
            "probability",
            "expected_close_date",
            "assigned_to",
            "assigned_to_name",
            "lost_reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "lead_name",
            "contact_name",
            "assigned_to_name",
            "created_at",
            "updated_at",
        ]

    def get_assigned_to_name(self, obj: Deal) -> str:
        if not obj.assigned_to:
            return ""
        return obj.assigned_to.get_full_name() or obj.assigned_to.email


class DealStageUpdateSerializer(serializers.Serializer[Any]):
    stage = serializers.ChoiceField(choices=Deal.Stage.choices)
    lost_reason = serializers.CharField(required=False, allow_blank=True, default="")
    probability = serializers.IntegerField(
        required=False, min_value=0, max_value=100, allow_null=True, default=None
    )


class ActivitySerializer(serializers.ModelSerializer[Activity]):
    lead_name = serializers.CharField(source="lead.company_name", read_only=True, default="")
    contact_name = serializers.CharField(source="contact.full_name", read_only=True, default="")
    deal_title = serializers.CharField(source="deal.title", read_only=True, default="")
    completed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Activity
        fields = [
            "id",
            "lead",
            "lead_name",
            "contact",
            "contact_name",
            "deal",
            "deal_title",
            "activity_type",
            "title",
            "description",
            "due_date",
            "completed",
            "completed_at",
            "completed_by",
            "completed_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "lead_name",
            "contact_name",
            "deal_title",
            "completed_at",
            "completed_by",
            "completed_by_name",
            "created_at",
            "updated_at",
        ]

    def get_completed_by_name(self, obj: Activity) -> str:
        if not obj.completed_by:
            return ""
        return obj.completed_by.get_full_name() or obj.completed_by.email
