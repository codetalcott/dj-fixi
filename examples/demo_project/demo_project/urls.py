"""URL configuration for demo_project"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("pitfalls/", include("pitfalls.urls")),
    path("", include("products.urls")),
]
