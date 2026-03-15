

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),

    # Authentication: register, login, logout, token refresh
    path("api/auth/", include("authentication.urls")),

    # URL management: shorten, CRUD, analytics
    path("api/", include("urls_app.urls")),
]
