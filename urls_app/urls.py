

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import ShortenedURLViewSet, redirect_view

# ── API router ────────────────────────────────────────────────────────────────
router = DefaultRouter()


router.register(r"shorten", ShortenedURLViewSet, basename="shorten")
router.register(r"urls", ShortenedURLViewSet, basename="urls")

urlpatterns = [
    path("", include(router.urls)),

    
    path("r/<str:short_code>/", redirect_view, name="redirect"),
]
