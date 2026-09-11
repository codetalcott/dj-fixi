"""
Template-resolution checks.

FxView hands an ordered *list* of candidates to TemplateResponse, and
``select_template`` only raises when every candidate is missing. So a typo in
``partial_template`` never errors -- it quietly falls through to the full page,
which fixi then swaps into a div.
"""

import django
from django.core.checks import Tags, Warning, register
from django.views.generic.edit import DeletionMixin

from dj_fixi.urlconf import iter_routed_views

from ._utils import PROVIDERS, fx_views, should_run


def _resolves(name) -> bool | None:
    """True/False, or None when we cannot tell and should stay quiet."""
    from django.template import TemplateDoesNotExist
    from django.template.loader import get_template

    try:
        get_template(name)
    except TemplateDoesNotExist:
        return False
    except Exception:
        # Template exists but has a syntax error, or an engine is misconfigured.
        # Django ships no template-syntax check; reporting one under a dj-fixi ID
        # would misattribute it.
        return None
    return True


@register("dj_fixi", Tags.templates)
def check_declared_templates_resolve(app_configs=None, **kwargs):
    """A ``template_name``/``partial_template`` that names nothing."""
    if not should_run(app_configs):
        return []

    messages = []
    seen = set()
    for routed in iter_routed_views():
        view_class = routed.view_class
        if view_class is None or not issubclass(view_class, PROVIDERS):
            continue
        for attribute in ("partial_template", "template_name"):
            name = routed.attr(attribute)
            if not isinstance(name, str) or not name:
                continue
            if (view_class, attribute, name) in seen:
                continue
            seen.add((view_class, attribute, name))
            if _resolves(name) is not False:
                continue
            if "#" in name:
                file, _, part = name.partition("#")
                if django.VERSION >= (6, 0):
                    consequence = (
                        f"{name!r} is Django's template-partial syntax: it needs "
                        f"{{% partialdef {part} %}} inside {file!r}, which does not exist or "
                        "does not define that partial."
                    )
                else:
                    consequence = (
                        f"{name!r} is Django 6.0's template-partial syntax, which this Django "
                        f"({django.get_version()}) does not have. Install django-template-partials, "
                        "or point partial_template at a separate file."
                    )
            elif attribute == "partial_template":
                consequence = (
                    "Fixi requests to this view will raise TemplateDoesNotExist "
                    "(since 0.4.0 an explicit partial never falls through to the page)."
                )
            else:
                consequence = "Requests to this view will fail at render time."
            messages.append(
                Warning(
                    f"{view_class.__name__}.{attribute} = {name!r} does not resolve to a template.",
                    hint=f"{consequence} Fix the name or create the template.",
                    obj=view_class,
                    id="dj_fixi.W201",
                )
            )
    return messages


def _relies_on_user_template_names(view_class) -> bool:
    """Only user code makes the candidate list unpredictable (see W202)."""
    return any(
        "get_template_names" in vars(k)
        for k in view_class.__mro__
        if not k.__module__.startswith(("django.", "dj_fixi."))
    )


@register("dj_fixi", Tags.templates)
def check_no_htmx_attributes(app_configs=None, **kwargs):
    """
    htmx attributes in the project's own templates.

    fixi.js reads six ``fx-*`` attributes and ignores everything else, so an
    ``hx-get`` written from habit renders fine and does nothing. Template source
    is the project's filesystem, which is what a boot-time check is for. Only
    project directories are scanned (never site-packages), comments are
    skipped, and a project that also installs django-htmx is left alone.
    """
    if not should_run(app_configs) or not fx_views():
        return []

    from django.apps import apps

    if apps.is_installed("django_htmx"):
        return []

    from dj_fixi.lint import (
        htmx_attributes_in_source,
        iter_template_files,
        template_directories,
        translate_htmx,
    )

    messages = []
    for path in iter_template_files(template_directories()):
        try:
            names = htmx_attributes_in_source(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        if not names:
            continue
        shown = names[:4]
        more = f" (+{len(names) - 4} more)" if len(names) > 4 else ""
        messages.append(
            Warning(
                f"{path} uses htmx attributes ({', '.join(shown)}{more}); fixi.js ignores them.",
                hint="; ".join(translate_htmx(n) for n in shown)
                + ". Add 'dj_fixi.W203' to SILENCED_SYSTEM_CHECKS if this template is meant "
                "for htmx.",
                obj=str(path),
                id="dj_fixi.W203",
            )
        )
    return messages


@register("dj_fixi", Tags.templates)
def check_a_partial_exists(app_configs=None, **kwargs):
    """
    A dj-fixi view that declares no ``partial_template``.

    Fixi requests to it get ``template_name``, the same page a browser gets,
    swapped into the control's target. Since 0.5 nothing is derived by
    convention, so the only way a view has a fragment is to name it.
    """
    if not should_run(app_configs):
        return []

    messages = []
    seen = set()
    for routed in iter_routed_views():
        view_class = routed.view_class
        if view_class is None or not issubclass(view_class, PROVIDERS):
            continue
        if view_class in seen or routed.attr("partial_template"):
            continue
        seen.add(view_class)

        # A delete view's Fixi path returns 204 No Content from
        # FxResponseMixin and renders nothing at all, so warning that it "will
        # render the full page" would be false.
        if issubclass(view_class, DeletionMixin):
            continue
        if _relies_on_user_template_names(view_class):
            continue
        template_name = routed.attr("template_name")
        if not isinstance(template_name, str) or not template_name:
            continue
        if _resolves(template_name) is not True:
            continue  # W201's problem, not ours

        head, sep, ext = template_name.rpartition(".")
        suggestion = f"{head}_partial.{ext}" if sep else f"{template_name}_partial"
        messages.append(
            Warning(
                f"Fixi requests to {view_class.__name__} get the full page {template_name!r}: "
                "the view declares no partial_template.",
                hint=(
                    f"Set partial_template = {suggestion!r} (or {template_name + '#name'!r} with "
                    "{% partialdef name %} on Django 6). If template_name is itself the fragment, "
                    "add 'dj_fixi.W202' to SILENCED_SYSTEM_CHECKS."
                ),
                obj=view_class,
                id="dj_fixi.W202",
            )
        )
    return messages
