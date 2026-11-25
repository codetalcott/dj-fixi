"""One list of patterns included under two namespaces, as NAV routes its API under api:, api:1: and api:2:."""

from django.urls import include, path

from . import views

api = [path("", include([path("thing/", views.GoodList.as_view(), name="thing")]))]

urlpatterns = [
    path("v1/", include((api, "api"), namespace="v1")),
    path("v2/", include((api, "api"), namespace="v2")),
]
