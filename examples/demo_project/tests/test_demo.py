"""The demo starts from its README, and its ordinary pages are lint-clean."""

import pytest
from django.core.management import call_command
from django.urls import reverse
from products.models import Product

from dj_fixi.testing import FxTestClient, assert_no_fixi_check_issues

pytestmark = pytest.mark.django_db


def test_seed_creates_enough_products_to_page_through():
    call_command("seed", verbosity=0)
    assert Product.objects.count() == 25
    call_command("seed", verbosity=0)  # idempotent
    assert Product.objects.count() == 25
    call_command("seed", "--reset", verbosity=0)
    assert Product.objects.count() == 25


def test_dj_fixi_is_configured_correctly():
    assert_no_fixi_check_issues()


def test_every_products_page_is_lint_clean():
    """FxTestClient raises on any error-level finding, so reaching the end is the assertion."""
    call_command("seed", verbosity=0)
    product = Product.objects.first()
    fx = FxTestClient()
    for url in [
        reverse("product_list"),
        reverse("product_list") + "?page=2&q=a",
        reverse("product_list_simple"),
        reverse("product_create"),
        reverse("product_update", args=[product.pk]),
    ]:
        assert fx.get(url).status_code == 200, url
        fragment = fx.fx_get(url)
        assert fragment.status_code == 200 and b"<html" not in fragment.content, url
        for response in (fx.get(url), fragment):
            assert b"{#" not in response.content and b"#}" not in response.content, url


def test_no_template_comment_spans_lines():
    """Django's {# #} is single-line; across lines it is not a comment and renders as text."""
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parent.parent
    for path in root.glob("*/templates/**/*.html"):
        for match in re.finditer(r"\{#(.*?)#\}", path.read_text(), flags=re.S):
            assert "\n" not in match.group(1), f"{path.relative_to(root)}: use {{% comment %}}"
