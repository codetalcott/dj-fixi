"""
llms.txt is the agent-facing API reference. It must not drift.

Stale documentation is a silent failure aimed squarely at the reader this project
cares about: an agent trusts the doc and writes code that cannot work. This repo
has already shipped two instances -- a README example that answered 405 forever,
and a development guide describing request.fx_target, removed in 0.2.0. These
tests pin the parts most likely to rot.
"""

import pathlib
import re

import pytest

LLMS = pathlib.Path(__file__).resolve().parent.parent / "llms.txt"


@pytest.fixture(scope="module")
def text():
    return LLMS.read_text()


def test_llms_txt_exists():
    assert LLMS.is_file()


def test_documented_check_ids_match_the_registered_ones(text):
    from django.core.checks import registry

    import dj_fixi.checks  # noqa: F401  (registration)

    # Scope to the "## Check IDs" table: an ID mentioned only in the silencing
    # example elsewhere in the file would otherwise satisfy this vacuously.
    # Match only the indented table rows. Slicing the whole section would also
    # pick up the SILENCED_SYSTEM_CHECKS example below it, which mentions an ID
    # without documenting it -- enough to satisfy this test vacuously.
    table = text.split("## Check IDs", 1)[1].split("\n##", 1)[0]
    documented = set(re.findall(r"^ +(dj_fixi\.[EW]\d{3})\s{2}", table, flags=re.M))
    registered = set()
    for check in registry.registry.get_checks(include_deployment_checks=False):
        source = pathlib.Path(check.__code__.co_filename)
        # Django's own checks also live in a directory called "checks", so match
        # on the package path, not the parent directory name.
        if "dj_fixi" in source.parts:
            registered |= set(re.findall(r'id="(dj_fixi\.[EW]\d{3})"', source.read_text()))
    assert registered, "found no dj-fixi checks; this test would pass vacuously"

    assert documented == registered, (
        f"llms.txt is out of sync. Only in doc: {documented - registered}. "
        f"Only in code: {registered - documented}."
    )


def test_documented_swap_values_match_the_code(text):
    from dj_fixi.templatetags.fixi_tags import SWAP_VALUES

    line = next(
        block for block in text.split("\n\n") if "Valid swap" in block or "valid swap" in block
    )
    for canonical in set(SWAP_VALUES.values()):
        assert canonical in line, f"{canonical!r} is accepted but undocumented"


@pytest.mark.parametrize(
    "name",
    [
        "is_fx",
        "FxView",
        "FxTemplateView",
        "FxResponseMixin",
        "ContextPersistenceMixin",
        "OptimizedQueryMixin",
        "FxMiddleware",
        "render_fx",
    ],
)
def test_names_documented_under_dj_fixi_are_importable(name, text):
    import dj_fixi

    assert name in text, f"{name} is exported but missing from llms.txt"
    assert hasattr(dj_fixi, name)


@pytest.mark.parametrize(
    "module,name",
    [
        ("dj_fixi.testing", "FxTestClient"),
        ("dj_fixi.testing", "assert_no_fixi_check_issues"),
        ("dj_fixi.testing", "fixi_check_messages"),
        ("dj_fixi.urlconf", "iter_routed_views"),
        ("dj_fixi.urlconf", "routed_view_classes"),
        ("dj_fixi.urlconf", "RoutedView"),
        ("dj_fixi.forms", "FxForm"),
        ("dj_fixi.forms", "InlineEditForm"),
        ("dj_fixi.forms", "FxModelForm"),
    ],
)
def test_documented_symbols_resolve(module, name, text):
    import importlib

    assert name in text, f"{module}.{name} is documented nowhere in llms.txt"
    assert hasattr(importlib.import_module(module), name)


def test_every_documented_template_tag_is_registered(text):
    from dj_fixi.templatetags.fixi_tags import register

    for tag in register.tags:
        assert f"{{% {tag} " in text or f"{{% {tag} %}}" in text, f"{tag} is undocumented"


def test_no_reference_to_attributes_removed_in_0_2_0(text):
    """request.fx_target and friends never existed after 0.2.0."""
    for dead in ("request.fx_target", "request.fx_swap", "request.fx_trigger"):
        assert f"{dead} =" not in text and f"= {dead}" not in text
