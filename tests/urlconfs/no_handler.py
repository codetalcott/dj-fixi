from django.urls import path

from . import views

urlpatterns = [path("nope/", views.NoHandler.as_view(), name="no-handler")]
