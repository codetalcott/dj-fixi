from django.urls import path

from . import views

urlpatterns = [
    path("groups/", views.GoodList.as_view(), name="good-list"),
    path("groups/add/", views.GoodCreate.as_view(), name="good-create"),
    path("about/", views.GoodTemplate.as_view(), name="good-template"),
    path("fbv/", views.good_fbv, name="good-fbv"),
]
