from django.urls import path

from . import views

urlpatterns = [
    path("list/", views.NoPartialList.as_view(), name="np-list"),
    path("create/", views.NoPartialCreate.as_view(), name="np-create"),
    path("delete/<int:pk>/", views.NoPartialDelete.as_view(), name="np-delete"),
    # The partial is written down at the URLconf; RoutedView.attr sees initkwargs.
    path("kw/", views.NoPartialAnywhere.as_view(partial_template=views.PARTIAL), name="np-kw"),
]
