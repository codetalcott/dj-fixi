"""URL patterns for products app"""

from django.urls import path

from . import views, views_backend_driven

urlpatterns = [
    path("", views.ProductListView.as_view(), name="product_list"),
    path("simple/", views.product_list_simple, name="product_list_simple"),
    path("create/", views.ProductCreateView.as_view(), name="product_create"),
    path("<int:pk>/edit/", views.ProductUpdateView.as_view(), name="product_update"),
    path("<int:pk>/delete/", views.ProductDeleteView.as_view(), name="product_delete"),
    # Backend-driven patterns
    path(
        "backend-driven/",
        views_backend_driven.ProductListBackendDriven.as_view(),
        name="product_list_backend",
    ),
    path(
        "backend-driven/<int:pk>/row/",
        views_backend_driven.ProductRowView.as_view(),
        name="product_update_row",
    ),
    path(
        "backend-driven/<int:pk>/delete/",
        views_backend_driven.ProductDeleteBackendDriven.as_view(),
        name="product_delete_backend",
    ),
]
