"""URL routing for admin, authentication, and the versioned API."""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)
from rest_framework.permissions import AllowAny
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from apps.core.api.auth import (
    LoginView,
    LogoutView,
    PasswordResetConfirmView,
    PasswordResetView,
    TOTPConfirmView,
    TOTPDisableView,
    TOTPSetupView,
)
from apps.core.api.views import (
    ActivityFeedView,
    AuditLogViewSet,
    CompanySettingViewSet,
    NotificationViewSet,
    RoleViewSet,
    SavedFilterViewSet,
    SearchView,
    UserViewSet,
)

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")
router.register("roles", RoleViewSet, basename="role")
router.register("audit-logs", AuditLogViewSet, basename="audit-log")
router.register("notifications", NotificationViewSet, basename="notification")
router.register("company-settings", CompanySettingViewSet, basename="company-setting")
router.register("saved-filters", SavedFilterViewSet, basename="saved-filter")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("api/schema/", SpectacularAPIView.as_view(permission_classes=[AllowAny]), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema", permission_classes=[AllowAny]),
        name="swagger-ui",
    ),
    path("api/v1/auth/login/", LoginView.as_view(), name="token_obtain_pair"),
    path("api/v1/auth/logout/", LogoutView.as_view(), name="token_blacklist"),
    path("api/v1/auth/password/reset/", PasswordResetView.as_view(), name="password_reset"),
    path(
        "api/v1/auth/password/reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path("api/v1/auth/2fa/setup/", TOTPSetupView.as_view(), name="totp_setup"),
    path("api/v1/auth/2fa/confirm/", TOTPConfirmView.as_view(), name="totp_confirm"),
    path("api/v1/auth/2fa/disable/", TOTPDisableView.as_view(), name="totp_disable"),
    path(
        "api/v1/auth/token/refresh/",
        TokenRefreshView.as_view(permission_classes=[AllowAny], authentication_classes=[]),
        name="token_refresh",
    ),
    path("api/v1/", include(router.urls)),
    path("api/v1/hr/", include("apps.hr.urls")),
    path("api/v1/projects/", include("apps.projects.urls")),
    path("api/v1/activity-feed/", ActivityFeedView.as_view(), name="activity-feed"),
    path("api/v1/search/", SearchView.as_view(), name="global-search"),
]
