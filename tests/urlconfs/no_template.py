from django.urls import path

from . import views

urlpatterns = [path("x/", views.NoTemplate.as_view(), name="no-template")]
