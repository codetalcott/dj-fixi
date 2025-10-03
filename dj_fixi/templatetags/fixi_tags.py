"""
Django template tags for Fixi.js integration.
"""

from django import template
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
        Safe string with Fixi attributes
    """
    attrs = []

    if action:
        attrs.append(f'fx-action="{action}"')

    if method and method.upper() != "GET":
        attrs.append(f'fx-method="{method.upper()}"')

    if target:
        attrs.append(f'fx-target="{target}"')

    if swap and swap != "innerHTML":
        attrs.append(f'fx-swap="{swap}"')

    if trigger and trigger != "click":
        attrs.append(f'fx-trigger="{trigger}"')

    # Add any extra attributes
    for key, value in kwargs.items():
        # Convert underscores to hyphens for HTML attributes
        attr_name = key.replace("_", "-")
        attrs.append(f'{attr_name}="{value}"')

    return mark_safe(" ".join(attrs))


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
    from django.middleware.csrf import get_token

    request = context.get("request")
    if request:
        token = get_token(request)
        return mark_safe(f'<input type="hidden" name="csrfmiddlewaretoken" value="{token}">')
    return ""


@register.inclusion_tag("fixi/table.html")
def render_fx_table(renderer):
    """
    Render a CRUD table from a ModelTableRenderer instance.

    Usage:
        {% load fixi_tags %}
        {% render_fx_table user_table %}

    Args:
        renderer: ModelTableRenderer instance
    """
    return {"renderer": renderer}


@register.filter
def get_attr(obj, attr_name):
    """
    Get attribute value, handling None gracefully.

    Usage:
        {{ object|get_attr:"field_name" }}
    """
    return getattr(obj, attr_name, None)


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


@register.simple_tag
def fx_indicator(selector="#fx-indicator", class_name="fx-loading"):
    """
    Create a global Fixi loading indicator.

    Usage:
        {% fx_indicator %}
        {% fx_indicator selector="#my-spinner" class_name="loading" %}

    The element will have the specified class added during Fixi requests.
    """
    return mark_safe(
        f'<div id="{selector.lstrip("#")}" class="{class_name}" style="display: none;">'
        f"Loading...</div>"
    )
