from django.urls import include, path

from . import views

urlpatterns = [
    path("top/", views.GoodList.as_view(), name="top"),
    path("shop/", include("tests.urlconfs.inner", namespace="shop")),
    path("plain/", include("tests.urlconfs.good")),
]
