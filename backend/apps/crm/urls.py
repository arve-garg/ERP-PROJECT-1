"""CRM routing for leads, contacts, deals, and activities."""

from rest_framework.routers import DefaultRouter

from apps.crm.views import ActivityViewSet, ContactViewSet, DealViewSet, LeadViewSet

router = DefaultRouter()
router.register("leads", LeadViewSet, basename="lead")
router.register("contacts", ContactViewSet, basename="contact")
router.register("deals", DealViewSet, basename="deal")
router.register("activities", ActivityViewSet, basename="activity")

urlpatterns = router.urls
