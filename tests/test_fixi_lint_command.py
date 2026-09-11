"""manage.py fixi_lint: template source, without rendering."""

import io

import pytest
from django.core.management import CommandError, call_command
from django.test import override_settings

from dj_fixi.lint import lint_template_source, strip_template_syntax

from .checks_support import GOOD_FILES, fs_templates


def ids(findings):
    return [f.id for f in findings]


def test_template_syntax_becomes_html_the_parser_can_judge():
    source = (
        '{% load fixi_tags %}{# <a hx-get="/old/"> #}\n'
        "<a fx-action=\"{% url 'x' %}\" fx-swap=\"outerhtml\">x</a>\n"
        "<button {% fx_attrs action='/y/' method='POST' %}>y</button>\n"
        '{% if ok %}<b fx-target="{{ sel }}" fx-action="{{ u }}">z</b>{% endif %}\n'
        '{% comment %}\nhx-post="/gone/"\n{% endcomment %}<i fx-swap="innerHTML">no action</i>'
    )
    findings = lint_template_source(source, file="t.html")
    assert ids(findings) == ["dj_fixi.L103", "dj_fixi.L110"]
    assert findings[0].line == 2 and findings[0].file == "t.html"  # {% url %} is a value, not an empty action
    assert findings[1].line == 7  # comment lines still count
    stripped = strip_template_syntax(source)
    assert "hx-get" not in stripped and "hx-post" not in stripped
    assert 'fx-action="{{VAR}}"' in stripped  # the fx_attrs element counts as a control


def test_source_mode_leaves_page_level_rules_off():
    """A template that extends a layout cannot know the page's ids."""
    assert lint_template_source('<a fx-action="/x/" fx-target="#defined-in-layout">x</a>') == []


def test_command_reports_findings_with_file_and_line_and_fails(tmp_path):
    (tmp_path / "bad.html").write_text('<button hx-post="/x/">x</button>\n<a fx-action="/y/" fx-swap="outerhtml">y</a>')
    out = io.StringIO()
    with pytest.raises(CommandError, match="1 error"):
        call_command("fixi_lint", str(tmp_path), stdout=out)
    text = out.getvalue()
    assert "(dj_fixi.L101)" in text and f"{tmp_path / 'bad.html'}:1" in text
    assert "(dj_fixi.L103)" in text and "bad.html:2" in text
    assert "1 template(s), 1 error(s), 1 warning(s)" in text


def test_command_is_quiet_on_clean_templates_and_strict_on_request(tmp_path):
    (tmp_path / "ok.html").write_text('{% load fixi_tags %}<a {% fx_attrs action="/x/" %}>x</a>')
    (tmp_path / "warn.html").write_text('<button hx-get="/x/">x</button>')
    out = io.StringIO()
    call_command("fixi_lint", str(tmp_path / "ok.html"), stdout=out)
    assert "1 template(s), 0 error(s), 0 warning(s)" in out.getvalue()
    call_command("fixi_lint", str(tmp_path / "warn.html"), stdout=io.StringIO())
    with pytest.raises(CommandError):
        call_command("fixi_lint", str(tmp_path / "warn.html"), warnings_as_errors=True, stdout=io.StringIO())


def test_command_defaults_to_the_projects_template_directories(tmp_path):
    files = {**GOOD_FILES, "mixed.html": '<a fx-action="/x/" fx-trigger="keyup delay:200ms">x</a>'}
    out = io.StringIO()
    with override_settings(TEMPLATES=fs_templates(tmp_path, files)):
        with pytest.raises(CommandError):
            call_command("fixi_lint", stdout=out)
    assert "(dj_fixi.L105)" in out.getvalue() and "mixed.html" in out.getvalue()
