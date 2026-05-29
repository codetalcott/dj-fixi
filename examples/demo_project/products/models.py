"""Product models for demo app"""

from django.db import models
from django.urls import reverse


class Product(models.Model):
    """Simple product model for demonstration"""

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        """Canonical edit URL (the demo has no standalone detail view)."""
        return reverse("product_update", args=[self.pk])
