"""
Template-resolution checks.

FxView hands an ordered *list* of candidates to TemplateResponse, and
``select_template`` only raises when every candidate is missing. So a typo in
``partial_template`` never errors -- it quietly falls through to the full page,
which fixi then swaps into a div.
"""

from django.core.checks import Tags, Warning, register
from django.views.generic.edit import DeletionMixin

from dj_fixi.mixins import FxResponseMixin
from dj_fixi.urlconf import iter_routed_views

from ._utils import PROVIDERS, should_run


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


def _partial_candidates(view_class, template_name: str) -> list[str]:
    """
    Every partial name dj-fixi would try for this view, derived as it does.

    Deduplicated: FxView and FxResponseMixin derive the same ``_partial`` name
    when the suffix is left at its default, and listing it twice in a hint just
    looks like a bug.
    """
    candidates = []
    if template_name.endswith(".html"):
        candidates.append(template_name.replace(".html", "_partial.html"))
    if issubclass(view_class, FxResponseMixin):
        suffix = getattr(view_class, "fx_template_suffix", "_partial")
        head, _, ext = template_name.rpartition(".")
        if head:
            candidates.append(f"{head}{suffix}.{ext}")
        directory, _, leaf = template_name.rpartition("/")
        if directory:
            candidates.append(f"{directory}/fragments/{leaf}")
    return list(dict.fromkeys(candidates))


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
            if attribute == "partial_template":
                consequence = (
                    "Fixi requests silently fall through to the next candidate -- "
                    "usually the full page -- because FxView passes a candidate "
                    "list to TemplateResponse, and select_template() only raises "
                    "when every candidate is missing."
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


@register("dj_fixi", Tags.templates)
def check_a_partial_exists(app_configs=None, **kwargs):
    """
    A dj-fixi view that can only ever render the full page.

    The narrowest useful form of "the fragment story was never wired up": only
    fires when the view declares no partial, overrides nothing, and none of the
    names dj-fixi would derive exist either.
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
        # FxResponseMixin.form_valid and renders nothing at all, so warning that
        # it "will render the full page" would be false. (Loading the
        # confirmation into a modal via Fixi is possible but unusual; a warning
        # that is wrong on the common case does not earn its noise.)
        if issubclass(view_class, DeletionMixin):
            continue

        # Only user code makes the candidate list unpredictable. Django's own
        # generic mixins derive full-page names ("auth/group_list.html"), which
        # FxView appends *after* the partial candidates, so they do not count as
        # a fragment and must not suppress this check.
        if any(
            "get_template_names" in vars(k)
            for k in view_class.__mro__
            if not k.__module__.startswith(("django.", "dj_fixi."))
        ):
            continue

        template_name = routed.attr("template_name")
        if not isinstance(template_name, str) or not template_name:
            continue
        if _resolves(template_name) is not True:
            continue  # W201's problem, not ours

        candidates = _partial_candidates(view_class, template_name)
        if not candidates or any(_resolves(c) is not False for c in candidates):
            continue

        messages.append(
            Warning(
                f"Fixi requests to {view_class.__name__} will render the full page "
                f"{template_name!r} into the swap target: no partial template exists.",
                hint=(
                    f"Create one of {', '.join(repr(c) for c in candidates)}, or set "
                    "partial_template explicitly. Add 'dj_fixi.W202' to "
                    "SILENCED_SYSTEM_CHECKS if this view intentionally swaps a "
                    "whole page."
                ),
                obj=view_class,
                id="dj_fixi.W202",
            )
        )
    return messages
