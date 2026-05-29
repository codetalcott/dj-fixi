"""
Tests for dj_fixi.mixins.

Covers FxResponseMixin (form_valid for create/update/delete, form_invalid,
fragment template selection), ContextPersistenceMixin (sort validation, query
string), and OptimizedQueryMixin. These modules previously had no coverage.
"""

import json

import pytest
from django import forms
from django.contrib.auth.models import Group
from django.test import RequestFactory, override_settings
from django.views.generic import CreateView, DeleteView, ListView, TemplateView

from dj_fixi.mixins import ContextPersistenceMixin, FxResponseMixin, OptimizedQueryMixin

# locmem templates so fragment rendering works without app template dirs.
LOCMEM_TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "OPTIONS": {
            "loaders": [
                (
                    "django.template.loaders.locmem.Loader",
                    {
                        "g/form.html": "FULL {{ object.name }}",
                        "g/form_partial.html": "PARTIAL {{ object.name }}",
                    },
                )
            ],
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    }
]


class GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ["name"]


@pytest.fixture
def rf():
    return RequestFactory()


def _fx(request):
    request.is_fx = True
    request.fx_target = None
    request.fx_swap = "innerHTML"
    request.fx_trigger = None
    return request


# --------------------------------------------------------------------------- #
# FxResponseMixin.form_valid
# --------------------------------------------------------------------------- #


@override_settings(TEMPLATES=LOCMEM_TEMPLATES)
@pytest.mark.django_db
def test_form_valid_create_renders_fragment_and_triggers_event(rf):
    class V(FxResponseMixin, CreateView):
        model = Group
        form_class = GroupForm
        template_name = "g/form.html"
        success_url = "/done/"

    view = V()
    view.setup(_fx(rf.post("/", {"name": "new"})))
    view.object = None
    form = view.get_form()
    assert form.is_valid()

    response = view.form_valid(form)
    response.render()

    assert response.status_code == 200
    assert b"PARTIAL new" in response.content
    assert Group.objects.filter(name="new").exists()
    payload = json.loads(response["FX-Trigger"])
    assert "formSuccess" in payload
    assert payload["formSuccess"]["object_id"]


@override_settings(TEMPLATES=LOCMEM_TEMPLATES)
@pytest.mark.django_db
def test_form_valid_delete_returns_204_with_event(rf):
    """The pre-fix code crashed here (delete form has no .save())."""

    grp = Group.objects.create(name="gone")
    pk = grp.pk

    class V(FxResponseMixin, DeleteView):
        model = Group
        template_name = "g/confirm.html"
        success_url = "/done/"

    view = V()
    view.setup(_fx(rf.post("/")), pk=pk)
    view.object = view.get_object()
    form = view.get_form()
    assert form.is_valid()

    response = view.form_valid(form)

    assert response.status_code == 204
    assert not Group.objects.filter(pk=pk).exists()
    payload = json.loads(response["FX-Trigger"])
    assert payload["formSuccess"]["object_id"] == str(pk)


@override_settings(TEMPLATES=LOCMEM_TEMPLATES)
@pytest.mark.django_db
def test_form_valid_non_fx_redirects(rf):
    class V(FxResponseMixin, CreateView):
        model = Group
        form_class = GroupForm
        template_name = "g/form.html"
        success_url = "/done/"

    request = rf.post("/", {"name": "plain"})
    request.is_fx = False
    request.fx_target = None
    request.fx_swap = "innerHTML"
    request.fx_trigger = None

    view = V()
    view.setup(request)
    view.object = None
    form = view.get_form()
    assert form.is_valid()

    response = view.form_valid(form)

    assert response.status_code == 302
    assert response["Location"] == "/done/"
    assert "FX-Trigger" not in response


@override_settings(TEMPLATES=LOCMEM_TEMPLATES)
@pytest.mark.django_db
def test_form_invalid_returns_422_with_error_event(rf):
    class V(FxResponseMixin, CreateView):
        model = Group
        form_class = GroupForm
        template_name = "g/form.html"
        success_url = "/done/"

    view = V()
    view.setup(_fx(rf.post("/", {})))  # missing required name
    view.object = None
    form = view.get_form()
    assert not form.is_valid()

    response = view.form_invalid(form)
    response.render()

    assert response.status_code == 422
    payload = json.loads(response["FX-Trigger"])
    assert "formError" in payload


# --------------------------------------------------------------------------- #
# FxResponseMixin.get_template_names
# --------------------------------------------------------------------------- #


def test_fxresponsemixin_template_names_for_fx(rf):
    class V(FxResponseMixin, TemplateView):
        template_name = "products/list.html"

    view = V()
    view.setup(_fx(rf.get("/")))
    names = view.get_template_names()

    assert "products/list_partial.html" in names
    assert "products/fragments/list.html" in names
    assert "products/list.html" in names


# --------------------------------------------------------------------------- #
# ContextPersistenceMixin
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_context_persistence_invalid_sort_ignored(rf):
    class V(ContextPersistenceMixin, ListView):
        model = Group
        ordering = ["id"]

    request = rf.get("/?sort=bogus")
    view = V()
    view.setup(request)
    qs = view.get_queryset()  # must not raise

    assert qs.query.order_by == ("id",)  # bogus sort not applied


@pytest.mark.django_db
def test_context_persistence_valid_sort_applied(rf):
    class V(ContextPersistenceMixin, ListView):
        model = Group

    request = rf.get("/?sort=name")
    view = V()
    view.setup(request)
    qs = view.get_queryset()

    assert qs.query.order_by == ("name",)


@pytest.mark.django_db
def test_context_persistence_query_string(rf):
    class V(ContextPersistenceMixin, ListView):
        model = Group

    request = rf.get("/?q=test&page=2&extra=1")
    view = V()
    view.setup(request)
    view.object_list = Group.objects.none()
    ctx = view.get_context_data(object_list=view.object_list)

    assert "q=test" in ctx["query_string"]
    assert ctx["preserved_params"]["q"] == "test"
    assert ctx["current_sort"] == ""


# --------------------------------------------------------------------------- #
# OptimizedQueryMixin
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_optimized_query_applies_prefetch(rf):
    class V(OptimizedQueryMixin, ListView):
        model = Group
        prefetch_related_fields = ["permissions"]

    view = V()
    view.setup(rf.get("/"))
    qs = view.get_queryset()

    assert qs._prefetch_related_lookups == ("permissions",)
