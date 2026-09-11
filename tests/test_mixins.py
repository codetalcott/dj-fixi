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
from django.core.exceptions import ImproperlyConfigured
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
                        "g/form_partial.html": (
                            "PARTIAL {{ object.name }}"
                            "[{% for g in group_list %}{{ g.name }},{% endfor %}]"
                        ),
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
        partial_template = "g/form_partial.html"
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
        partial_template = "g/form_partial.html"
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
        partial_template = "g/form_partial.html"
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


def test_fxresponsemixin_without_a_partial_keeps_the_page_names(rf):
    """Nothing is derived by convention; W202 names such a view at boot."""

    class V(FxResponseMixin, TemplateView):
        template_name = "products/list.html"

    view = V()
    view.setup(_fx(rf.get("/")))

    assert view.get_template_names() == ["products/list.html"]


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


# --------------------------------------------------------------------------- #
# FxResponseMixin.fx_collection -- the collection a form view's fragment shows
# --------------------------------------------------------------------------- #


@override_settings(TEMPLATES=LOCMEM_TEMPLATES)
@pytest.mark.django_db
def test_fx_collection_reaches_the_success_fragment(rf):
    """A create view's fragment shows the list the object just joined.

    Six of six independent implementations wrote this by hand in
    get_context_data, because ModelFormMixin has no object_list.
    """
    Group.objects.create(name="existing")

    class V(FxResponseMixin, CreateView):
        model = Group
        form_class = GroupForm
        template_name = "g/form.html"
        partial_template = "g/form_partial.html"
        success_url = "/done/"
        fx_collection = Group.objects.all()

    view = V()
    view.setup(_fx(rf.post("/", {"name": "new"})))
    view.object = None
    form = view.get_form()
    assert form.is_valid()

    response = view.form_valid(form)
    response.render()

    body = response.content.decode()
    assert "existing," in body
    assert "new," in body, "the just-created object must be in the rendered collection"


@override_settings(TEMPLATES=LOCMEM_TEMPLATES)
@pytest.mark.django_db
def test_fx_collection_accepts_a_manager_and_a_callable(rf):
    Group.objects.create(name="one")

    class Managed(FxResponseMixin, CreateView):
        model = Group
        form_class = GroupForm
        template_name = "g/form.html"
        partial_template = "g/form_partial.html"
        fx_collection = Group.objects

    class Called(Managed):
        fx_collection = staticmethod(lambda view: Group.objects.filter(name="one"))

    for cls in (Managed, Called):
        view = cls()
        view.setup(_fx(rf.get("/")))
        view.object = None
        names = [g.name for g in view.get_context_data(form=view.get_form())["group_list"]]
        assert "one" in names


@override_settings(TEMPLATES=LOCMEM_TEMPLATES)
@pytest.mark.django_db
def test_fx_collection_name_defaults_to_the_listview_convention(rf):
    class V(FxResponseMixin, CreateView):
        model = Group
        form_class = GroupForm
        template_name = "g/form.html"
        partial_template = "g/form_partial.html"
        fx_collection = Group.objects.all()

    view = V()
    view.setup(_fx(rf.get("/")))
    view.object = None
    context = view.get_context_data(form=view.get_form())
    assert "group_list" in context
    assert "object_list" in context


@override_settings(TEMPLATES=LOCMEM_TEMPLATES)
@pytest.mark.django_db
def test_no_fx_collection_leaves_context_untouched(rf):
    class V(FxResponseMixin, CreateView):
        model = Group
        form_class = GroupForm
        template_name = "g/form.html"
        partial_template = "g/form_partial.html"

    view = V()
    view.setup(_fx(rf.get("/")))
    view.object = None
    context = view.get_context_data(form=view.get_form())
    assert "group_list" not in context
    assert "object_list" not in context


# --------------------------------------------------------------------------- #
# FxResponseMixin.get_success_url -- optional on a path that discards it
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_success_url_falls_back_to_the_referring_page(rf):
    class V(FxResponseMixin, CreateView):
        model = Group
        form_class = GroupForm
        template_name = "g/form.html"
        partial_template = "g/form_partial.html"

    view = V()
    view.setup(rf.post("/add/", {"name": "x"}, HTTP_REFERER="http://testserver/notes/"))
    view.object = None
    assert view.get_success_url() == "http://testserver/notes/"


@pytest.mark.django_db
def test_success_url_prefers_an_explicit_default_over_the_referer(rf):
    class V(FxResponseMixin, CreateView):
        model = Group
        form_class = GroupForm
        template_name = "g/form.html"
        partial_template = "g/form_partial.html"
        fx_default_success_url = "/elsewhere/"

    view = V()
    view.setup(rf.post("/add/", {"name": "x"}, HTTP_REFERER="http://testserver/notes/"))
    view.object = None
    assert view.get_success_url() == "/elsewhere/"


@pytest.mark.django_db
def test_success_url_still_wins_when_set(rf):
    class V(FxResponseMixin, CreateView):
        model = Group
        form_class = GroupForm
        template_name = "g/form.html"
        partial_template = "g/form_partial.html"
        success_url = "/explicit/"

    view = V()
    view.setup(rf.post("/add/", {"name": "x"}, HTTP_REFERER="http://testserver/notes/"))
    view.object = Group.objects.create(name="saved")
    assert view.get_success_url() == "/explicit/"


