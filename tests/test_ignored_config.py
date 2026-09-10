"""
Regression tests for dj-fixi 0.3.0 fixes F3-F10.

Every case here is the same species of bug: dj-fixi accepted a configuration
value, documented it, and then dropped it -- so the caller got no error and no
effect. These assert the value is now honored, or that a wrong one is loud.
"""

import logging

import pytest
from django import forms
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ImproperlyConfigured
from django.template import Context, RequestContext, Template, TemplateSyntaxError
from django.test import RequestFactory
from django.views.generic import FormView

from dj_fixi.forms import FxForm
from dj_fixi.mixins import ContextPersistenceMixin, FxResponseMixin

LOCMEM_TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "OPTIONS": {
            "loaders": [("django.template.loaders.locmem.Loader", {"g/form.html": "FORM"})],
            "context_processors": ["django.template.context_processors.request"],
        },
    }
]


@pytest.fixture
def rf():
    return RequestFactory()


# --------------------------------------------------------------------------- #
# F3 -- filterset_fields was documented, gated a branch, and then discarded
# --------------------------------------------------------------------------- #


class _Filtered(ContextPersistenceMixin):
    filterset_fields = ["codename"]

    def __init__(self, request):
        self.request = request


def test_filterset_fields_actually_filters(rf):
    view = _Filtered(rf.get("/", {"codename": "add_group"}))
    qs = view.filter_queryset(Permission.objects.all())
    assert "codename" in str(qs.query)


def test_filterset_fields_is_a_noop_when_not_supplied(rf):
    view = _Filtered(rf.get("/"))
    base = Permission.objects.all()
    assert view.filter_queryset(base).query.where == base.query.where


def test_unknown_filterset_field_raises(rf):
    class Bad(_Filtered):
        filterset_fields = ["nonexistent"]

    with pytest.raises(ImproperlyConfigured, match="nonexistent"):
        Bad(rf.get("/")).filter_queryset(Permission.objects.all())


def test_filterset_field_with_a_lookup_raises_and_says_what_to_use(rf):
    class Bad(_Filtered):
        filterset_fields = ["codename__icontains"]

    with pytest.raises(ImproperlyConfigured, match="filterset_class"):
        Bad(rf.get("/")).filter_queryset(Permission.objects.all())


# --------------------------------------------------------------------------- #
# F10 -- a valid related-field sort was validated away and silently dropped
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "path,expected",
    [
        ("codename", True),
        ("content_type__app_label", True),  # used to be rejected
        ("content_type", True),
        ("nope", False),
        ("content_type__nope", False),
        ("codename__nope", False),  # codename has no related model
    ],
)
def test_sortable_paths(path, expected):
    assert ContextPersistenceMixin._is_sortable(Permission, path) is expected


# --------------------------------------------------------------------------- #
# F8 -- get_success_message read self.model blindly, on the success path only
# --------------------------------------------------------------------------- #


def test_success_message_without_a_model():
    class V(FxResponseMixin, FormView):
        pass

    assert V().get_success_message() == "Saved successfully"


def test_success_message_falls_back_to_the_saved_object():
    class V(FxResponseMixin, FormView):
        pass

    view = V()
    view.object = Group(name="x")
    assert "Group" in view.get_success_message()


def test_success_message_prefers_the_declared_model():
    class V(FxResponseMixin, FormView):
        model = Permission

    assert "Permission" in V().get_success_message()


# --------------------------------------------------------------------------- #
# F4 -- FxForm accepted cancel_action and hardcoded fx-action="" instead
# --------------------------------------------------------------------------- #


class _GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ["name"]


def test_cancel_button_uses_cancel_action():
    html = FxForm(
        form=_GroupForm(),
        action="/groups/1/edit/",
        target="#row-1",
        cancel_action="/groups/1/row/",
    ).render()
    assert 'fx-action="/groups/1/row/"' in html
    assert 'fx-action=""' not in html


def test_cancel_button_falls_back_to_action():
    html = FxForm(form=_GroupForm(), action="/groups/1/edit/", target="#row-1").render()
    assert html.count("/groups/1/edit/") >= 2
    assert 'fx-action=""' not in html


