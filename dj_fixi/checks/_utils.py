"""
Shared predicates for the system checks.

Every predicate here defaults to "fine" when it cannot decide. A check that
guesses wrong in the noisy direction is worse than no check at all: an Error
stops ``runserver``, so a false positive does not annoy someone, it blocks them.
"""

import inspect

from dj_fixi.mixins import ContextPersistenceMixin, FxResponseMixin, OptimizedQueryMixin
from dj_fixi.urlconf import routed_view_classes
from dj_fixi.views import FxView

#: dj-fixi classes whose hooks can be silently shadowed by a bad base order.
PROVIDERS = (FxView, FxResponseMixin, ContextPersistenceMixin, OptimizedQueryMixin)

#: Hooks dj-fixi relies on reaching. Each is cooperative: dj-fixi's version calls
#: super(), and expects everything ahead of it in the MRO to do the same.
COOPERATIVE_HOOKS = (
    "get_template_names",
    "get_context_data",
    "get_queryset",
    "form_valid",
    "form_invalid",
)


def should_run(app_configs) -> bool:
    """False when this check does not apply to the app set being checked."""
    from django.apps import apps

    if app_configs is not None and not any(c.label == "dj_fixi" for c in app_configs):
        return False
    return apps.is_installed("dj_fixi")


def fx_views(urlconf=None) -> dict:
    """
    Routed dj-fixi view classes -- the evidence gate for every settings check.

    Not memoized on purpose. ``get_resolver`` is already cached by Django and
    ``url_patterns`` is a cached_property, so a repeat walk is a list traversal;
    caching on top of that would just break ``override_settings(ROOT_URLCONF=...)``.
    """
    return routed_view_classes(PROVIDERS, urlconf)


def calls_super(func) -> bool:
    """
    True unless we can prove ``func`` terminates the MRO chain.

    A bytecode heuristic, biased toward silence: anything unrecognizable reads as
    cooperative and produces no message.
    """
    func = inspect.unwrap(func)
    code = getattr(func, "__code__", None)
    if code is None:
        return True
    return "__class__" in code.co_freevars or "super" in code.co_names


def shadowed_hooks(cls) -> list[tuple[str, type, type]]:
    """
    Return ``(hook, dj_fixi_owner, shadowing_class)`` for every dead dj-fixi hook.

    A dj-fixi implementation at MRO index *i* is reachable only if **every** class
    before it that defines the same hook calls ``super()``. Scanning the whole
    prefix rather than only the winner is what catches CreateView:
    ``ModelFormMixin.form_valid`` does call super, but ``FormMixin.form_valid``
    terminates the chain before ``FxResponseMixin`` is ever reached.
    """
    mro = cls.__mro__
    found = []
    for index, owner in enumerate(mro):
        if owner not in PROVIDERS:
            continue
        for hook in COOPERATIVE_HOOKS:
            if hook not in vars(owner):
                continue
            for earlier in mro[:index]:
                impl = vars(earlier).get(hook)
                if impl is not None and not calls_super(impl):
                    found.append((hook, owner, earlier))
                    break
    return found
