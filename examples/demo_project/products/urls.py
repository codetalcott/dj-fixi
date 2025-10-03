"""URL patterns for products app"""

from django.urls import path

from . import views

urlpatterns = [
    path("", views.ProductListView.as_view(), name="product_list"),
    path("simple/", views.product_list_simple, name="product_list_simple"),
    path("create/", views.ProductCreateView.as_view(), name="product_create"),
    path("<int:pk>/edit/", views.ProductUpdateView.as_view(), name="product_update"),
    path("<int:pk>/delete/", views.ProductDeleteView.as_view(), name="product_delete"),
]
