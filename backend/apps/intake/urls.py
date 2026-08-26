from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("batches", views.ImportBatchViewSet, basename="batch")
router.register("students", views.StagedStudentViewSet, basename="student")
router.register("mapping-profiles", views.MappingProfileViewSet, basename="mappingprofile")

urlpatterns = [
    path("", include(router.urls)),
    path("canonical-fields/", views.CanonicalFieldsView.as_view(), name="canonical-fields"),
]