def test_csrf_input_emitted_when_a_request_is_supplied(rf):
    html = FxForm(form=_GroupForm(), action="/x/", request=rf.get("/")).render()
    assert "csrfmiddlewaretoken" in html


def test_no_csrf_input_for_safe_methods(rf):
    html = FxForm(form=_GroupForm(), action="/x/", method="GET", request=rf.get("/")).render()
    assert "csrfmiddlewaretoken" not in html


# --------------------------------------------------------------------------- #
# F5 -- a case-wrong swap made fixi.js throw; the server still returned 200
# --------------------------------------------------------------------------- #


def _attrs(arg):
    return Template("{% load fixi_tags %}{% fx_attrs action='/a' " + arg + " %}").render(Context())


@pytest.mark.parametrize(
    "given,expected",
    [("'innerhtml'", "innerHTML"), ("'INNERHTML'", "innerHTML"), ("'BeforeEnd'", "beforeend")],
)
def test_swap_case_is_normalized(given, expected):
    assert f'fx-swap="{expected}"' in _attrs(f"swap={given}")


def test_case_wrong_default_swap_is_still_omitted():
    """outerHTML is fixi's default, so it is emitted by omission either way."""
    assert "fx-swap" not in _attrs("swap='outerhtml'")


def test_morph_is_accepted_for_paxi():
    assert 'fx-swap="morph"' in _attrs("swap='morph'")


def test_unknown_swap_raises_and_names_the_alternatives():
    with pytest.raises(TemplateSyntaxError, match="innerHTML"):
        _attrs("swap='innerHTM'")


# --------------------------------------------------------------------------- #
# F6 -- fx_csrf_token returned "" without the request context processor,
#       so forms rendered correctly and every POST came back 403
# --------------------------------------------------------------------------- #


def test_csrf_token_without_the_request_context_processor(rf):
    """csrf_token is a *builtin* context processor, so this needs no config."""
    out = Template("{% load fixi_tags %}{% fx_csrf_token %}").render(RequestContext(rf.get("/")))
    assert "csrfmiddlewaretoken" in out


def test_csrf_token_raises_outside_a_request_context():
    with pytest.raises(ImproperlyConfigured, match="RequestContext"):
        Template("{% load fixi_tags %}{% fx_csrf_token %}").render(Context())


# --------------------------------------------------------------------------- #
# A successful Fixi create used to save the row and *then* 500, when the view
# had no success_url -- the redirect ModelFormMixin builds is discarded on the
# Fixi path anyway. Found by two agents reading the source during the 0.3.0
# generation evaluation.
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_fixi_create_without_success_url_still_returns_a_fragment(rf, settings):
    from django.views.generic import CreateView

    settings.TEMPLATES = LOCMEM_TEMPLATES

    class V(FxResponseMixin, CreateView):
        model = Group
        form_class = _GroupForm
        template_name = "g/form.html"  # no success_url; Group has no get_absolute_url

    view = V()
    view.request = rf.post("/", {"name": "made"}, HTTP_FX_REQUEST="true")
    view.object = None
    form = _GroupForm({"name": "made"})
    assert form.is_valid()

    response = view.form_valid(form)

    assert response.status_code == 200
    assert Group.objects.filter(name="made").exists()
    assert "formSuccess" in response["FX-Trigger"]


@pytest.mark.django_db
def test_non_fixi_create_without_success_url_still_raises(rf, settings):
    """Django's own error must survive for the path that actually redirects."""
    from django.views.generic import CreateView

    settings.TEMPLATES = LOCMEM_TEMPLATES

    class V(FxResponseMixin, CreateView):
        model = Group
        form_class = _GroupForm
        template_name = "g/form.html"

    view = V()
    view.request = rf.post("/", {"name": "plain"})
    view.object = None
    form = _GroupForm({"name": "plain"})
    assert form.is_valid()

    with pytest.raises(ImproperlyConfigured):
        view.form_valid(form)


# --------------------------------------------------------------------------- #
# Composing FxResponseMixin with FxView used to bury the explicit
# partial_template behind six convention-derived guesses, so a stray
# foo_partial.html silently outranked the fragment the author actually named.
# Found by an agent during the 0.3.0 generation evaluation.
# --------------------------------------------------------------------------- #


