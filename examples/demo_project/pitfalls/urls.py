from django.urls import path

from . import views

app_name = "pitfalls"

urlpatterns = [
    path("", views.index, name="index"),
    path("details/", views.details, name="details"),
    path("details-page-only/", views.details_page_only, name="details_page_only"),
    path("notes/naive/", views.NoteCreateNaive.as_view(), name="note_naive"),
    path("notes/", views.NoteCreate.as_view(), name="note_fixed"),
    path("events/", views.events_frame, name="events_frame"),
    path("ping/", views.ping, name="ping"),
    path("hit/<slug:token>/<slug:name>/", views.hit, name="hit"),
    path("save/", views.save, name="save"),
]
