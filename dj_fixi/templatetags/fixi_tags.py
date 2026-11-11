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

from dj_fixi import attrs as _attrs

register = template.Library()

#: Re-exported from :mod:`dj_fixi.attrs`, the one source of truth for what fixi.js
#: accepts. The tag, ``FxForm`` and ``dj_fixi.lint`` all read the same table.
SWAP_VALUES = _attrs.SWAP_VALUES


def _checked(validate, *values):
    """Run one of the ``dj_fixi.attrs`` validators, raising the template error."""
    try:
        return validate(*values)
    except ValueError as exc:
        raise template.TemplateSyntaxError(f"{{% fx_attrs %}} got {exc}") from None


@register.simple_tag
def fx_attrs(
    action=None,
    method="GET",
    target=None,
    swap="outerHTML",
    trigger="click",
    confirm=None,
    debounce=None,
    **kwargs,
):
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
        confirm: A question to ask first (``ext-fx-confirm``); Cancel sends nothing
        debounce: Milliseconds of quiet to wait for before sending
            (``ext-fx-debounce``), for search-as-you-type with ``trigger="input"``
        **kwargs: Additional attributes to add

    ``confirm`` and ``debounce`` are implemented by ``ext-fixi.js``, which
    ``{% fixi_scripts %}`` loads. Without it they do nothing; the lint and
    check ``dj_fixi.W303`` say so.

    Returns:
        Safe string with Fixi attributes (values are HTML-escaped)

    Note:
        Fixi's own defaults are emitted-by-omission: GET method, ``click`` trigger,
        and ``outerHTML`` swap. Passing those values renders nothing for them, since
        Fixi already applies them when the attribute is absent. Pass a non-default
        value (e.g. ``swap="innerHTML"``) to emit it explicitly.

        Every value is validated against what fixi.js will do with it, and the tag
        raises ``TemplateSyntaxError`` rather than emit something fixi ignores:
        an empty ``action`` (fixi fetches ``./undefined``), a ``trigger`` with
        spaces or commas (fixi waits for an event named exactly that), a
        ``method`` fetch() refuses, or a ``swap`` fixi does not recognize.
    """
    attrs = {}

    if action is not None:
        attrs["fx-action"] = _checked(_attrs.validate_action, action)

    if method:
        method = _checked(_attrs.validate_method, method)
        if method != "GET":
            attrs["fx-method"] = method

    if target:
        attrs["fx-target"] = target

    # Fixi's default swap is outerHTML; only emit fx-swap when it differs.
    if swap:
        swap = normalize_swap(swap)
        if swap != "outerHTML":
            attrs["fx-swap"] = swap

    if trigger:
        trigger = _checked(_attrs.validate_trigger, trigger)
        if trigger != "click":
            attrs["fx-trigger"] = trigger

    if confirm is not None:
        attrs["ext-fx-confirm"] = _checked(_attrs.validate_confirm, confirm)

    if debounce is not None:
        # trigger="click" is this tag's "not given"; the element's real default
        # depends on its tag, which only the lint can see.
        explicit = trigger if trigger and trigger != "click" else None
        attrs["ext-fx-debounce"] = _checked(_attrs.validate_debounce, debounce, explicit)

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
    return _checked(_attrs.normalize_swap, swap)


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
    FxResponseMixin is inert without this (or an equivalent moxi ``on-fx:swapped``
    handler). Load it *after* fixi.js. The same file logs, in the console, the
    mistakes fixi swallows: a target selector that matches nothing, a swap
    spelling fixi cannot perform, and a request that failed.
    """
    return format_html('<script src="{}"></script>', static("dj_fixi/fixi-events.js"))


def _csrf_token(context, tag: str) -> str | None:
    """The CSRF token for a script tag, or None when the view opted out of CSRF."""
    token = context.get("csrf_token")
    if not token:
        request = context.get("request")
        if request is None:
            raise ImproperlyConfigured(
                f"{{% {tag} %}} found no CSRF token in the template context. Render this "
                "template with a RequestContext (django.shortcuts.render, TemplateResponse, "
                "or a generic view) so the token is available."
            )
        token = get_token(request)
    return None if token == "NOTPROVIDED" else str(token)


@register.simple_tag(takes_context=True)
def fixi_ext(context):
    """
    Include dj-fixi's extension attributes: ``ext-fx-confirm``, ``ext-fx-debounce``,
    and Django's CSRF token on every unsafe same-origin request.

    Usage:
        {% fixi_js %}
        {% fixi_ext %}

    Prefer ``{% fixi_scripts %}``, which emits all three scripts in order.

    The token and the header name (``CSRF_HEADER_NAME``) are written onto the
    script element, not read from the cookie, so this works with
    ``CSRF_COOKIE_HTTPONLY`` and ``CSRF_USE_SESSIONS``. Putting the token in
    the page makes Django add ``Vary: Cookie``, as ``{% csrf_token %}`` does.
    """
    from django.conf import settings

    token = _csrf_token(context, "fixi_ext")
    src = static("dj_fixi/ext-fixi.js")
    if token is None:
        return format_html('<script src="{}"></script>', src)
    header = settings.CSRF_HEADER_NAME.removeprefix("HTTP_").replace("_", "-")
    return format_html(
        '<script src="{}" data-csrf-token="{}" data-csrf-header="{}"></script>', src, token, header
    )


@register.simple_tag(takes_context=True)
def fixi_scripts(context):
    """
    Everything dj-fixi ships for the browser, in the order it must load:
    fixi.js, the FX-Trigger event bridge, and the extension attributes.

    Usage:
        <head>{% fixi_scripts %}</head>

    One tag instead of three, so there is no order to get wrong and no script
    to forget. Requires ``django.contrib.staticfiles`` (or an equivalent).
    """
    return format_html("{}\n{}\n{}", fixi_js(), fixi_events(), fixi_ext(context))
