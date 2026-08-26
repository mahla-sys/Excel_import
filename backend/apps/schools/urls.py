from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("operators", views.OperatorViewSet, basename="operator")
router.register("", views.SchoolViewSet, basename="school")

urlpatterns = router.urls