def _composed_candidates(rf):
    from django.views.generic import CreateView

    from dj_fixi.views import FxView

    class V(FxResponseMixin, FxView, CreateView):
        model = Group
        fields = ["name"]
        template_name = "notes/note_list.html"
        partial_template = "notes/_panel.html"

    view = V()
    view.request = rf.post("/", HTTP_FX_REQUEST="true")
    return view.get_template_names()


def test_explicit_partial_template_outranks_derived_names(rf):
    assert _composed_candidates(rf)[0] == "notes/_panel.html"


def test_no_double_suffixed_candidate(rf):
    assert not any("_partial_partial" in n for n in _composed_candidates(rf))


def test_no_duplicate_candidates(rf):
    names = _composed_candidates(rf)
    assert len(names) == len(set(names))


def test_full_page_still_last(rf):
    assert _composed_candidates(rf)[-1] == "notes/note_list.html"


def test_non_fixi_requests_are_untouched(rf):
    from django.views.generic import CreateView

    from dj_fixi.views import FxView

    class V(FxResponseMixin, FxView, CreateView):
        model = Group
        fields = ["name"]
        template_name = "notes/note_list.html"
        partial_template = "notes/_panel.html"

    view = V()
    view.request = rf.get("/")
    assert "notes/_panel.html" not in view.get_template_names()


# --------------------------------------------------------------------------- #
# All six agents in the generation evaluation independently wrote the same
# workaround: substituting a fresh unbound form after a successful create,
# because the mixin re-rendered the bound one and echoed back what was just
# saved. Six of six converging on a workaround is a missing feature.
# --------------------------------------------------------------------------- #


def _create_view(**attrs):
    from django.views.generic import CreateView

    return type(
        "V",
        (FxResponseMixin, CreateView),
        {
            "model": Group,
            "form_class": _GroupForm,
            "template_name": "g/form.html",
            **attrs,
        },
    )


@pytest.mark.django_db
def test_create_returns_a_blank_form(rf, settings):
    settings.TEMPLATES = LOCMEM_TEMPLATES
    view = _create_view()()
    view.request = rf.post("/", {"name": "fresh"}, HTTP_FX_REQUEST="true")
    view.object = None
    form = _GroupForm({"name": "fresh"})
    assert form.is_valid()

    response = view.form_valid(form)

    assert response.context_data["form"].is_bound is False
    assert Group.objects.filter(name="fresh").exists()


@pytest.mark.django_db
def test_update_keeps_the_bound_form(rf, settings):
    """An update's values are the object's current state, so they must stay."""
    settings.TEMPLATES = LOCMEM_TEMPLATES
    existing = Group.objects.create(name="before")

    view = _create_view()()
    view.request = rf.post("/", {"name": "after"}, HTTP_FX_REQUEST="true")
    view.object = existing
    form = _GroupForm({"name": "after"}, instance=existing)
    assert form.is_valid()

    response = view.form_valid(form)

    assert response.context_data["form"].is_bound is True
    assert response.context_data["form"].data["name"] == "after"


@pytest.mark.django_db
def test_reset_can_be_switched_off(rf, settings):
    settings.TEMPLATES = LOCMEM_TEMPLATES
    view = _create_view(fx_reset_form_after_create=False)()
    view.request = rf.post("/", {"name": "kept"}, HTTP_FX_REQUEST="true")
    view.object = None
    form = _GroupForm({"name": "kept"})
    assert form.is_valid()

    assert view.form_valid(form).context_data["form"].is_bound is True


@pytest.mark.django_db
def test_a_form_needing_constructor_args_falls_back_loudly(rf, settings, caplog):
    """A save that already committed must not fail; it warns and keeps the form."""
    settings.TEMPLATES = LOCMEM_TEMPLATES

    class NeedsArgs(_GroupForm):
        def __init__(self, *args, required_arg, **kwargs):
            super().__init__(*args, **kwargs)

    view = _create_view()()
    view.get_form_class = lambda: NeedsArgs
    view.request = rf.post("/", {"name": "args"}, HTTP_FX_REQUEST="true")
    view.object = None
    form = _GroupForm({"name": "args"})
    assert form.is_valid()

    with caplog.at_level(logging.WARNING):
        response = view.form_valid(form)

    assert response.context_data["form"] is form
    assert "get_fx_success_form" in caplog.text
