"""
Shortcut functions for Fixi.js integration with Django.
"""

from django.shortcuts import render


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
    is_fx = getattr(request, "is_fx", False)

    if is_fx or page_template is None:
        template = fragment_template
    else:
        template = page_template

    # Add Fixi context
    context.setdefault("is_fx", is_fx)
    context.setdefault("fx_info", getattr(request, "fx_info", {}))

    return render(request, template, context, **kwargs)


def render_fx_json(request, data, **kwargs):
    """
    Render JSON response (convenience wrapper).

    Args:
        request: HttpRequest object
        data: Data to serialize to JSON
        **kwargs: Additional arguments for JsonResponse

    Returns:
        JsonResponse
    """
    from django.http import JsonResponse

    return JsonResponse(data, **kwargs)
