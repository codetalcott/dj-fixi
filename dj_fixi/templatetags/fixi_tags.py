"""
Django template tags for Fixi.js integration.
"""

from django import template
from django.forms.utils import flatatt
from django.middleware.csrf import get_token
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def fx_attrs(action=None, method="GET", target=None, swap="innerHTML", trigger="click", **kwargs):
    """
    Generate Fixi.js attributes for an element.

    Usage:
        {% fx_attrs action="/api/data" method="GET" target="#result" %}
        {% fx_attrs action="/submit" method="POST" swap="outerHTML" %}

    Args:
        action: URL for the Fixi action
        method: HTTP method (GET, POST, PUT, DELETE, PATCH)
        target: CSS selector for swap target
        swap: Swap strategy (innerHTML, outerHTML, beforebegin, afterend)
        trigger: Event that triggers the action (click, change, submit, etc.)
        **kwargs: Additional attributes to add

    Returns:
        Safe string with Fixi attributes (values are HTML-escaped)
    """
    attrs = {}

    if action:
        attrs["fx-action"] = action

    if method and method.upper() != "GET":
        attrs["fx-method"] = method.upper()

    if target:
        attrs["fx-target"] = target

    if swap and swap != "innerHTML":
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


@register.simple_tag(takes_context=True)
def fx_csrf_token(context):
    """
    Output CSRF token for Fixi requests.

    Usage:
        <form>
            {% fx_csrf_token %}
            ...
        </form>
    """
    request = context.get("request")
    if request:
        token = get_token(request)
        return mark_safe(f'<input type="hidden" name="csrfmiddlewaretoken" value="{token}">')
    return ""


@register.simple_tag
def fixi_cdn(version="1.0.0"):
    """
    Include Fixi.js from CDN.

    Usage:
        {% fixi_cdn %}
        {% fixi_cdn version="1.0.1" %}

    Returns:
        Script tag for Fixi.js
    """
    # Note: Update this URL when fixi.js gets published to a CDN
    return mark_safe(f'<script src="https://unpkg.com/fixi@{version}/fixi.js"></script>')
