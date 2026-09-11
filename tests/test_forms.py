"""Tests for dj_fixi.forms (FxForm, InlineEditForm, FxModelForm)."""

from django import forms
from django.contrib.auth.models import Group

from dj_fixi.forms import FxForm, FxModelForm, InlineEditForm


class SimpleForm(forms.Form):
    name = forms.CharField()


def test_fxform_render_attrs_escapes_values():
    f = FxForm(form=SimpleForm(), action='/a"b', target="#t", swap="outerHTML")
    attrs = f.render_attrs()

    assert 'fx-action="/a&quot;b"' in attrs  # value HTML-escaped
    assert 'fx-target="#t"' in attrs
    assert 'fx-method="POST"' in attrs


def test_fxform_render_structure():
    f = FxForm(form=SimpleForm(), action="/save", target="#t")
    html = f.render()

    assert "<form" in html
    assert "Save" in html and "Cancel" in html
    assert 'name="name"' in html


def test_inline_edit_form_uses_cancel_action():
    f = InlineEditForm(
        form=SimpleForm(),
        action="/items/5/update/",
        row_id="row-5",
        cancel_action="/items/5/row/",
    )
    html = f.render()

    assert 'id="row-5"' in html
    assert 'fx-action="/items/5/row/"' in html  # cancel button
    assert "/items/5/update/" in html  # submit action still present


def test_inline_edit_form_cancel_falls_back_to_action():
    """No cancel_action -> reuse action (no silent /update/->/row/ rewrite)."""
    f = InlineEditForm(form=SimpleForm(), action="/items/5/edit/", row_id="row-5")
    html = f.render()

    assert "/row/" not in html  # the old magic rewrite is gone
    assert html.count("/items/5/edit/") >= 2  # form action + cancel button


def test_fxmodelform_as_fx_form():
    class GForm(FxModelForm):
        class Meta:
            model = Group
            fields = ["name"]

    html = GForm().as_fx_form(action="/save", target="#t")

    assert "<form" in html
    assert "Save" in html


def test_fxmodelform_as_fx_inline_threads_cancel_action():
    class GForm(FxModelForm):
        class Meta:
            model = Group
            fields = ["name"]

    html = GForm().as_fx_inline(target="#row-1", action="/g/1/update/", cancel_action="/g/1/row/")

    assert 'id="row-1"' in html
    assert 'fx-action="/g/1/row/"' in html


# ------------------------------------------------------------- validation (0.4.0)


def test_fxform_normalizes_swap_like_the_tag():
    """FxForm emitted the raw swap; 'innerhtml' made fixi throw and swap nothing."""
    f = FxForm(form=SimpleForm(), action="/save", swap="innerhtml")
    assert 'fx-swap="innerHTML"' in f.render_attrs()


def test_fxform_rejects_values_fixi_cannot_act_on():
    import pytest

    with pytest.raises(ValueError, match="not something fixi.js recognizes"):
        FxForm(form=SimpleForm(), action="/save", swap="replace").render_attrs()
    with pytest.raises(ValueError, match="not one event name"):
        FxForm(form=SimpleForm(), action="/save", trigger="submit, change").render_attrs()
    with pytest.raises(ValueError, match="undefined"):
        FxForm(form=SimpleForm(), action="").render_attrs()
    with pytest.raises(ValueError, match="fetch\\(\\) refuses"):
        FxForm(form=SimpleForm(), action="/save", method="TRACE").render_attrs()
