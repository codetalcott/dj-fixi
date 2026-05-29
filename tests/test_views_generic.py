"""
Tests for FxView composed with Django generic views.

These guard the cooperative-inheritance contract: FxView must not terminate the
MRO super() chain, so generic-view context (object_list, pagination, etc.) and
generic template-name resolution keep working when FxView sits in front of
ListView/DetailView. The pre-fix bug dropped all of that silently.
"""

import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import ImproperlyConfigured
from django.test import RequestFactory
from django.views.generic import DetailView, ListView

from dj_fixi.mixins import ContextPersistenceMixin, OptimizedQueryMixin
from dj_fixi.views import FxView


@pytest.fixture
def rf():
    return RequestFactory()


def _request(rf, *, is_fx=False, target=None, swap="innerHTML"):
    request = rf.get("/")
    request.is_fx = is_fx
    request.fx_target = target
    request.fx_swap = swap
    request.fx_trigger = None
    return request


@pytest.mark.django_db
def test_fxview_listview_preserves_listview_context(rf):
    """object_list / context_object_name / paginator / page_obj survive FxView."""

    class V(FxView, ListView):
        model = Group
        ordering = ["id"]
        context_object_name = "groups"
        paginate_by = 10
        template_name = "g/list.html"

    Group.objects.create(name="a")
    Group.objects.create(name="b")

    view = V()
    view.setup(_request(rf))
    view.object_list = view.get_queryset()
    ctx = view.get_context_data(object_list=view.object_list)

    assert list(ctx["groups"]) == list(ctx["object_list"])
    assert len(ctx["object_list"]) == 2
    assert ctx["paginator"] is not None
    assert ctx["page_obj"] is not None
    assert ctx["is_paginated"] is False
    # Fx metadata layered on top
    assert ctx["is_fx"] is False
    assert ctx["fx_swap"] == "innerHTML"


@pytest.mark.django_db
def test_full_demo_mro_context_coexists(rf):
    """The documented demo stack keeps Django, persistence, and Fx context."""

    class V(ContextPersistenceMixin, OptimizedQueryMixin, FxView, ListView):
        model = Group
        ordering = ["id"]
        context_object_name = "groups"
        template_name = "g/list.html"

    Group.objects.create(name="a")

    view = V()
    view.setup(_request(rf, is_fx=True, target="#c", swap="outerHTML"))
    view.object_list = view.get_queryset()
    ctx = view.get_context_data(object_list=view.object_list)

    # ListView context
    assert "object_list" in ctx and "groups" in ctx and "page_obj" in ctx
    # ContextPersistenceMixin context
    assert "query_string" in ctx and "preserved_params" in ctx and "current_sort" in ctx
    # Fx metadata
    assert ctx["is_fx"] is True
    assert ctx["fx_target"] == "#c"
    assert ctx["fx_swap"] == "outerHTML"


@pytest.mark.django_db
def test_fxview_detailview_preserves_object(rf):
    class V(FxView, DetailView):
        model = Group
        template_name = "g/detail.html"

    grp = Group.objects.create(name="solo")
    view = V()
    view.setup(_request(rf))
    view.object = grp
    ctx = view.get_context_data(object=grp)

    assert ctx["object"] is grp
    assert ctx["group"] is grp  # DetailView default context_object_name
    assert ctx["is_fx"] is False


def test_bare_fxview_builds_context_from_kwargs(rf):
    """Bare FxView (over django.views.View) has no super get_context_data."""

    class V(FxView):
        template_name = "x.html"

    view = V()
    view.setup(_request(rf, is_fx=True, target="#c", swap="outerHTML"))
    ctx = view.get_context_data(foo="bar")

    assert ctx["foo"] == "bar"
    assert ctx["view"] is view
    assert ctx["is_fx"] is True
    assert ctx["fx_target"] == "#c"


def test_get_template_names_raises_when_unconfigured(rf):
    class V(FxView):
        pass

    view = V()
    view.setup(_request(rf))
    with pytest.raises(ImproperlyConfigured) as exc:
        view.get_template_names()
    assert "V" in str(exc.value)


@pytest.mark.django_db
def test_get_template_names_appends_model_template(rf):
    """Generic model-derived template names are appended after explicit ones."""

    class V(FxView, ListView):
        model = Group
        template_name = "g/list.html"

    view = V()
    view.setup(_request(rf))
    view.object_list = Group.objects.all()
    names = view.get_template_names()

    assert names[0] == "g/list.html"
    assert "auth/group_list.html" in names  # from MultipleObjectTemplateResponseMixin


def test_get_template_names_partial_first_for_fx(rf):
    class V(FxView):
        template_name = "products/list.html"
        partial_template = "products/list_partial.html"

    view = V()
    view.setup(_request(rf, is_fx=True))
    names = view.get_template_names()

    assert names.index("products/list_partial.html") < names.index("products/list.html")
