"""
E101/W102 -- the check that justifies the module.

``class V(ListView, FxView)`` renders fine, returns 200, and silently serves the
full page to every Fixi request with is_fx missing from the context. The rule: a
dj-fixi hook at MRO index i is reachable only if *every* class before it that
defines the same hook calls super(). Scanning the whole prefix rather than only
the winner is what catches CreateView, where ModelFormMixin.form_valid does call
super but FormMixin.form_valid terminates the chain first.
"""

import pytest
from django.test import override_settings
from django.views.generic import CreateView, DeleteView, ListView

from dj_fixi.checks._utils import calls_super, shadowed_hooks
from dj_fixi.mixins import ContextPersistenceMixin, FxResponseMixin, OptimizedQueryMixin
from dj_fixi.views import FxView

from .checks_support import TEMPLATES, check_ids


def hooks(*bases):
    return sorted({hook for hook, _, _ in shadowed_hooks(type("V", bases, {}))})


# The specification of E101, as a table.
@pytest.mark.parametrize(
    "bases,expected",
    [
        ((FxView, ListView), []),
        ((FxResponseMixin, CreateView), []),
        ((ContextPersistenceMixin, OptimizedQueryMixin, FxView, ListView), []),
        ((ListView, FxView), ["get_context_data", "get_template_names"]),
        (
            (CreateView, FxResponseMixin),
            [
                "form_invalid",
                "form_valid",
                "get_context_data",
                "get_success_url",
                "get_template_names",
            ],
        ),
        (
            (DeleteView, FxResponseMixin),
            [
                "delete",
                "form_invalid",
                "form_valid",
                "get_context_data",
                "get_success_url",
                "get_template_names",
            ],
        ),
        ((ListView, ContextPersistenceMixin), ["get_context_data", "get_queryset"]),
        ((FxView, ListView, OptimizedQueryMixin), ["get_queryset"]),
    ],
    ids=[
        "good-fxview-first",
        "good-fxresponse-first",
        "good-full-stack",
        "bad-listview-first",
        "bad-createview-first",
        "bad-deleteview-first",
        "bad-contextpersistence-last",
        "bad-optimizedquery-last",
    ],
)
def test_shadowed_hooks_table(bases, expected):
    assert hooks(*bases) == expected


class TestCallsSuper:
    def test_distinguishes_the_real_chain_terminator(self):
        """MultipleObjectMixin cooperates; ContextMixin is where the chain dies.

        Exactly why shadowed_hooks scans the whole MRO prefix rather than just
        the winning implementation.
        """
        from django.views.generic.base import ContextMixin

        assert calls_super(ListView.get_context_data) is True
        assert calls_super(ContextMixin.get_context_data) is False

    def test_true_for_a_cooperative_method(self):
        class C:
            def hook(self):
                return super().hook()

        assert calls_super(C.hook) is True

    def test_false_for_a_terminating_method(self):
        class C:
            def hook(self):
                return {}

        assert calls_super(C.hook) is False

    def test_stays_quiet_when_it_cannot_tell(self):
        """Bias toward silence: anything unrecognizable reads as cooperative."""
        assert calls_super(object()) is True

    def test_sees_through_functools_wraps(self):
        import functools

        def deco(fn):
            @functools.wraps(fn)
            def wrapper(*a, **kw):
                return fn(*a, **kw)

            return wrapper

        class C:
            @deco
            def hook(self):
                return super().hook()

        assert calls_super(C.hook) is True


class TestCheckOutput:
    def test_bad_order_is_an_error(self):
        with override_settings(ROOT_URLCONF="tests.urlconfs.bad_mro", TEMPLATES=TEMPLATES):
            assert "dj_fixi.E101" in check_ids()

    def test_user_override_is_a_warning(self):
        with override_settings(ROOT_URLCONF="tests.urlconfs.user_shadow", TEMPLATES=TEMPLATES):
            found = check_ids()
            assert "dj_fixi.W102" in found and "dj_fixi.E101" not in found

    def test_message_names_the_dead_hook_and_the_shadowing_class(self):
        from django.core.checks import run_checks

        with override_settings(ROOT_URLCONF="tests.urlconfs.bad_mro", TEMPLATES=TEMPLATES):
            errors = [m for m in run_checks(tags=["dj_fixi"]) if m.id == "dj_fixi.E101"]
        text = " ".join(m.msg for m in errors)
        assert "get_template_names" in text
        assert "TemplateResponseMixin" in text
        assert any("Reorder the bases" in (m.hint or "") for m in errors)

    def test_good_order_produces_no_mro_findings(self):
        with override_settings(ROOT_URLCONF="tests.urlconfs.good", TEMPLATES=TEMPLATES):
            found = check_ids()
            assert "dj_fixi.E101" not in found and "dj_fixi.W102" not in found
