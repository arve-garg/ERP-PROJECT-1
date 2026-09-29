"""Views and endpoints for CRM leads, contacts, deals, and activities."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db.models import Count, Sum
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.crm.models import Activity, Contact, Deal, Lead
from apps.crm.permissions import IsSalesOrAdmin
from apps.crm.serializers import (
    ActivitySerializer,
    ContactSerializer,
    DealSerializer,
    DealStageUpdateSerializer,
    LeadSerializer,
)
from apps.crm.services import complete_activity, qualify_lead, update_deal_stage


class LeadViewSet(viewsets.ModelViewSet[Lead]):
    queryset = Lead.objects.filter(is_deleted=False).select_related("assigned_to")
    serializer_class = LeadSerializer
    permission_classes = [IsSalesOrAdmin]
    filterset_fields = ["status", "source", "assigned_to"]
    search_fields = ["company_name", "contact_name", "email", "phone"]
    ordering_fields = ["created_at", "company_name", "estimated_value", "status"]
    ordering = ["-created_at"]

    def perform_create(self, serializer: Any) -> None:
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer: Any) -> None:
        serializer.save(updated_by=self.request.user)

    @extend_schema(request=None, responses=LeadSerializer)
    @action(detail=True, methods=["post"])
    def qualify(self, request: Request, pk: str | None = None) -> Response:
        lead = self.get_object()
        create_deal_opp = request.data.get("create_deal", False)
        deal_title = request.data.get("deal_title", "")
        updated_lead, deal = qualify_lead(
            lead,
            actor=request.user,
            create_deal_opportunity=create_deal_opp,
            deal_title=deal_title,
        )
        data = LeadSerializer(updated_lead).data
        if deal:
            data["created_deal_id"] = deal.id
        return Response(data, status=status.HTTP_200_OK)


class ContactViewSet(viewsets.ModelViewSet[Contact]):
    queryset = Contact.objects.filter(is_deleted=False)
    serializer_class = ContactSerializer
    permission_classes = [IsSalesOrAdmin]
    search_fields = ["first_name", "last_name", "email", "phone", "organization"]
    ordering_fields = ["first_name", "last_name", "organization", "created_at"]
    ordering = ["first_name", "last_name"]

    def perform_create(self, serializer: Any) -> None:
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer: Any) -> None:
        serializer.save(updated_by=self.request.user)


class DealViewSet(viewsets.ModelViewSet[Deal]):
    queryset = Deal.objects.filter(is_deleted=False).select_related(
        "lead", "contact", "assigned_to"
    )
    serializer_class = DealSerializer
    permission_classes = [IsSalesOrAdmin]
    filterset_fields = ["stage", "assigned_to", "currency"]
    search_fields = ["title", "company_name"]
    ordering_fields = ["created_at", "expected_value", "expected_close_date", "stage"]
    ordering = ["-created_at"]

    def perform_create(self, serializer: Any) -> None:
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer: Any) -> None:
        serializer.save(updated_by=self.request.user)

    @extend_schema(request=DealStageUpdateSerializer, responses=DealSerializer)
    @action(detail=True, methods=["post"], url_path="stage")
    def update_stage(self, request: Request, pk: str | None = None) -> Response:
        deal = self.get_object()
        serializer = DealStageUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated_deal = update_deal_stage(
            deal,
            new_stage=serializer.validated_data["stage"],
            lost_reason=serializer.validated_data.get("lost_reason", ""),
            probability=serializer.validated_data.get("probability"),
            actor=request.user,
        )
        return Response(DealSerializer(updated_deal).data, status=status.HTTP_200_OK)

    @extend_schema(responses={200: dict})
    @action(detail=False, methods=["get"], url_path="pipeline-summary")
    def pipeline_summary(self, request: Request) -> Response:
        qs = self.filter_queryset(self.get_queryset())
        summary_rows = (
            qs.values("stage")
            .annotate(
                count=Count("id"),
                total_value=Sum("expected_value"),
            )
            .order_by("stage")
        )
        stages_data = {
            stage: {"count": 0, "total_value": Decimal("0.00")} for stage, _ in Deal.Stage.choices
        }
        for row in summary_rows:
            stg = row["stage"]
            if stg in stages_data:
                stages_data[stg] = {
                    "count": row["count"],
                    "total_value": row["total_value"] or Decimal("0.00"),
                }
        return Response(stages_data, status=status.HTTP_200_OK)


class ActivityViewSet(viewsets.ModelViewSet[Activity]):
    queryset = Activity.objects.filter(is_deleted=False).select_related(
        "lead", "contact", "deal", "completed_by"
    )
    serializer_class = ActivitySerializer
    permission_classes = [IsSalesOrAdmin]
    filterset_fields = ["activity_type", "completed", "deal", "lead", "contact"]
    search_fields = ["title", "description"]
    ordering_fields = ["due_date", "completed", "created_at"]
    ordering = ["completed", "due_date", "-created_at"]

    def perform_create(self, serializer: Any) -> None:
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer: Any) -> None:
        serializer.save(updated_by=self.request.user)

    @extend_schema(request=None, responses=ActivitySerializer)
    @action(detail=True, methods=["post"])
    def complete(self, request: Request, pk: str | None = None) -> Response:
        activity = self.get_object()
        updated_activity = complete_activity(activity, actor=request.user)
        return Response(ActivitySerializer(updated_activity).data, status=status.HTTP_200_OK)
