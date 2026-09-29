"""Comprehensive tests for CRM models, services, and API endpoints."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.core.models import Notification, Role, User
from apps.crm.models import Activity, Contact, Deal, Lead
from apps.crm.services import (
    complete_activity,
    create_activity,
    create_deal,
    create_lead,
    qualify_lead,
    send_activity_reminders,
    update_deal_stage,
)


class CrmTests(APITestCase):
    def setUp(self) -> None:
        self.admin_role, _ = Role.objects.get_or_create(name="Admin")
        self.sales_role, _ = Role.objects.get_or_create(name="Sales")
        self.employee_role, _ = Role.objects.get_or_create(name="Employee")

        self.sales_user = User.objects.create_user(
            email="sales@example.com",
            password="SalesPassword123!",
            first_name="Sam",
            last_name="Sales",
        )
        self.sales_user.roles.add(self.sales_role)

        self.admin_user = User.objects.create_user(
            email="admin@example.com",
            password="AdminPassword123!",
            first_name="Ada",
            last_name="Admin",
        )
        self.admin_user.roles.add(self.admin_role)

        self.employee_user = User.objects.create_user(
            email="dev@example.com",
            password="DevPassword123!",
            first_name="Dan",
            last_name="Developer",
        )
        self.employee_user.roles.add(self.employee_role)

    # 1. Model & Validation Tests
    def test_lead_model_creation_and_defaults(self) -> None:
        lead = Lead.objects.create(
            company_name="Acme Corp",
            contact_name="Alice Smith",
            email="alice@acme.com",
            phone="+1234567890",
            source=Lead.Source.WEBSITE,
            estimated_value=Decimal("15000.00"),
        )
        self.assertEqual(lead.status, Lead.Status.NEW)
        self.assertIn("Acme Corp", str(lead))
        self.assertEqual(lead.estimated_value, Decimal("15000.00"))

    def test_contact_model_full_name(self) -> None:
        contact = Contact.objects.create(
            first_name="Bob",
            last_name="Johnson",
            email="bob@acme.com",
            organization="Acme Corp",
        )
        self.assertEqual(contact.full_name, "Bob Johnson")
        self.assertIn("Bob Johnson - Acme Corp", str(contact))

    def test_deal_validation_currency_and_probability(self) -> None:
        deal = Deal(
            title="Website Redesign",
            company_name="Acme Corp",
            currency="usd",  # should be uppercase
            probability=110,  # exceeds 100
        )
        with self.assertRaises(ValidationError):
            deal.full_clean()

    # 2. Service Unit Tests
    def test_create_and_qualify_lead_service(self) -> None:
        lead = create_lead(
            company_name="Beta Inc",
            contact_name="Barbara",
            email="barbara@beta.com",
            estimated_value=Decimal("25000.00"),
            assigned_to=self.sales_user,
            created_by=self.sales_user,
        )
        self.assertEqual(lead.status, Lead.Status.NEW)
        self.assertEqual(lead.created_by, self.sales_user)

        updated_lead, deal = qualify_lead(
            lead,
            actor=self.sales_user,
            create_deal_opportunity=True,
            deal_title="Beta ERP Project",
        )
        self.assertEqual(updated_lead.status, Lead.Status.QUALIFIED)
        self.assertIsNotNone(deal)
        assert deal is not None
        self.assertEqual(deal.title, "Beta ERP Project")
        self.assertEqual(deal.company_name, "Beta Inc")
        self.assertEqual(deal.expected_value, Decimal("25000.00"))
        self.assertEqual(deal.stage, Deal.Stage.NEW)
        self.assertEqual(deal.probability, 10)

    def test_deal_stage_transition_service(self) -> None:
        deal = create_deal(
            title="Mobile App",
            company_name="Delta LLC",
            expected_value=Decimal("50000.00"),
            created_by=self.sales_user,
        )
        self.assertEqual(deal.stage, Deal.Stage.NEW)
        self.assertEqual(deal.probability, 10)

        # Transition to Proposal
        deal = update_deal_stage(deal, new_stage=Deal.Stage.PROPOSAL, actor=self.sales_user)
        self.assertEqual(deal.stage, Deal.Stage.PROPOSAL)
        self.assertEqual(deal.probability, 60)

        # Transition to Lost with reason
        deal = update_deal_stage(
            deal,
            new_stage=Deal.Stage.LOST,
            lost_reason="Budget cuts by client",
            actor=self.sales_user,
        )
        self.assertEqual(deal.stage, Deal.Stage.LOST)
        self.assertEqual(deal.probability, 0)
        self.assertEqual(deal.lost_reason, "Budget cuts by client")

        # Invalid stage raises ValueError
        with self.assertRaises(ValueError):
            update_deal_stage(deal, new_stage="invalid_stage", actor=self.sales_user)

    def test_activity_lifecycle_and_reminders(self) -> None:
        deal = create_deal(
            title="Cloud Migration",
            company_name="Echo Tech",
            assigned_to=self.sales_user,
            created_by=self.sales_user,
        )
        act = create_activity(
            activity_type=Activity.ActivityType.CALL,
            title="Introductory discovery call",
            due_date=timezone.now() - timedelta(hours=2),
            deal=deal,
            created_by=self.sales_user,
        )
        self.assertFalse(act.completed)
        self.assertIn("Introductory discovery call", str(act))

        # Check notification reminders
        reminder_count = send_activity_reminders()
        self.assertGreaterEqual(reminder_count, 1)
        notif = Notification.objects.filter(recipient=self.sales_user, category="crm").first()
        self.assertIsNotNone(notif)
        assert notif is not None
        self.assertIn("Introductory discovery call", notif.body)

        # Complete activity
        completed_act = complete_activity(act, actor=self.sales_user)
        self.assertTrue(completed_act.completed)
        self.assertIsNotNone(completed_act.completed_at)
        self.assertEqual(completed_act.completed_by, self.sales_user)

    # 3. RBAC & API Endpoint Tests
    def test_unauthenticated_request_rejected(self) -> None:
        response = self.client.get("/api/v1/crm/leads/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthorized_role_rejected(self) -> None:
        self.client.force_authenticate(user=self.employee_user)
        response = self.client.get("/api/v1/crm/leads/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_sales_and_admin_authorized(self) -> None:
        # Sales role
        self.client.force_authenticate(user=self.sales_user)
        res_sales = self.client.get("/api/v1/crm/leads/")
        self.assertEqual(res_sales.status_code, status.HTTP_200_OK)

        # Admin role
        self.client.force_authenticate(user=self.admin_user)
        res_admin = self.client.get("/api/v1/crm/leads/")
        self.assertEqual(res_admin.status_code, status.HTTP_200_OK)

    def test_lead_crud_and_qualify_action(self) -> None:
        self.client.force_authenticate(user=self.sales_user)
        # Create lead
        create_payload = {
            "company_name": "Globex Corp",
            "contact_name": "Hank Scorpio",
            "email": "hank@globex.com",
            "phone": "+1999888777",
            "source": "referral",
            "estimated_value": "45000.00",
            "notes": "Interested in turnkey solutions.",
        }
        create_res = self.client.post("/api/v1/crm/leads/", create_payload, format="json")
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        lead_id = create_res.data["id"]

        # Qualify lead with deal opportunity
        qualify_res = self.client.post(
            f"/api/v1/crm/leads/{lead_id}/qualify/",
            {"create_deal": True, "deal_title": "Globex Infrastructure Deal"},
            format="json",
        )
        self.assertEqual(qualify_res.status_code, status.HTTP_200_OK)
        self.assertEqual(qualify_res.data["status"], "qualified")
        self.assertIn("created_deal_id", qualify_res.data)

    def test_contact_crud(self) -> None:
        self.client.force_authenticate(user=self.sales_user)
        payload = {
            "first_name": "Carol",
            "last_name": "Danvers",
            "email": "carol@marvel.org",
            "phone": "+1231231234",
            "organization": "Marvel Corp",
            "title": "Director",
        }
        res = self.client.post("/api/v1/crm/contacts/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["full_name"], "Carol Danvers")

        # Search contacts
        search_res = self.client.get("/api/v1/crm/contacts/?search=Danvers")
        self.assertEqual(search_res.status_code, status.HTTP_200_OK)
        self.assertEqual(search_res.data["count"], 1)

    def test_deal_kanban_stage_transitions_and_summary(self) -> None:
        self.client.force_authenticate(user=self.sales_user)
        # Create deals across stages
        deal1 = Deal.objects.create(
            title="Deal 1",
            company_name="Company 1",
            stage=Deal.Stage.NEW,
            expected_value=Decimal("10000.00"),
        )
        Deal.objects.create(
            title="Deal 2",
            company_name="Company 2",
            stage=Deal.Stage.WON,
            expected_value=Decimal("30000.00"),
        )

        # Pipeline summary
        summary_res = self.client.get("/api/v1/crm/deals/pipeline-summary/")
        self.assertEqual(summary_res.status_code, status.HTTP_200_OK)
        self.assertEqual(summary_res.data["new"]["count"], 1)
        self.assertEqual(Decimal(str(summary_res.data["new"]["total_value"])), Decimal("10000.00"))
        self.assertEqual(summary_res.data["won"]["count"], 1)
        self.assertEqual(Decimal(str(summary_res.data["won"]["total_value"])), Decimal("30000.00"))

        # Transition stage via API
        stage_res = self.client.post(
            f"/api/v1/crm/deals/{deal1.id}/stage/",
            {"stage": "won"},
            format="json",
        )
        self.assertEqual(stage_res.status_code, status.HTTP_200_OK)
        self.assertEqual(stage_res.data["stage"], "won")
        self.assertEqual(stage_res.data["probability"], 100)

    def test_activity_crud_and_complete_action(self) -> None:
        self.client.force_authenticate(user=self.sales_user)
        act = Activity.objects.create(
            activity_type=Activity.ActivityType.MEETING,
            title="Product Demo",
            due_date=timezone.now() + timedelta(days=1),
        )

        res = self.client.post(f"/api/v1/crm/activities/{act.id}/complete/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["completed"])
        self.assertEqual(res.data["completed_by_name"], "Sam Sales")
