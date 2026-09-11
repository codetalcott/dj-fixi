"""Product views demonstrating dj-fixi usage"""

from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from dj_fixi.mixins import ContextPersistenceMixin, FxResponseMixin, OptimizedQueryMixin
from dj_fixi.shortcuts import render_fx
from dj_fixi.views import FxView

from .models import Product


class ProductListView(ContextPersistenceMixin, OptimizedQueryMixin, FxView, ListView):
    """
    List products with automatic fragment serving for Fixi requests.

    Demonstrates:
    - FxView for automatic template selection
    - ContextPersistenceMixin for filter/sort state
    - OptimizedQueryMixin for query optimization
    """

    model = Product
    template_name = "products/list.html"
    partial_template = "products/list_partial.html"
    context_object_name = "products"
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()
        # Add search functionality
        search = self.request.GET.get("q")
        if search:
            queryset = queryset.filter(name__icontains=search)
        return queryset


class ProductCreateView(FxResponseMixin, CreateView):
    """
    Create product with Fixi form handling.

    Demonstrates:
    - FxResponseMixin for automatic fragment responses
    - Form validation with Fixi
    """

    model = Product
    template_name = "products/form.html"
    partial_template = "products/form_partial.html"
    fields = ["name", "description", "price", "stock", "is_active"]
    success_url = reverse_lazy("product_list")


class ProductUpdateView(FxResponseMixin, UpdateView):
    """Update product with Fixi integration"""

    model = Product
    template_name = "products/form.html"
    partial_template = "products/form_partial.html"
    fields = ["name", "description", "price", "stock", "is_active"]
    success_url = reverse_lazy("product_list")


class ProductDeleteView(FxResponseMixin, DeleteView):
    """Delete product with Fixi confirmation"""

    model = Product
    template_name = "products/confirm_delete.html"
    success_url = reverse_lazy("product_list")


def product_list_simple(request):
    """
    Simple function-based view using render_fx shortcut.

    Demonstrates:
    - render_fx() for automatic template selection
    """
    products = Product.objects.all()

    # Search functionality
    search = request.GET.get("q")
    if search:
        products = products.filter(name__icontains=search)

    return render_fx(
        request,
        fragment_template="products/list_simple_partial.html",
        page_template="products/list_simple.html",
        context={"products": products},
    )
