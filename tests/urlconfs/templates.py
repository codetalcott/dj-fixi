from django.urls import path

from . import views

urlpatterns = [
    path("typo/", views.MissingPartial.as_view(), name="typo"),
    path("nopartial/", views.NoPartialAnywhere.as_view(), name="nopartial"),
    path("hash/", views.MissingHashPartial.as_view(), name="hash"),
]
