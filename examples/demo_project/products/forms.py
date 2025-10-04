"""Product forms for demo app"""

from django import forms
from .models import Product


class ProductForm(forms.ModelForm):
    """Form for creating/editing products."""

    class Meta:
        model = Product
        fields = ["name", "description", "price", "stock", "is_active"]
