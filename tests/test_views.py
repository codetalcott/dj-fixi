"""Tests for FxView"""
import pytest
from django.test import RequestFactory

from dj_fixi.views import FxCRUDView, FxTemplateView, FxView


@pytest.fixture
def rf():
    return RequestFactory()


class FakeQuerySet:
    """Minimal ordered queryset stand-in that tracks slicing.

    Iterating preserves insertion order; slicing returns a new FakeQuerySet
    over the same ordered items. This lets us assert pagination keeps order
    without touching the database.
    """

    def __init__(self, items, model=object):
        self._items = list(items)
        self.model = model

    def count(self):
        return len(self._items)

    def __getitem__(self, key):
        return FakeQuerySet(self._items[key], model=self.model)

    def __iter__(self):
        return iter(self._items)


def test_paginated_data_preserves_order(rf):
    """The HTML path must reuse the ordered page slice, not re-query by pk.

    Regression: a `filter(pk__in=[...])` re-query dropped the applied ordering.
    get_paginated_data now exposes the ordered slice as a queryset.
    """

    class TestView(FxCRUDView):
        model = object
        fields = ["name"]
        paginate_by = 3

    # Deliberately not pk-sorted: order must come from the queryset, not pks.
    ordered = [
        {"pk": 30, "name": "c"},
        {"pk": 10, "name": "a"},
        {"pk": 20, "name": "b"},
        {"pk": 5, "name": "z"},
    ]
    qs = FakeQuerySet(ordered)
    request = rf.get("/?page=1&limit=3")

    view = TestView()
    paginated = view.get_paginated_data(qs, request)

    # A queryset (not a list) is returned so callers render without re-querying.
    assert "queryset" in paginated
    assert isinstance(paginated["queryset"], FakeQuerySet)

    # Order is preserved across the page slice, and matches `items`.
    assert [obj["name"] for obj in paginated["queryset"]] == ["c", "a", "b"]
    assert [obj["name"] for obj in paginated["items"]] == ["c", "a", "b"]
    assert paginated["pagination"]["total"] == 4
    assert paginated["pagination"]["totalPages"] == 2


def test_fx_view_detects_fx_request(rf):
    """Test that FxView detects Fixi requests"""

    class TestView(FxTemplateView):
        template_name = "test.html"
        partial_template = "test_partial.html"

    request = rf.get("/", HTTP_FX_REQUEST="true")

    # Process through middleware-like setup
    request.is_fx = True
    request.fx_target = None
    request.fx_swap = "innerHTML"
    request.fx_trigger = None

    # Would need actual templates to test rendering
    # Just verify dispatch works
    view_instance = TestView()
    view_instance.setup(request)

    assert view_instance.is_fx is True


def test_fx_view_template_selection_for_fx_request(rf):
    """Test that FxView selects partial template for Fixi requests"""

    class TestView(FxView):
        template_name = "test.html"
        partial_template = "test_partial.html"

    request = rf.get("/", HTTP_FX_REQUEST="true")
    request.is_fx = True
    request.fx_target = None
    request.fx_swap = "innerHTML"
    request.fx_trigger = None

    view_instance = TestView()
    view_instance.setup(request)
    view_instance.dispatch(request)

    templates = view_instance.get_template_names()

    assert "test_partial.html" in templates
    assert "test.html" in templates


def test_fx_view_template_fallback_with_suffix(rf):
    """Test that FxView tries _partial suffix when partial_template not set"""

    class TestView(FxView):
        template_name = "test.html"

    request = rf.get("/", HTTP_FX_REQUEST="true")
    request.is_fx = True
    request.fx_target = None
    request.fx_swap = "innerHTML"
    request.fx_trigger = None

    view_instance = TestView()
    view_instance.setup(request)
    view_instance.dispatch(request)

    templates = view_instance.get_template_names()

    assert "test_partial.html" in templates
    assert "test.html" in templates


def test_fx_view_context_includes_fx_metadata(rf):
    """Test that context includes Fixi metadata"""

    class TestView(FxView):
        template_name = "test.html"

    request = rf.get("/", HTTP_FX_REQUEST="true")
    request.is_fx = True
    request.fx_target = "#content"
    request.fx_swap = "outerHTML"
    request.fx_trigger = "button"

    view_instance = TestView()
    view_instance.setup(request)
    view_instance.dispatch(request)

    context = view_instance.get_context_data()

    assert context["is_fx"] is True
    assert context["fx_target"] == "#content"
    assert context["fx_swap"] == "outerHTML"