@pytest.mark.django_db
def test_an_offsite_referer_is_refused(rf):
    """A redirect target taken from a header is an open-redirect if unchecked."""

    class V(FxResponseMixin, CreateView):
        model = Group
        form_class = GroupForm
        template_name = "g/form.html"
        partial_template = "g/form_partial.html"

    view = V()
    view.setup(rf.post("/add/", {"name": "x"}, HTTP_REFERER="https://evil.example/x"))
    view.object = None
    with pytest.raises(ImproperlyConfigured):
        view.get_success_url()


@pytest.mark.django_db
def test_the_fallback_can_be_switched_off(rf):
    class V(FxResponseMixin, CreateView):
        model = Group
        form_class = GroupForm
        template_name = "g/form.html"
        partial_template = "g/form_partial.html"
        fx_default_success_url = False

    view = V()
    view.setup(rf.post("/add/", {"name": "x"}, HTTP_REFERER="http://testserver/notes/"))
    view.object = None
    with pytest.raises(ImproperlyConfigured):
        view.get_success_url()


@pytest.mark.django_db
def test_no_referer_and_no_url_still_raises(rf):
    class V(FxResponseMixin, CreateView):
        model = Group
        form_class = GroupForm
        template_name = "g/form.html"
        partial_template = "g/form_partial.html"

    view = V()
    view.setup(rf.post("/add/", {"name": "x"}))
    view.object = None
    with pytest.raises(ImproperlyConfigured):
        view.get_success_url()


@override_settings(TEMPLATES=LOCMEM_TEMPLATES)
@pytest.mark.django_db
def test_fx_collection_clones_a_class_level_queryset(rf):
    """A queryset on the class keeps its result cache for the life of the process.

    Returned as-is it serves the first request's rows forever. Four of six
    implementations worked this out from the source and passed a manager instead.
    """

    class V(FxResponseMixin, CreateView):
        model = Group
        form_class = GroupForm
        template_name = "g/form.html"
        partial_template = "g/form_partial.html"
        fx_collection = Group.objects.all()

    view = V()
    view.setup(_fx(rf.get("/")))

    Group.objects.create(name="first")
    assert [g.name for g in view.get_fx_collection()] == ["first"]
    Group.objects.create(name="second")
    names = [g.name for g in view.get_fx_collection()]
    assert "second" in names, "a stale result cache was served"


@override_settings(TEMPLATES=LOCMEM_TEMPLATES)
@pytest.mark.django_db
def test_fx_collection_accepts_a_plain_function(rf):
    """A bare function on the class must not bind as a method and take self twice."""

    def newest(view):
        return Group.objects.order_by("-pk")

    class V(FxResponseMixin, CreateView):
        model = Group
        form_class = GroupForm
        template_name = "g/form.html"
        partial_template = "g/form_partial.html"
        fx_collection = newest

    Group.objects.create(name="only")
    view = V()
    view.setup(_fx(rf.get("/")))
    assert [g.name for g in view.get_fx_collection()] == ["only"]


@override_settings(TEMPLATES=LOCMEM_TEMPLATES)
@pytest.mark.django_db
def test_fx_collection_still_accepts_staticmethod(rf):
    """The shape implementations reached for when the plain function failed."""

    class V(FxResponseMixin, CreateView):
        model = Group
        form_class = GroupForm
        template_name = "g/form.html"
        partial_template = "g/form_partial.html"
        fx_collection = staticmethod(lambda view: Group.objects.all())

    Group.objects.create(name="only")
    view = V()
    view.setup(_fx(rf.get("/")))
    assert [g.name for g in view.get_fx_collection()] == ["only"]


# ------------------------------------------------------------------ 0.4.0


@override_settings(TEMPLATES=LOCMEM_TEMPLATES)
@pytest.mark.django_db
def test_http_delete_answers_a_fixi_control_with_204(rf):
    """DeletionMixin.delete() redirects without form_valid; fetch followed it as a DELETE."""
    grp = Group.objects.create(name="gone")
    pk = grp.pk

    class V(FxResponseMixin, DeleteView):
        model = Group
        template_name = "g/confirm.html"
        success_url = "/done/"

    response = V.as_view()(rf.delete("/", HTTP_FX_REQUEST="true"), pk=pk)

    assert response.status_code == 204
    assert not Group.objects.filter(pk=pk).exists()
    assert json.loads(response["FX-Trigger"])["formSuccess"]["object_id"] == str(pk)


@override_settings(TEMPLATES=LOCMEM_TEMPLATES)
@pytest.mark.django_db
def test_http_delete_from_a_browser_keeps_djangos_redirect(rf):
    grp = Group.objects.create(name="gone")

    class V(FxResponseMixin, DeleteView):
        model = Group
        success_url = "/done/"

    response = V.as_view()(rf.delete("/"), pk=grp.pk)

    assert (response.status_code, response["Location"]) == (302, "/done/")
    assert not Group.objects.filter(pk=grp.pk).exists()


@override_settings(TEMPLATES=LOCMEM_TEMPLATES)
@pytest.mark.django_db
def test_http_delete_on_a_view_without_a_delete_path_is_405(rf):
    class V(FxResponseMixin, CreateView):
        model = Group
        form_class = GroupForm
        template_name = "g/form.html"
        partial_template = "g/form_partial.html"

    assert V.as_view()(rf.delete("/", HTTP_FX_REQUEST="true")).status_code == 405


def test_fxresponsemixin_explicit_partial_is_the_whole_answer(rf):
    class V(FxResponseMixin, TemplateView):
        template_name = "products/list.html"
        partial_template = "products/rows.html"

    view = V()
    view.setup(_fx(rf.get("/")))
    assert view.get_template_names() == ["products/rows.html"]
