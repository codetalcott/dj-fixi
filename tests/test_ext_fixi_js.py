"""
ext-fixi.js is small on purpose, and these tests are what keeps it that way.

dj-fixi is not growing into htmx. An extension attribute is admitted only when
it closes a silent failure or data loss (or a shipped demo needs it), fixi's
own README already sketches it under that name, its value is one scalar, and
it adds nothing to the wire. If you are here to raise a number or add a name,
read "Extension attributes" in CLAUDE.md first, and say why in the changelog.
"""

import pathlib
import re

from dj_fixi import attrs

STATIC = pathlib.Path(__file__).resolve().parent.parent / "dj_fixi/static/dj_fixi"
EXT = (STATIC / "ext-fixi.js").read_text()
FIXI = (STATIC / "fixi.js").read_text()

#: Lines of code, not counting blanks and comments. The file is 30 today.
CODE_LINE_BUDGET = 40


def code_lines(source: str) -> list[str]:
    body = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    return [ln for ln in body.splitlines() if ln.strip() and not ln.strip().startswith("//")]


def test_the_vocabulary_is_closed():
    assert attrs.EXT_ATTRIBUTES == {"ext-fx-confirm", "ext-fx-debounce"}


def test_the_script_implements_exactly_the_vocabulary():
    implemented = set(re.findall(r'"(ext-fx-[a-z-]+)"', EXT))
    assert implemented == set(attrs.EXT_ATTRIBUTES)


def test_the_script_stays_small():
    assert len(code_lines(EXT)) <= CODE_LINE_BUDGET


def test_it_adds_no_request_header_but_csrf_and_reads_no_response_header():
    assert EXT.count("cfg.headers[") == 1 and "cfg.headers[csrfHeader]" in EXT
    assert "response" not in "\n".join(code_lines(EXT))


def test_csrf_is_only_sent_to_this_origin_and_only_on_unsafe_methods():
    assert "SAFE = /^(GET|HEAD|OPTIONS|TRACE)$/" in EXT
    assert "!SAFE.test(cfg.method) && sameOrigin(cfg.action)" in EXT


def test_fixi_js_lines_the_extensions_depend_on():
    assert 'let go = send(elt, "config", {cfg, requests:reqs})' in FIXI
    assert "if (!go || cfg.drop) return" in FIXI
    assert "let result = await cfg.confirm()" in FIXI
    assert "drop:reqs.size," in FIXI
    assert "abort:ac.abort.bind(ac)," in FIXI
    assert 'send(elt, "inited", {}, false)' in FIXI  # does not bubble: we listen in capture
    assert "elt.addEventListener(elt.__fixi.evt, elt.__fixi, options)" in FIXI
