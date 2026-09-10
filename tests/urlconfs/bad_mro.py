from django.urls import path

from . import views

urlpatterns = [
    path("groups/", views.BadList.as_view(), name="bad-list"),
    path("groups/add/", views.BadCreate.as_view(), name="bad-create"),
    path("groups/q/", views.BadQueryMixins.as_view(), name="bad-query"),
]
