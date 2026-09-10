"""
Shortcut functions for Fixi.js integration with Django.
"""

from django.shortcuts import render

from .request import is_fx as _is_fx
from .request import vary_on_fx


def render_fx(request, fragment_template, page_template=None, context=None, **kwargs):
    """
    Render appropriate template based on whether this is a Fixi request.

    Automatically selects:
    - fragment_template for Fixi requests
    - page_template for normal browser requests

    If page_template is not provided, always uses fragment_template.

    Args:
        request: HttpRequest object
        fragment_template: Template for Fixi requests
        page_template: Template for full page requests (optional)
        context: Template context dict
        **kwargs: Additional arguments passed to render()

    Returns:
        HttpResponse

    Usage:
        # With separate templates
        return render_fx(
            request,
            'products/list_fragment.html',
            'products/list.html',
            {'products': products}
        )

        # Single template (works for both)
        return render_fx(
            request,
            'products/list.html',
            context={'products': products}
        )
    """
    if context is None:
        context = {}

    # Determine which template to use
    is_fx = _is_fx(request)

    if is_fx or page_template is None:
        template = fragment_template
    else:
        template = page_template

    # Add Fixi context
    context.setdefault("is_fx", is_fx)

    return vary_on_fx(render(request, template, context, **kwargs))
