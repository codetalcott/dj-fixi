"""A URLconf that includes itself: the walk must still end."""

from django.urls import include, path

from . import views

urlpatterns = [
    path("top/", views.GoodList.as_view(), name="top"),
    path("again/", include("tests.urlconfs.recursive")),
]
