"""
Lint rendered HTML for what fixi.js silently ignores.

Coding agents know htmx far better than Fixi and write htmx into a Fixi app:
``hx-get``, ``hx-swap="innerHTML swap:1s"``, ``hx-trigger="keyup delay:200ms"``.
fixi.js reads six attributes and ignores the rest, so every one of those
mistakes renders a 200 and does nothing in the browser. This module makes them
loud on the surface an agent actually looks at: the responses a test fetches.

    from dj_fixi.testing import FxTestClient   # lints every text/html response

    from dj_fixi.lint import lint_html, lint_response
    findings = lint_html(html)                 # or lint_response(response)

Each rule names the line of the vendored ``dj_fixi/static/dj_fixi/fixi.js`` it
comes from, and every rule was checked against correct Fixi code first
(``tests/test_lint_no_false_positives.py``). Custom ``fx-*`` attributes are
the project's own (``fx:config`` listeners read them) and are never errors.
Findings carry ids (``dj_fixi.L101`` ...) that ``SILENCED_SYSTEM_CHECKS`` and
``FxTestClient(lint_ignore=...)`` both silence.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Iterable
from dataclasses import dataclass
from html.parser import HTMLParser

from .attrs import (
    FX_ATTRIBUTES,
    FX_CONTROL_ATTRIBUTES,
    SWAP_VALUES,
    validate_method,
    validate_trigger,
)

__all__ = [
    "Finding",
    "FxLintError",
    "FxLintWarning",
    "Node",
    "lint_html",
    "lint_response",
    "format_findings",
    "translate_htmx",
    "FINDING_IDS",
    "template_directories",
    "iter_template_files",
    "htmx_attributes_in_source",
    "lint_template_source",
    "strip_template_syntax",
]

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}

#: Every finding this module can produce, for llms.txt and SILENCED_SYSTEM_CHECKS.
FINDING_IDS = {
    "dj_fixi.L101": "htmx attribute; fixi reads only fx-*",
    "dj_fixi.L102": "fx-* attribute that looks like a typo of a real one",
    "dj_fixi.L103": "fx-swap spelled in the wrong case; fixi throws and swaps nothing",
    "dj_fixi.L104": "fx-swap value fixi has no swap for (it assigns that element property)",
    "dj_fixi.L105": "fx-trigger with spaces or commas; fixi waits for an event named exactly that",
    "dj_fixi.L106": "fx-method fetch() refuses; fixi swallows the error",
    "dj_fixi.L107": 'fx-action=""; fixi fetches ./undefined',
    "dj_fixi.L108": "fx-target matches nothing on this page; fixi swaps into the element itself",
    "dj_fixi.L109": "an id that fx-target points at appears more than once; fixi takes the first",
    "dj_fixi.L110": "fx-method/target/swap/trigger on an element with no fx-action; fixi never initialises it",
    "dj_fixi.L111": "a full HTML document answering a Fixi request",
}

_HTMX_TRANSLATIONS = {
    "hx-get": 'fx-action="..." (GET is fixi\'s default method)',
    "hx-post": 'fx-action="..." fx-method="POST"',
    "hx-put": 'fx-action="..." fx-method="PUT"',
    "hx-patch": 'fx-action="..." fx-method="PATCH"',
    "hx-delete": 'fx-action="..." fx-method="DELETE"',
    "hx-target": 'fx-target="<css selector>" (no "this", no closest/next/previous/find: those match nothing and fixi swaps into the element itself)',
    "hx-swap": "fx-swap with one keyword and no modifiers; note fixi's default is outerHTML where htmx's is innerHTML",
    "hx-trigger": "fx-trigger with one event name and no modifiers",
    "hx-confirm": "no attribute; set cfg.confirm in an fx:config listener",
}
_NO_EQUIVALENT = ("hx-boost", "hx-push-url", "hx-replace-url", "hx-include", "hx-vals", "hx-select", "hx-select-oob", "hx-swap-oob", "hx-indicator", "hx-sync", "hx-disable", "hx-ext", "hx-headers", "hx-encoding", "hx-preserve", "hx-history")


def translate_htmx(name: str) -> str:
    """What to write instead of an htmx attribute, or why there is nothing."""
    base = name[5:] if name.startswith("data-hx-") else name
    if base in _HTMX_TRANSLATIONS:
        return f"{base} -> {_HTMX_TRANSLATIONS[base]}"
    if base.startswith("hx-on"):
        return f"{base} -> no equivalent; use addEventListener, or fx:* events for fixi's lifecycle"
    for known in _NO_EQUIVALENT:
        if base == known or base.startswith(known + ":"):
            return f"{base} -> no fixi equivalent"
    return f"{base} -> not an htmx attribute fixi has any equivalent for"


# ------------------------------------------------------------------- findings


@dataclass(frozen=True)
class Finding:
    id: str
    level: str  # error | warning
    message: str
    line: int
    column: int
    element: str
    fixi_line: str | None = None
    file: str | None = None

    def __str__(self) -> str:
        where = f"{self.file}:{self.line}" if self.file else f"line {self.line}:{self.column}"
        source = f" ({self.fixi_line})" if self.fixi_line else ""
        return f"({self.id}) <{self.element}> {where}: {self.message}{source}"


class FxLintError(AssertionError):
    """Raised by ``FxTestClient`` when a response carries an error-level finding."""

    def __init__(self, findings: list[Finding], where: str = ""):
        self.findings = list(findings)
        super().__init__(format_findings(self.findings, where))


class FxLintWarning(UserWarning):
    """A warning-level finding, surfaced through ``warnings.warn`` by ``FxTestClient``."""


def format_findings(findings: Iterable[Finding], where: str = "") -> str:
    findings = list(findings)
    head = f"dj-fixi lint found {len(findings)} issue(s)"
    if where:
        head += f" in {where}"
    lines = [head + ":"] + [f"  {f}" for f in findings]
    lines.append(
        "  Silence an id with SILENCED_SYSTEM_CHECKS or FxTestClient(lint_ignore=...); "
        "see dj_fixi.lint.FINDING_IDS."
    )
    return "\n".join(lines)


# ------------------------------------------------------------------- the tree


class Node:
    __slots__ = ("tag", "attrs", "children", "parent", "line", "column")

    def __init__(self, tag: str, attrs: dict[str, str | None], parent: Node | None, pos: tuple[int, int]):
        self.tag = tag
        self.attrs = attrs
        self.children: list[Node] = []
        self.parent = parent
        self.line, self.column = pos

    def descendants(self) -> Iterable[Node]:
        for child in self.children:
            yield child
            yield from child.descendants()

    def ancestors(self) -> Iterable[Node]:
        node = self.parent
        while node is not None:
            yield node
            node = node.parent

    def ignored(self) -> bool:
        """fixi.js:6 skips any element with an ``fx-ignore`` ancestor (or the attribute itself)."""
        return "fx-ignore" in self.attrs or any("fx-ignore" in a.attrs for a in self.ancestors())

    def describe(self) -> str:
        if self.attrs.get("id"):
            return f"{self.tag}#{self.attrs['id']}"
        if self.attrs.get("fx-action"):
            return f'{self.tag} fx-action="{self.attrs["fx-action"]}"'
        return self.tag


class _TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root", {}, None, (0, 0))
        self.stack = [self.root]
        self.scripts: list[str] = []
        self.doctype = False

    def handle_decl(self, decl):
        if decl.lower().startswith("doctype"):
            self.doctype = True

    def handle_starttag(self, tag, attrs):
        node = Node(tag, {k: v for k, v in attrs}, self.stack[-1], self.getpos())
        self.stack[-1].children.append(node)
        if tag == "script" and node.attrs.get("src"):
            self.scripts.append(node.attrs["src"])
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        node = Node(tag, {k: v for k, v in attrs}, self.stack[-1], self.getpos())
        self.stack[-1].children.append(node)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return


def parse(html: str) -> _TreeBuilder:
    builder = _TreeBuilder()
    builder.feed(html)
    builder.close()
    return builder


# ------------------------------------------------------------------- the rules

_ID_TARGET = re.compile(r"^#([\w-]+)$")
_BARE_WORD = re.compile(r"^[A-Za-z][\w-]*$")
_TEMPLATE_VAR = "{{"  # a value still carrying template syntax cannot be judged
_HTMX_EXTENDED = re.compile(r"^(closest|next|previous|find|findAll|this|global)\b")
#: Swap styles that exist in htmx and not in fixi; anything else unknown is an
#: element property fixi will assign (fixi.js:63), which is a documented use.
_HTMX_ONLY_SWAPS = {"delete", "innermorph", "outermorph", "outersync", "before", "after", "prepend", "append", "upsert", "download"}


class _Linter:
    def __init__(self, tree: _TreeBuilder, *, full_document: bool, is_fx: bool | None, file: str | None):
        self.tree = tree
        self.nodes = list(tree.root.descendants())
        self.full_document = full_document
        self.is_fx = is_fx
        self.file = file
        self.findings: list[Finding] = []
        self.ids: dict[str, list[Node]] = {}
        self.tags = {n.tag for n in self.nodes}
        for node in self.nodes:
            if node.attrs.get("id"):
                self.ids.setdefault(node.attrs["id"], []).append(node)
        scripts = " ".join(tree.scripts)
        self.loads_fixi = "fixi" in scripts
        self.loads_htmx = "htmx" in scripts

    def add(self, id_: str, level: str, node: Node, message: str, fixi_line: str | None = None) -> None:
        self.findings.append(Finding(id_, level, message, node.line, node.column, node.describe(), fixi_line, self.file))

    def run(self) -> list[Finding]:
        referenced: dict[str, Node] = {}
        for node in self.nodes:
            if node.ignored():
                continue
            has_action = "fx-action" in node.attrs
            for name, value in node.attrs.items():
                if name.startswith(("hx-", "data-hx-")):
                    self.htmx_attribute(node, name)
                elif name.startswith("fx-"):
                    self.fx_attribute(node, name, value, has_action)
            target = node.attrs.get("fx-target")
            if target and _TEMPLATE_VAR not in target:
                m = _ID_TARGET.match(target.strip())
                if m:
                    referenced[m.group(1)] = node
            if not has_action:
                present = sorted(n for n in node.attrs if n in FX_CONTROL_ATTRIBUTES)
                if present:
                    self.add(
                        "dj_fixi.L110", "warning", node,
                        f"{', '.join(present)} on an element with no fx-action; fixi only initialises elements "
                        "matching [fx-action], so this one does nothing.",
                        "fixi.js:81",
                    )
        for id_, node in referenced.items():
            if len(self.ids.get(id_, [])) > 1:
                self.add(
                    "dj_fixi.L109", "error", self.ids[id_][1],
                    f'id="{id_}" appears {len(self.ids[id_])} times and fx-target="#{id_}" points at it; '
                    "fixi swaps into the first one only.",
                    "fixi.js:21",
                )
        if self.full_document and self.is_fx:
            root = next((n for n in self.nodes if n.tag == "html"), self.nodes[0] if self.nodes else None)
            if root is not None:
                self.add(
                    "dj_fixi.L111", "warning", root,
                    "a full HTML document answered a Fixi request; fixi will swap the whole page into "
                    "the control's target. Render a fragment for Fixi requests (partial_template, render_fx).",
                )
        return self.findings

    def htmx_attribute(self, node: Node, name: str) -> None:
        level = "error" if (self.full_document and self.loads_fixi and not self.loads_htmx) else "warning"
        self.add(
            "dj_fixi.L101", level, node,
            f"{name} is htmx; fixi reads only fx-action, fx-method, fx-target, fx-swap, fx-trigger and "
            f"fx-ignore, so it is ignored. {translate_htmx(name)}.",
            "fixi.js:19-22",
        )

    def fx_attribute(self, node: Node, name: str, value: str | None, has_action: bool) -> None:
        if name not in FX_ATTRIBUTES:
            if has_action and not any(name.startswith(real) for real in FX_ATTRIBUTES):
                close = difflib.get_close_matches(name, sorted(FX_CONTROL_ATTRIBUTES), n=1, cutoff=0.75)
                if close:
                    self.add(
                        "dj_fixi.L102", "warning", node,
                        f"{name} is not a fixi attribute (did you mean {close[0]}?); fixi ignores it.",
                        "fixi.js:19-22",
                    )
            return
        if value is None or _TEMPLATE_VAR in value:
            return
        if name == "fx-swap":
            canonical = SWAP_VALUES.get(value.lower())
            if canonical is None:
                if re.search(r"\s", value):
                    self.add(
                        "dj_fixi.L104", "error", node,
                        f'fx-swap="{value}" carries modifiers, which are htmx; fixi takes one keyword, looks '
                        f'up target["{value}"], finds nothing, throws, and swaps nothing.',
                        "fixi.js:63-65",
                    )
                elif value.lower() in _HTMX_ONLY_SWAPS:
                    self.add(
                        "dj_fixi.L104", "warning", node,
                        f'fx-swap="{value}" is an htmx swap style fixi does not have; fixi assigns '
                        f'target["{value}"] if that property exists and throws otherwise.',
                        "fixi.js:63-65",
                    )
            elif canonical != value:
                self.add(
                    "dj_fixi.L103", "error", node,
                    f'fx-swap="{value}" must be spelled {canonical}; fixi matches case, throws, and swaps nothing.',
                    "fixi.js:63-65",
                )
        elif name == "fx-trigger":
            try:
                validate_trigger(value)
            except ValueError:
                self.add(
                    "dj_fixi.L105", "error", node,
                    f'fx-trigger="{value}" is handed to addEventListener verbatim, so it waits for an event '
                    "named exactly that. One event name, no modifiers.",
                    "fixi.js:74-75",
                )
        elif name == "fx-method":
            try:
                validate_method(value)
            except ValueError:
                self.add(
                    "dj_fixi.L106", "error", node,
                    f'fx-method="{value}" is refused by fetch(); fixi swallows the TypeError and nothing happens.',
                    "fixi.js:51-53",
                )
        elif name == "fx-action":
            if not value.strip():
                self.add(
                    "dj_fixi.L107", "error", node,
                    'fx-action="" is read as undefined; fixi fetches "./undefined". A misspelled template '
                    "variable renders as an empty string.",
                    "fixi.js:5",
                )
        elif name == "fx-target" and self.full_document:
            self.fx_target(node, value.strip())

    def fx_target(self, node: Node, value: str) -> None:
        if _HTMX_EXTENDED.match(value):
            self.add(
                "dj_fixi.L108", "error", node,
                f'fx-target="{value}" is an htmx extended selector, not CSS; querySelector throws on it '
                "and the request never starts.",
                "fixi.js:21",
            )
            return
        m = _ID_TARGET.match(value)
        if m and m.group(1) not in self.ids:
            self.add(
                "dj_fixi.L108", "error", node,
                f'fx-target="{value}" matches nothing on this page; fixi falls back to the element itself and '
                "swaps the response into it.",
                "fixi.js:21",
            )
        elif not m and _BARE_WORD.match(value) and value.lower() not in self.tags:
            hint = f' (did you mean "#{value}"?)' if value in self.ids else ""
            self.add(
                "dj_fixi.L108", "error", node,
                f'fx-target="{value}" is a tag selector and no <{value}> is on this page{hint}; fixi falls back '
                "to the element itself and swaps the response into it.",
                "fixi.js:21",
            )


# --------------------------------------------------------------------- entry


def lint_html(
    html: str,
    *,
    full_document: bool | None = None,
    is_fx: bool | None = None,
    ignore: Iterable[str] = (),
    file: str | None = None,
) -> list[Finding]:
    """
    Findings for one HTML string.

    ``full_document`` decides whether page-level rules run (a target id that is
    missing from a fragment may live in the page); it is detected from a
    doctype or ``<html>`` when not given. ``is_fx`` says whether a Fixi request
    was answered, for the full-document warning. ``ignore`` holds finding ids.
    """
    tree = parse(html)
    if full_document is None:
        full_document = tree.doctype or "html" in {n.tag for n in tree.root.descendants()}
    findings = _Linter(tree, full_document=full_document, is_fx=is_fx, file=file).run()
    silenced = set(ignore) | _silenced_by_settings()
    return [f for f in findings if f.id not in silenced]


def lint_response(response, *, ignore: Iterable[str] = ()) -> list[Finding]:
    """
    Findings for a Django response, or ``[]`` when there is nothing to lint.

    Skips streaming responses, anything that is not ``text/html``, and 5xx
    pages (the technical 500 page is not the project's HTML). Reads
    ``response.wsgi_request`` when the test client attached it, to know whether
    a Fixi request was answered.
    """
    if getattr(response, "streaming", False) or response.status_code >= 500:
        return []
    if not (response.get("Content-Type") or "").startswith("text/html"):
        return []
    body = response.content.decode(response.charset or "utf-8", errors="replace")
    if not body.strip():
        return []
    request = getattr(response, "wsgi_request", None)
    is_fx = None
    if request is not None:
        from .request import is_fx as _is_fx

        is_fx = _is_fx(request)
    return lint_html(body, is_fx=is_fx, ignore=ignore)


def _silenced_by_settings() -> set[str]:
    try:
        from django.conf import settings

        return set(getattr(settings, "SILENCED_SYSTEM_CHECKS", ()))
    except Exception:  # settings not configured: pure-function use
        return set()


# ------------------------------------------------------------ template files

_TEMPLATE_COMMENT = re.compile(r"\{#.*?#\}|\{%\s*comment\b.*?%\}.*?\{%\s*endcomment\s*%\}", re.S)
_HTMX_IN_SOURCE = re.compile(r"\b((?:data-)?hx-[a-z][\w:.-]*)\s*=")


def template_directories() -> list:
    """
    Every directory a DjangoTemplates engine reads project templates from.

    The engine's ``DIRS`` plus what each loader reports through ``get_dirs()``
    (app template directories), the algorithm ``django.template.autoreload``
    uses, replicated here because importing that module registers autoreload
    receivers. Directories under site-packages are left out: a third-party
    app's templates are that app's business.
    """
    import sysconfig
    from pathlib import Path

    from django.template import engines
    from django.template.backends.django import DjangoTemplates

    site = {Path(sysconfig.get_paths()[k]).resolve() for k in ("purelib", "platlib")}
    seen: list = []
    try:
        backends = list(engines.all())
    except Exception:
        # A backend that cannot even be instantiated (Jinja2 without jinja2
        # installed) is Django's own error to report, not a lint's.
        return []
    for backend in backends:
        if not isinstance(backend, DjangoTemplates):
            continue
        dirs = list(backend.engine.dirs)
        for loader in backend.engine.template_loaders:
            dirs += getattr(loader, "get_dirs", lambda: [])()
        for d in dirs:
            path = Path(d).resolve()
            if path in seen or any(path.is_relative_to(s) for s in site):
                continue
            seen.append(path)
    return seen


def iter_template_files(directories, suffixes=(".html", ".htm")):
    for directory in directories:
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*")):
            if path.suffix in suffixes and path.is_file():
                yield path


def htmx_attributes_in_source(source: str) -> list[str]:
    """Distinct htmx attribute names written in template source, comments excluded."""
    stripped = _TEMPLATE_COMMENT.sub("", source)
    return sorted(set(_HTMX_IN_SOURCE.findall(stripped)))


# ------------------------------------------------------------ template source

_VAR = "{{VAR}}"  # what a computed value becomes; rules skip values containing "{{"
_BLOCK_TAGS = re.compile(
    r"^(?:if|elif|else|endif|for|empty|endfor|block|endblock|extends|load|with|endwith|"
    r"spaceless|endspaceless|autoescape|endautoescape|verbatim|endverbatim|include|"
    r"blocktrans(?:late)?|endblocktrans(?:late)?|filter|endfilter|ifchanged|endifchanged|"
    r"partialdef|endpartialdef|partial|regroup|cycle|resetcycle|debug|templatetag|lorem)\b"
)
_FX_ATTRS_TAG = re.compile(r"\{%\s*fx_attrs\b.*?%\}", re.S)
_TAG = re.compile(r"\{%.*?%\}", re.S)
_EXPR = re.compile(r"\{\{.*?\}\}", re.S)


def _keep_lines(match, filler: str) -> str:
    return "\n" * match.group(0).count("\n") + filler


def strip_template_syntax(source: str) -> str:
    """
    Django template source as HTML the parser can read, line numbers intact.

    Comments go. ``{% fx_attrs ... %}`` becomes an ``fx-action`` with a computed
    value, so the element counts as a control and the rules do not judge what
    the tag will emit (the tag validates that itself at render). Every other
    ``{{ }}`` and value-producing tag (``{% url %}``, ``{% static %}``, custom
    tags) becomes a computed value; block tags become whitespace.
    """
    source = _TEMPLATE_COMMENT.sub(lambda m: _keep_lines(m, ""), source)
    source = _FX_ATTRS_TAG.sub(lambda m: _keep_lines(m, f' fx-action="{_VAR}" '), source)
    source = _EXPR.sub(lambda m: _keep_lines(m, _VAR), source)

    def tag(m):
        body = m.group(0)[2:-2].strip()
        return _keep_lines(m, " " if _BLOCK_TAGS.match(body) else _VAR)

    return _TAG.sub(tag, source)


def lint_template_source(source: str, file: str | None = None, ignore: Iterable[str] = ()) -> list[Finding]:
    """
    Findings for one template's source, without rendering it.

    Static, so page-level rules stay off: a template that extends a layout
    cannot know which ids the page will have. The test client lints rendered
    responses; this is for a person at the command line (``manage.py fixi_lint``).
    """
    return lint_html(strip_template_syntax(source), full_document=False, is_fx=None, ignore=ignore, file=file)
