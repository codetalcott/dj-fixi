from django.urls import path

from . import views

urlpatterns = [path("groups/", views.UserShadow.as_view(), name="shadow")]
