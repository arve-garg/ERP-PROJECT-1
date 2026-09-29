"""CRM business services and domain logic."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.core.models import Notification
from apps.crm.models import Activity, Contact, Deal, Lead

User = get_user_model()

DEFAULT_PROBABILITIES: dict[str, int] = {
    Deal.Stage.NEW: 10,
    Deal.Stage.QUALIFIED: 30,
    Deal.Stage.PROPOSAL: 60,
    Deal.Stage.WON: 100,
    Deal.Stage.LOST: 0,
}


@transaction.atomic
def create_lead(
    *,
    company_name: str,
    contact_name: str = "",
    email: str = "",
    phone: str = "",
    source: str = Lead.Source.WEBSITE,
    status: str = Lead.Status.NEW,
    estimated_value: Decimal = Decimal("0.00"),
    notes: str = "",
    assigned_to: Any = None,
    created_by: Any = None,
) -> Lead:
    """Create a new sales lead."""
    lead = Lead(
        company_name=company_name.strip(),
        contact_name=contact_name.strip(),
        email=email.strip().lower() if email else "",
        phone=phone.strip(),
        source=source,
        status=status,
        estimated_value=estimated_value,
        notes=notes.strip(),
        assigned_to=assigned_to,
        created_by=created_by,
        updated_by=created_by,
    )
    lead.full_clean()
    lead.save()
    return lead


@transaction.atomic
def qualify_lead(
    lead: Lead,
    *,
    actor: Any = None,
    create_deal_opportunity: bool = False,
    deal_title: str = "",
    expected_value: Decimal | None = None,
) -> tuple[Lead, Deal | None]:
    """Mark a lead as qualified and optionally spawn an opportunity deal."""
    lead.status = Lead.Status.QUALIFIED
    lead.updated_by = actor
    lead.save(update_fields=["status", "updated_at", "updated_by"])

    deal: Deal | None = None
    if create_deal_opportunity:
        title = deal_title.strip() or f"{lead.company_name} Opportunity"
        deal = create_deal(
            title=title,
            company_name=lead.company_name,
            lead=lead,
            expected_value=expected_value if expected_value is not None else lead.estimated_value,
            assigned_to=lead.assigned_to,
            created_by=actor,
        )

    return lead, deal


@transaction.atomic
def create_deal(
    *,
    title: str,
    company_name: str,
    lead: Lead | None = None,
    contact: Contact | None = None,
    stage: str = Deal.Stage.NEW,
    expected_value: Decimal = Decimal("0.00"),
    currency: str = "USD",
    probability: int | None = None,
    expected_close_date: date | None = None,
    assigned_to: Any = None,
    lost_reason: str = "",
    created_by: Any = None,
) -> Deal:
    """Create a sales deal in the pipeline."""
    prob = probability if probability is not None else DEFAULT_PROBABILITIES.get(stage, 10)
    deal = Deal(
        title=title.strip(),
        company_name=company_name.strip(),
        lead=lead,
        contact=contact,
        stage=stage,
        expected_value=expected_value,
        currency=currency.upper(),
        probability=prob,
        expected_close_date=expected_close_date,
        assigned_to=assigned_to,
        lost_reason=lost_reason.strip(),
        created_by=created_by,
        updated_by=created_by,
    )
    deal.full_clean()
    deal.save()
    return deal


@transaction.atomic
def update_deal_stage(
    deal: Deal,
    *,
    new_stage: str,
    lost_reason: str = "",
    probability: int | None = None,
    actor: Any = None,
) -> Deal:
    """Transition deal through sales stages with probability and audit updating."""
    if new_stage not in Deal.Stage.values:
        raise ValueError(f"Invalid deal stage: {new_stage}")

    deal.stage = new_stage
    deal.updated_by = actor

    if new_stage == Deal.Stage.LOST:
        deal.lost_reason = lost_reason.strip()
    elif new_stage == Deal.Stage.WON:
        deal.lost_reason = ""

    if probability is not None:
        deal.probability = probability
    else:
        deal.probability = DEFAULT_PROBABILITIES.get(new_stage, deal.probability)

    deal.full_clean()
    deal.save(update_fields=["stage", "probability", "lost_reason", "updated_at", "updated_by"])
    return deal


@transaction.atomic
def create_activity(
    *,
    activity_type: str,
    title: str,
    description: str = "",
    due_date: datetime | None = None,
    lead: Lead | None = None,
    contact: Contact | None = None,
    deal: Deal | None = None,
    created_by: Any = None,
) -> Activity:
    """Log an interaction or schedule a follow-up action."""
    activity = Activity(
        activity_type=activity_type,
        title=title.strip(),
        description=description.strip(),
        due_date=due_date,
        lead=lead,
        contact=contact,
        deal=deal,
        created_by=created_by,
        updated_by=created_by,
    )
    activity.full_clean()
    activity.save()
    return activity


@transaction.atomic
def complete_activity(
    activity: Activity,
    *,
    actor: Any = None,
) -> Activity:
    """Mark an activity as completed."""
    activity.completed = True
    activity.completed_at = timezone.now()
    activity.completed_by = actor
    activity.updated_by = actor
    activity.save(
        update_fields=[
            "completed",
            "completed_at",
            "completed_by",
            "updated_at",
            "updated_by",
        ]
    )
    return activity


def send_activity_reminders() -> int:
    """Find open activities due today or overdue and send in-app notifications to assignees."""
    now = timezone.now()
    pending = Activity.objects.filter(
        completed=False,
        due_date__lte=now,
        is_deleted=False,
    ).select_related("deal__assigned_to", "lead__assigned_to")

    count = 0
    for act in pending:
        recipient = None
        if act.deal and act.deal.assigned_to:
            recipient = act.deal.assigned_to
        elif act.lead and act.lead.assigned_to:
            recipient = act.lead.assigned_to
        elif act.created_by:
            recipient = act.created_by

        if recipient:
            scheduled_time = act.due_date.strftime("%Y-%m-%d %H:%M") if act.due_date else "today"
            Notification.objects.create(
                recipient=recipient,
                category="crm",
                title=f"CRM Reminder: {act.title}",
                body=f"Activity '{act.title}' was scheduled for {scheduled_time}.",
                target_url="/crm",
                created_by=recipient,
            )
            count += 1
    return count
