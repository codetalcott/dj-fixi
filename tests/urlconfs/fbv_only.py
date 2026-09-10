from django.urls import path

from . import views

urlpatterns = [
    path("fbv/", views.good_fbv, name="fbv"),
    path("plain/", views.plain_fbv, name="plain"),
]
