"""
Views behind the pitfalls page.

The ``*_naive`` and ``*_page_only`` views are deliberately the wrong way to do
it; each sits next to the dj-fixi view that replaces it.
"""

import uuid
from collections import Counter

from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template import engines
from django.urls import reverse, reverse_lazy
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST
from django.views.generic import CreateView

from dj_fixi.lint import lint_html
from dj_fixi.mixins import FxResponseMixin
from dj_fixi.shortcuts import render_fx

from .catalog import PITFALLS
from .models import Note

#: Requests received per (page load, control). In memory: this is a demo.
HITS: Counter = Counter()


def render_snippet(source: str, request, context: dict) -> str:
    template = engines["django"].from_string("{% load fixi_tags %}" + source)
    return template.render(context, request)


def snippet_context(request, token: str) -> dict:
    return {
        "token": token,
        "details_url": reverse("pitfalls:details"),
        "note_naive_url": reverse("pitfalls:note_naive"),
        "note_fixed_url": reverse("pitfalls:note_fixed"),
        "form": NoteCreate().get_form_class()(),
    }


def index(request):
    token = uuid.uuid4().hex
    context = snippet_context(request, token)
    rows = []
    for pitfall in PITFALLS:
        naive_html = render_snippet(pitfall.naive, request, context)
        rows.append(
            {
                "pitfall": pitfall,
                "naive_html": naive_html,
                "fixed_html": render_snippet(pitfall.fixed, request, context),
                # Computed now, from the markup on this page, not copied from the catalog.
                "findings": lint_html(naive_html, full_document=False),
            }
        )
    return render(request, "pitfalls/index.html", {"rows": rows})


# --- a fragment URL -----------------------------------------------------


def details_page_only(request):
    """Naive: one template, whoever is asking."""
    return render(request, "pitfalls/details.html")


def details(request):
    """dj-fixi: the fragment for Fixi, the page for everyone else."""
    return render_fx(request, "pitfalls/details_partial.html", "pitfalls/details.html")


# --- a form that redirects on success -------------------------------------


class NoteCreateNaive(CreateView):
    """Naive: Django's own behaviour, a redirect after a valid POST."""

    model = Note
    fields = ["text"]
    template_name = "pitfalls/note_form.html"
    success_url = reverse_lazy("pitfalls:index")

    def get_context_data(self, **kwargs):
        return super().get_context_data(action=self.request.path, **kwargs)


class NoteCreate(FxResponseMixin, CreateView):
    """dj-fixi: a Fixi POST gets the form fragment back, and an event."""

    model = Note
    fields = ["text"]
    template_name = "pitfalls/note_page.html"
    partial_template = "pitfalls/note_form.html"
    success_url = reverse_lazy("pitfalls:index")

    def get_context_data(self, **kwargs):
        return super().get_context_data(action=self.request.path, **kwargs)


# --- FX-Trigger ---------------------------------------------------------


@xframe_options_sameorigin
def events_frame(request):
    """A tiny page with, or without, the events shim. Shown in an iframe."""
    return render(request, "pitfalls/events_frame.html", {"shim": request.GET.get("shim") == "1"})


def ping(request):
    response = HttpResponse("The server answered, with FX-Trigger: pinged.")
    response["FX-Trigger"] = "pinged"
    return response


# --- confirm ------------------------------------------------------------


def hit(request, token, name):
    HITS[token, name] += 1
    count = HITS[token, name]
    return HttpResponse(f"The server has received {count} request{'' if count == 1 else 's'}.")


# --- CSRF ---------------------------------------------------------------


@require_POST
def save(request):
    if not request.headers.get("FX-Request"):
        return redirect("pitfalls:index")
    return HttpResponse("Saved.")
