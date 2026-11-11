"""
The Fixi attribute vocabulary, and the render-time validation every emitter shares.

One source of truth: ``{% fx_attrs %}``, ``FxForm`` and ``dj_fixi.lint`` all
import from here, so none of them can disagree about what fixi.js accepts.
Each rule names the line of the vendored ``dj_fixi/static/dj_fixi/fixi.js``
it comes from, and ``tests/test_lint_vocabulary.py`` pins those lines.

Every function returns the value fixi.js will act on, or raises ``ValueError``
with a message that says what fixi would have done with the bad value. The
template tag turns that into ``TemplateSyntaxError``; ``FxForm`` lets it
propagate.
"""

from __future__ import annotations

import re

__all__ = [
    "FX_ATTRIBUTES",
    "FX_CONTROL_ATTRIBUTES",
    "EXT_ATTRIBUTES",
    "UNDEBOUNCEABLE_TRIGGERS",
    "SWAP_VALUES",
    "FORBIDDEN_METHODS",
    "normalize_swap",
    "validate_trigger",
    "validate_method",
    "validate_action",
    "validate_confirm",
    "validate_debounce",
]

#: Every attribute fixi.js reads (fixi.js:7 ``fx-ignore``; :19-22 action, method,
#: target, swap; :74 trigger). Anything else is the project's own.
FX_ATTRIBUTES = frozenset(
    {"fx-action", "fx-method", "fx-target", "fx-swap", "fx-trigger", "fx-ignore"}
)

#: The attributes that only mean something on an element fixi initialises,
#: which is any element matching ``[fx-action]`` (fixi.js:81, :83).
FX_CONTROL_ATTRIBUTES = frozenset({"fx-method", "fx-target", "fx-swap", "fx-trigger"})

#: The extension attributes ``ext-fixi.js`` implements, in fixi's own ``ext-fx-``
#: convention. Closed on purpose: see "Extension attributes" in CLAUDE.md for
#: what may join this set. ``tests/test_ext_fixi_js.py`` pins it against the file.
EXT_ATTRIBUTES = frozenset({"ext-fx-confirm", "ext-fx-debounce"})

#: Debouncing delays the call into fixi, and fixi is what calls
#: ``preventDefault()`` (fixi.js:34). By then a click has already followed its
#: link and a submit has already navigated.
UNDEBOUNCEABLE_TRIGGERS = frozenset({"click", "submit"})

#: Fixi dispatches swaps case-sensitively (fixi.js:61-65): the adjacent positions
#: go through a lowercase regex, and everything else is looked up as a property on
#: the target element ("outerhtml" is not a property, so fixi throws and nothing
#: swaps). Map the case-insensitive spelling to the one fixi actually recognizes.
SWAP_VALUES = {
    "innerhtml": "innerHTML",
    "outerhtml": "outerHTML",
    "textcontent": "textContent",
    "innertext": "innerText",
    "beforebegin": "beforebegin",
    "afterbegin": "afterbegin",
    "beforeend": "beforeend",
    "afterend": "afterend",
    "none": "none",
    "morph": "morph",  # provided by paxi.js
}

#: ``fetch()`` refuses these with a TypeError, which fixi.js:51-53 swallows into an
#: ``fx:error`` event nobody listens to by default. Everything else (HEAD, OPTIONS,
#: QUERY, PROPFIND, ...) fixi uppercases and forwards (fixi.js:20).
FORBIDDEN_METHODS = frozenset({"CONNECT", "TRACE", "TRACK"})

_TOKEN = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")


def normalize_swap(swap) -> str:
    """The spelling of ``swap`` that fixi.js recognizes, or ``ValueError``."""
    canonical = SWAP_VALUES.get(str(swap).lower())
    if canonical is None:
        raise ValueError(
            f"swap={swap!r} is not something fixi.js recognizes. Valid values: "
            f"{', '.join(sorted(set(SWAP_VALUES.values())))}. fixi throws on an unknown "
            "swap after the request succeeds, so the server returns 200 and nothing in "
            "the page changes. To assign an arbitrary element property, write the "
            "fx-swap attribute directly."
        )
    return canonical


def validate_trigger(trigger) -> str:
    """
    ``trigger`` as fixi.js will use it: one event name, verbatim.

    fixi.js:74-75 hands the attribute value to ``addEventListener`` unchanged,
    so htmx modifier syntax (``keyup delay:200ms``, ``click, change``) registers
    a listener for an event with that literal name, which never fires. Colons
    are fine: ``fx:swapped`` is a real event name.
    """
    value = str(trigger)
    if not value or re.search(r"\s|,", value):
        raise ValueError(
            f"trigger={trigger!r} is not one event name. fixi.js passes fx-trigger to "
            "addEventListener verbatim, so a value with spaces or commas waits for an "
            "event that never fires. Use a single event such as 'change' or 'submit'."
        )
    return value


def validate_method(method) -> str:
    """``method`` uppercased the way fixi.js:20 does, or ``ValueError``."""
    value = str(method).upper()
    if not _TOKEN.match(value) or value in FORBIDDEN_METHODS:
        raise ValueError(
            f"method={method!r} cannot be sent: fetch() refuses it with a TypeError that "
            "fixi swallows, so the click does nothing and nothing is logged."
        )
    return value


def validate_action(action) -> str:
    """
    ``action`` as given, or ``ValueError`` for the empty string.

    fixi.js:5 reads attributes with ``||``, so ``fx-action=""`` becomes
    ``fetch(undefined)``: a request to ``./undefined`` relative to the page. The
    usual cause is a misspelled template variable rendering as an empty string.
    """
    value = str(action)
    if not value.strip():
        raise ValueError(
            'action is empty. fixi.js treats fx-action="" as undefined and fetches '
            "'./undefined'. A misspelled template variable renders as '' silently; "
            "check the name."
        )
    return value


def validate_confirm(message) -> str:
    """``message`` as given, or ``ValueError`` when there is nothing to ask."""
    value = str(message)
    if not value.strip():
        raise ValueError(
            "confirm is empty. ext-fixi.js only asks when ext-fx-confirm has a value, so an "
            "empty one sends the request without asking. A misspelled template variable "
            "renders as '' silently; check the name."
        )
    return value


def validate_debounce(wait, trigger=None) -> str:
    """
    ``wait`` as whole milliseconds, or ``ValueError``.

    One number and nothing else: no units, no modifiers. ``trigger`` is the
    event the element listens for, when the caller knows it; a debounced click
    or submit is refused because the browser's default action is not delayed.
    """
    try:
        value = int(str(wait).strip())
    except ValueError:
        value = 0
    if value <= 0 or str(wait).strip() != str(value):
        raise ValueError(
            f"debounce={wait!r} is not a whole number of milliseconds. ext-fixi.js reads it "
            "with parseInt and ignores the attribute when that is not positive, so the "
            "control fires on every event. Write a number such as 250, with no unit."
        )
    if trigger is not None and str(trigger).lower() in UNDEBOUNCEABLE_TRIGGERS:
        raise ValueError(
            f"debounce cannot be combined with trigger={trigger!r}: fixi cancels the browser's "
            "default action only when it runs, and a debounced handler runs later, so the "
            "link is followed or the form submitted first. Debounce an input event instead."
        )
    return str(value)
