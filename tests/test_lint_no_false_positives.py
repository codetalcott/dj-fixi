"""
Correct Fixi code produces no lint findings.

The discipline file for dj_fixi.lint, modelled on the one for the system checks:
every rule was written against this corpus first. Anything fixi.js genuinely
accepts, and anything dj-fixi's own emitters produce, must come out clean.
"""

from django import forms
from django.template import Context, Template

from dj_fixi.forms import FxForm, InlineEditForm
from dj_fixi.lint import lint_html


class SimpleForm(forms.Form):
    name = forms.CharField()


def page(body: str, scripts: str = '<script src="/static/dj_fixi/fixi.js"></script>') -> str:
    return f"<!doctype html><html><head>{scripts}</head><body>{body}</body></html>"


def render(source: str) -> str:
    return Template("{% load fixi_tags %}" + source).render(Context({}))


def test_everything_fx_attrs_can_emit():
    body = render(
        '<div id="r"></div>'
        "<button {% fx_attrs action='/x/' method='POST' target='#r' swap='innerHTML' trigger='change' %}>a</button>"
        "<a {% fx_attrs action='/y/' %}>b</a>"
        "<form {% fx_attrs action='/z/' method='post' swap='beforeend' target='#r' trigger='submit' %}></form>"
        "<button fx-action='/w/' {% fx_attrs method='delete' target='#r' %}>c</button>"
    )
    assert lint_html(page(body)) == []


def test_everything_fxform_and_inline_edit_form_emit():
    form_html = FxForm(form=SimpleForm(), action="/save/", target="#row-1", swap="innerhtml").render()
    inline = InlineEditForm(form=SimpleForm(), action="/items/5/", row_id="row-5").render()
    assert lint_html(page(f'<div id="row-1"></div><table><tbody>{inline}</tbody></table>{form_html}')) == []


def test_the_demo_apps_shapes():
    body = """
    <form fx-action="/products/" fx-method="GET" fx-target="#product-container" fx-swap="innerHTML">
      <input type="search" name="q"><button type="submit">Search</button></form>
    <div id="product-container">
      <tr id="product-3"><td>
        <button fx-action="/products/3/" fx-target="#product-container" fx-swap="innerHTML">Edit</button>
        <button fx-action="/products/3/delete/" fx-method="DELETE" fx-target="#product-3">Delete</button>
      </td></tr>
      <a href="?page=2" fx-action="." fx-target="#product-container" fx-swap="innerHTML">Next</a>
    </div>
    <form fx-action="/products/create/" fx-method="POST"><input name="name"></form>
    """
    assert lint_html(page(body)) == []


def test_values_fixi_accepts_that_look_odd():
    body = """
    <button fx-action="/x/" fx-trigger="fx:swapped">chained</button>
    <button fx-action="/x/" fx-trigger="dblclick">twice</button>
    <textarea fx-action="/x/" fx-swap="value"></textarea>
    <button fx-action="/x/" fx-swap="none">no swap</button>
    <button fx-action="/x/" fx-swap="morph">paxi</button>
    <button fx-action="/x/" fx-method="head">head</button>
    <button fx-action="/x/" fx-method="QUERY">query</button>
    <button fx-action="/x/" fx-target="tbody">a tag selector</button>
    <button fx-action="/x/" fx-target=".results">a class selector</button>
    <button fx-action="/x/" fx-target="body">the body</button>
    <button fx-action="/x/" fx-target="#r > .inner">a compound selector</button>
    <table><tbody></tbody></table><div class="results"></div><div id="r"><p class="inner"></p></div>
    """
    assert lint_html(page(body)) == []


def test_fx_ignore_and_custom_attributes_are_the_projects_own():
    body = """
    <div fx-ignore><a href="/plain/">plain link</a><button fx-method="POST">inert on purpose</button></div>
    <table fx-table fx-table-search="/search/" fx-table-empty="none" fx-pagination fx-page-status>
      <tr fx-row fx-row-editing fx-row-actions>
        <td fx-field fx-editable fx-cell-editing>x</td>
        <td fx-actions><button fx-action="/rows/1/" fx-method="POST" fx-actions>save</button></td>
      </tr>
    </table>
    """
    assert lint_html(page(body)) == []


def test_a_project_that_mixes_htmx_and_fixi_on_purpose_gets_no_errors():
    both = '<script src="/static/dj_fixi/fixi.js"></script><script src="/static/htmx.min.js"></script>'
    body = '<button hx-get="/h/" hx-target="#r">htmx</button><button fx-action="/f/">fixi</button><div id="r"></div>'
    assert [f for f in lint_html(page(body, both)) if f.level == "error"] == []
    assert [f for f in lint_html('<button hx-get="/h/">fragment</button>') if f.level == "error"] == []


def test_ids_targets_and_pages_that_are_fine():
    body = """
    <img id="spinner"><img id="spinner">
    <button fx-action="/x/" fx-target="#panel">open</button><div id="panel"></div>
    <button fx-action="/x/" fx-target="#later">the target is inserted by an earlier swap</button>
    <template><div id="later"></div></template>
    """
    assert lint_html(page(body)) == []
    assert lint_html(page("<h1>No fixi on this page at all</h1>", scripts="")) == []
    assert lint_html("") == []


def test_a_fragment_referencing_ids_that_live_in_the_page():
    assert lint_html('<tr id="row-1"><td><a fx-action="/rows/1/" fx-target="#row-1">edit</a></td></tr>') == []
    assert lint_html('<a fx-action="/x/" fx-target="#something-on-the-page">x</a>') == []
