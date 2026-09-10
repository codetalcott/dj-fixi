"""View-level checks: MRO ordering, and views that cannot answer a request."""

from django.core.checks import Error, Tags, Warning, register
from django.views import View

from dj_fixi.urlconf import routed_view_classes
from dj_fixi.views import FxView

from ._utils import fx_views, shadowed_hooks, should_run


@register("dj_fixi", Tags.urls)
def check_view_mro(app_configs=None, **kwargs):
    """
    dj-fixi hooks that a base-class ordering has made unreachable.

    ``class V(ListView, FxView)`` still renders, still returns 200, and silently
    serves the full page to every Fixi request with ``is_fx`` missing from the
    context. Nothing raises, which is why this is worth an Error.
    """
    if not should_run(app_configs):
        return []

    messages = []
    for view_class, routed in fx_views().items():
        for hook, owner, shadowing in shadowed_hooks(view_class):
            django_class = shadowing.__module__.startswith("django.")
            detail = (
                f"{view_class.__name__} lists {shadowing.__name__} before "
                f"{owner.__name__}, so {owner.__name__}.{hook}() never runs "
                f"(routed at {routed.route!r})."
            )
            if django_class:
                messages.append(
                    Error(
                        detail,
                        hint=(
                            f"Reorder the bases so dj-fixi classes come first: "
                            f"class {view_class.__name__}({owner.__name__}, ...). "
                            "Django's generic view mixins do not call super() in "
                            "these hooks, so anything after them in the MRO is "
                            "dead code."
                        ),
                        obj=view_class,
                        id="dj_fixi.E101",
                    )
                )
            else:
                messages.append(
                    Warning(
                        detail,
                        hint=(
                            f"Call super().{hook}(...) in "
                            f"{shadowing.__name__}.{hook}, or silence dj_fixi.W102 "
                            "if the override is deliberate."
                        ),
                        obj=view_class,
                        id="dj_fixi.W102",
                    )
                )
    return messages


def _has_http_handler(view_class) -> bool:
    # "options" is excluded because View always defines it.
    return any(hasattr(view_class, m) for m in View.http_method_names if m != "options")


def _overrides_dispatch(view_class) -> bool:
    return any("dispatch" in vars(k) for k in view_class.__mro__ if k is not View)


@register("dj_fixi", Tags.urls)
def check_view_has_handler(app_configs=None, **kwargs):
    """
    Routed FxView subclasses that answer every request with 405.

    FxView is a base class and supplies no handlers. A subclass with only
    ``template_name`` looks complete and returns 405 forever, raising nothing.
    """
    if not should_run(app_configs):
        return []

    messages = []
    for view_class, routed in routed_view_classes(FxView).items():
        if _has_http_handler(view_class) or _overrides_dispatch(view_class):
            continue
        messages.append(
            Error(
                f"{view_class.__name__} is routed at {routed.route!r} but defines no "
                "get(), post(), or other HTTP handler, so every request to it "
                "returns 405 Method Not Allowed.",
                hint=(
                    "Subclass FxTemplateView, which supplies get(), or compose "
                    "FxView with a Django generic view. FxView is a base class "
                    "only and deliberately provides no handlers."
                ),
                obj=view_class,
                id="dj_fixi.E103",
            )
        )
    return messages


@register("dj_fixi", Tags.urls)
def check_view_has_template_source(app_configs=None, **kwargs):
    """
    Routed FxView subclasses with no way to name a template.

    Already loud at request time (ImproperlyConfigured); this just moves it to
    boot, where an agent iterating on configuration will actually see it.
    """
    if not should_run(app_configs):
        return []

    from django.views.generic.base import TemplateResponseMixin

    messages = []
    for view_class, routed in routed_view_classes(FxView).items():
        if routed.attr("template_name") or routed.attr("partial_template"):
            continue
        # Any of these can supply a name, so stay quiet.
        if issubclass(view_class, TemplateResponseMixin):
            continue
        if routed.attr("model") is not None or routed.attr("queryset") is not None:
            continue
        if any(
            "get_template_names" in vars(k) or "render_to_response" in vars(k)
            for k in view_class.__mro__
            if k not in (FxView, View)
        ):
            continue
        messages.append(
            Error(
                f"{view_class.__name__} (routed at {routed.route!r}) sets neither "
                "template_name nor partial_template, and nothing in its MRO can "
                "derive a template name.",
                hint=(
                    "Set template_name on the class, pass it to as_view(), or "
                    "override get_template_names()."
                ),
                obj=view_class,
                id="dj_fixi.E104",
            )
        )
    return messages
