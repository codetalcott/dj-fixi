from django.urls import path

from . import views

urlpatterns = [
    path("list/", views.DerivedList.as_view(), name="derived-list"),
    path("create/", views.DerivedCreate.as_view(), name="derived-create"),
    path("delete/<int:pk>/", views.DerivedDelete.as_view(), name="derived-delete"),
    # The partial is written down at the URLconf; RoutedView.attr sees initkwargs.
    path("kw/", views.NoPartialAnywhere.as_view(partial_template=views.PARTIAL), name="derived-kw"),
]
