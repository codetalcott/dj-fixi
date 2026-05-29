"""
Shortcut functions for Fixi.js integration with Django.
"""

from typing import Any, Dict, List

from django.http import HttpRequest, JsonResponse
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
    context.setdefault("fx_target", getattr(request, "fx_target", None))
    context.setdefault("fx_swap", getattr(request, "fx_swap", "innerHTML"))

    return render(request, template, context, **kwargs)


def render_table(
    request: HttpRequest,
    queryset,
    fields: List[str],
    template: str = None,
    editable_fields: List[str] = None,
    actions: List[str] = None,
    formatters: Dict[str, Any] = None,
    json_mode: bool = False,
    context: Dict[str, Any] = None,
    **kwargs,
):
    """
    Render a table for function-based views with automatic Fixi integration.

    Equivalent to FxTableMixin but for functional views.

    Args:
        request: HttpRequest object
        queryset: Django queryset to display
        fields: List of field names to display
        template: Template path (optional, defaults to JSON response for Fixi requests)
        editable_fields: List of fields that can be edited inline
        actions: List of actions ['edit', 'delete']
        formatters: Dict of field_name -> formatter_function
        json_mode: Force JSON response (for FixiPlug client-side rendering)
        context: Additional template context
        **kwargs: Additional arguments for render()

    Returns:
        HttpResponse or JsonResponse

    Usage:
        def product_list(request):
            products = Product.objects.all()

            return render_table(
                request,
                queryset=products,
                fields=['name', 'price', 'stock'],
                editable_fields=['name', 'stock'],
                actions=['edit', 'delete'],
                template='products/list.html',
                formatters={'price': lambda p: f'${p:.2f}'}
            )
    """
    from dj_fixi.tables import ModelTable

    if context is None:
        context = {}

    # Build table
    model = queryset.model
    table = ModelTable(
        queryset=queryset,
        fields=fields,
        editable_fields=editable_fields or [],
        actions=actions or ["edit", "delete"],
        formatters=formatters or {},
        view_name_prefix=model._meta.model_name,
    )

    # Check if client wants JSON (FixiPlug mode)
    wants_json = (
        json_mode
        or request.headers.get("FX-Data") == "json"
        or "application/json" in request.headers.get("Accept", "")
    )

    if wants_json:
        return JsonResponse(table.to_json(), safe=False)

    # Render HTML template
    context["table"] = table
    context.setdefault("is_fx", getattr(request, "is_fx", False))

    if template:
        return render(request, template, context, **kwargs)

    # No template provided - return just the table HTML
    from django.http import HttpResponse

    return HttpResponse(table.render())


def create_table(
    queryset,
    fields: List[str],
    editable_fields: List[str] = None,
    actions: List[str] = None,
    formatters: Dict[str, Any] = None,
):
    """
    Create a table object for use in function-based views.

    Provides fine-grained control over table rendering in templates.

    Args:
        queryset: Django queryset to display
        fields: List of field names to display
        editable_fields: List of fields that can be edited inline
        actions: List of actions ['edit', 'delete']
        formatters: Dict of field_name -> formatter_function

    Returns:
        ModelTable instance

    Usage:
        def product_list(request):
            products = Product.objects.all()

            table = create_table(
                queryset=products,
                fields=['name', 'price', 'stock'],
                editable_fields=['name', 'stock'],
                formatters={'price': lambda p: f'${p:.2f}'}
            )

            return render(request, 'products/list.html', {
                'table': table,
                'custom_data': 'example'
            })

        # In template:
        # {{ table }}  or  {{ table.render }}
    """
    from dj_fixi.tables import ModelTable

    model = queryset.model

    return ModelTable(
        queryset=queryset,
        fields=fields,
        editable_fields=editable_fields or [],
        actions=actions or ["edit", "delete"],
        formatters=formatters or {},
        view_name_prefix=model._meta.model_name,
    )
