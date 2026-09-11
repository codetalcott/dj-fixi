"""View classes used by the fixture URLconfs. Deliberately includes wrong ones."""

from django.contrib.auth.models import Group
from django.http import HttpResponse
from django.views.generic import CreateView, DeleteView, ListView

from dj_fixi.mixins import ContextPersistenceMixin, FxResponseMixin, OptimizedQueryMixin
from dj_fixi.shortcuts import render_fx
from dj_fixi.views import FxTemplateView, FxView

TEMPLATE = "good/list.html"
PARTIAL = "good/list_partial.html"


# ------------------------------ correct ------------------------------------ #


class GoodList(FxView, ListView):
    model = Group
    template_name = TEMPLATE
    partial_template = PARTIAL


class GoodCreate(FxResponseMixin, CreateView):
    model = Group
    fields = ["name"]
    template_name = TEMPLATE
    partial_template = PARTIAL
    success_url = "/"


class GoodMixinStack(ContextPersistenceMixin, OptimizedQueryMixin, FxView, ListView):
    model = Group
    template_name = TEMPLATE
    partial_template = PARTIAL


class GoodTemplate(FxTemplateView):
    template_name = TEMPLATE
    partial_template = PARTIAL


def good_fbv(request):
    return render_fx(request, PARTIAL, TEMPLATE, {})


def plain_fbv(request):
    return HttpResponse("ok")


# ------------------------------ wrong MRO ---------------------------------- #


class BadList(ListView, FxView):
    """FxView after ListView: partial selection and is_fx silently disabled."""

    model = Group
    template_name = TEMPLATE
    partial_template = PARTIAL


class BadCreate(CreateView, FxResponseMixin):
    """FormMixin.form_valid terminates the chain before FxResponseMixin."""

    model = Group
    fields = ["name"]
    template_name = TEMPLATE
    success_url = "/"


class BadQueryMixins(ListView, ContextPersistenceMixin):
    """get_queryset never reaches the mixin: no filtering, silent N+1."""

    model = Group
    template_name = TEMPLATE
    partial_template = PARTIAL


class UserShadow(FxView, ListView):
    """User code that overrides a hook without calling super()."""

    model = Group
    template_name = TEMPLATE
    partial_template = PARTIAL

    def get_context_data(self, **kwargs):
        return {}


# --------------------------- other misconfigurations ------------------------ #


class NoHandler(FxView):
    """FxView supplies no get()/post(), so this answers 405 forever."""

    template_name = TEMPLATE


class MissingPartial(FxView, ListView):
    model = Group
    template_name = TEMPLATE
    partial_template = "good/typo_partail.html"


class NoPartialAnywhere(FxView, ListView):
    model = Group
    template_name = TEMPLATE


class MissingHashPartial(FxView, ListView):
    """Django 6 partial syntax naming a partial the template does not define."""

    model = Group
    template_name = TEMPLATE
    partial_template = "good/list.html#nope"


# ------------------------- no partial_template (W202) ---------------------- #


class NoPartialList(FxView, ListView):
    """Fixi requests get the page; nothing is derived from template_name."""

    model = Group
    template_name = TEMPLATE


class NoPartialCreate(FxResponseMixin, CreateView):
    model = Group
    fields = ["name"]
    template_name = TEMPLATE
    success_url = "/"


class NoPartialDelete(FxResponseMixin, DeleteView):
    """Renders nothing for Fixi (204), so no partial is expected of it."""

    model = Group
    template_name = TEMPLATE
    success_url = "/"


class NoTemplate(FxTemplateView):
    """Has get() (so not E103) but nothing that can name a template."""
