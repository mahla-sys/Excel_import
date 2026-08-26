from django.conf import settings
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from apps.accounts.account_views import ChangePasswordView
from apps.intake import admin_views


def health(_request):
    """Lightweight health check (no sensitive data)."""
    return JsonResponse({"status": "ok"})


api_v1 = [
    path("auth/", include("apps.accounts.urls")),
    path("auth/change-password/", ChangePasswordView.as_view()),
    path("schools/", include("apps.schools.urls")),
    path("intake/", include("apps.intake.urls")),
    # Dashboard / admin endpoints
    path("dashboard/", admin_views.DashboardView.as_view()),
    path("admin/schools/", admin_views.SchoolListCreateView.as_view()),
    path("admin/schools/<int:pk>/", admin_views.SchoolDetailView.as_view()),
    path("admin/operators/", admin_views.OperatorListCreateView.as_view()),
    path("admin/operators/<int:pk>/", admin_views.OperatorDetailView.as_view()),
    path("admin/audit-log/", admin_views.AuditLogView.as_view()),
]

# Interactive API docs are a developer convenience and are only enabled
# when DEBUG is on. In production they are not registered at all so the
# API surface cannot be enumerated without authentication.
if settings.DEBUG:
    api_v1.extend([
        path("schema/", SpectacularAPIView.as_view(), name="schema"),
        path("docs/", SpectacularSwaggerView.as_view(url_name="v1:schema"), name="docs"),
        path("redoc/", SpectacularRedocView.as_view(url_name="v1:schema"), name="redoc"),
    ])

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz/", health, name="health"),
    path("api/v1/", include((api_v1, "api"), namespace="v1")),
]
