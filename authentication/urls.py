

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import register_view, login_view, logout_view, me_view

urlpatterns = [
    path("register", register_view, name="auth-register"),
    path("login", login_view, name="auth-login"),
    path("logout", logout_view, name="auth-logout"),
    path("refresh", TokenRefreshView.as_view(), name="auth-token-refresh"),
    path("me", me_view, name="auth-me"),
]
