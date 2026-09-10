"""
Django template tags for Fixi.js integration.
"""

from django import template
from django.core.exceptions import ImproperlyConfigured
from django.forms.utils import flatatt
from django.middleware.csrf import get_token
from django.templatetags.static import static
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()

# Fixi dispatches swaps case-sensitively: the adjacent positions go through a
# lowercase regex, and everything else is looked up as a property on the target
# element ("outerhtml" is not a property, so fixi throws and nothing swaps).
# Map the case-insensitive spelling to the one fixi actually recognizes.
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


@register.simple_tag
def fx_attrs(action=None, method="GET", target=None, swap="outerHTML", trigger="click", **kwargs):
    """
    Generate Fixi.js attributes for an element.

    Usage:
        {% fx_attrs action="/api/data" method="GET" target="#result" %}
        {% fx_attrs action="/submit" method="POST" swap="innerHTML" %}

    Args:
        action: URL for the Fixi action
        method: HTTP method (GET, POST, PUT, DELETE, PATCH)
        target: CSS selector for swap target
        swap: Swap strategy (outerHTML, innerHTML, beforebegin, afterend, ...)
        trigger: Event that triggers the action (click, change, submit, etc.)
        **kwargs: Additional attributes to add

    Returns:
        Safe string with Fixi attributes (values are HTML-escaped)

    Note:
        Fixi's own defaults are emitted-by-omission: GET method, ``click`` trigger,
        and ``outerHTML`` swap. Passing those values renders nothing for them, since
        Fixi already applies them when the attribute is absent. Pass a non-default
        value (e.g. ``swap="innerHTML"``) to emit it explicitly.
    """
    attrs = {}

    if action:
        attrs["fx-action"] = action

    if method and method.upper() != "GET":
        attrs["fx-method"] = method.upper()

    if target:
        attrs["fx-target"] = target

    # Fixi's default swap is outerHTML; only emit fx-swap when it differs.
    if swap:
        swap = normalize_swap(swap)
        if swap != "outerHTML":
            attrs["fx-swap"] = swap

    if trigger and trigger != "click":
        attrs["fx-trigger"] = trigger

    # Add any extra attributes
    for key, value in kwargs.items():
        # Convert underscores to hyphens for HTML attributes
        attrs[key.replace("_", "-")] = value

    # flatatt escapes values and prefixes a leading space; strip it for
    # consistent placement inside a tag.
    return mark_safe(flatatt(attrs).lstrip())


def normalize_swap(swap):
    """
    Return the spelling of ``swap`` that fixi.js recognizes.

    Raises TemplateSyntaxError for an unrecognized value rather than emitting it:
    fixi throws on an unknown swap, so the request succeeds, the server returns
    200, and nothing in the page changes.
    """
    canonical = SWAP_VALUES.get(str(swap).lower())
    if canonical is None:
        raise template.TemplateSyntaxError(
            f"{{% fx_attrs %}} got swap={swap!r}, which fixi.js does not recognize. "
            f"Valid values: {', '.join(sorted(set(SWAP_VALUES.values())))}. "
            "To target an arbitrary element property, write the fx-swap "
            "attribute directly instead of using this tag."
        )
    return canonical


@register.simple_tag(takes_context=True)
def fx_csrf_token(context):
    """
    Output CSRF token for Fixi requests.

    Usage:
        <form>
            {% fx_csrf_token %}
            ...
        </form>

    Reads ``csrf_token`` straight from the context the way Django's own
    ``{% csrf_token %}`` does. ``django.template.context_processors.csrf`` is a
    *builtin*, applied to every RequestContext, so this needs no context-processor
    configuration. Previously this returned an empty string whenever
    ``context["request"]`` was absent, so the form rendered looking correct and
    every POST came back 403.
    """
    token = context.get("csrf_token")
    if not token:
        # Fall back to the request, then refuse: a POST form with no token is
        # never correct, and a 500 naming the cause beats a silent 403.
        request = context.get("request")
        if request is None:
            raise ImproperlyConfigured(
                "{% fx_csrf_token %} found no CSRF token in the template context. "
                "Render this template with a RequestContext (django.shortcuts.render, "
                "TemplateResponse, or a generic view) so the token is available."
            )
        token = get_token(request)
    if token == "NOTPROVIDED":
        return ""
    return format_html('<input type="hidden" name="csrfmiddlewaretoken" value="{}">', token)


@register.simple_tag
def fixi_js():
    """
    Include the vendored Fixi.js core from this package's static files.

    Usage:
        {% fixi_js %}

    Requires ``django.contrib.staticfiles`` (or an equivalent static setup).
    This serves the copy of fixi.js shipped with dj-fixi, matching Fixi's
    "copy the file in" distribution model — no external CDN, version-pinned.
    """
    return format_html('<script src="{}"></script>', static("dj_fixi/fixi.js"))


@register.simple_tag
def fixi_events():
    """
    Include dj-fixi's optional FX-Trigger event bridge.

    Usage:
        {% fixi_js %}
        {% fixi_events %}

    Fixi core does not read response headers, so the ``FX-Trigger`` header set by
    FxResponseMixin is inert without this (or an equivalent moxi ``on-fx:after``
    handler). Load it *after* fixi.js.
    """
    return format_html('<script src="{}"></script>', static("dj_fixi/fixi-events.js"))


@register.simple_tag
def fixi_cdn(version="0.1.1"):
    """
    Include the Fixi Project bundle from a CDN.

    .. deprecated::
        Prefer ``{% fixi_js %}`` (vendored, offline, version-pinned). This tag is
        kept for convenience and points at the real ``the-fixi-project`` package
        (fixi + moxi + ssexi + paxi + rexi). The old ``unpkg.com/fixi@1.0.0`` URL
        was wrong — that npm name is an unrelated, abandoned package.

    Usage:
        {% fixi_cdn %}
        {% fixi_cdn version="0.1.1" %}
    """
    url = f"https://unpkg.com/the-fixi-project@{version}/dist/the-fixi-project.js"
    return format_html('<script src="{}"></script>', url)
