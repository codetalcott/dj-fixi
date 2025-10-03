"""
Base views for Fixi.js integration with Django.

Adapted from django_hypermedia.views.base
"""

from django.http import HttpResponse, JsonResponse
from django.template.response import TemplateResponse
from django.views import View


class FxView(View):
    """
    Base view for Fixi.js integration with automatic fragment/page detection.

    Automatically serves:
    - HTML fragments for Fixi requests (request.is_fx == True)
    - Full HTML pages for normal browser requests

    Attributes:
        template_name: Full page template
        partial_template: Fragment template for Fixi requests (optional)
        context_data: Additional context for templates

    Example:
        class ProductListView(FxView):
            template_name = 'products/list.html'
            partial_template = 'products/_list_partial.html'

            def get_context_data(self, **kwargs):
                context = super().get_context_data(**kwargs)
                context['products'] = Product.objects.all()
                return context
    """

    template_name = None
    partial_template = None
    json_fields = None  # Fields to include in JSON response

    def dispatch(self, request, *args, **kwargs):
        """Enhanced dispatch with Fixi detection."""
        # Detect if this is a Fixi request
        self.is_fx = getattr(request, "is_fx", False)
        self.fx_info = getattr(request, "fx_info", {})

        # Call parent dispatch
        return super().dispatch(request, *args, **kwargs)

    def get_template_names(self):
        """
        Get template names with automatic partial template selection.

        Returns partial_template for Fixi requests, falls back to template_name.
        Also tries template_name with _partial suffix if partial_template not set.
        """
        template_names = []

        if self.is_fx and self.partial_template:
            template_names.append(self.partial_template)

        # Try _partial suffix variation
        if self.is_fx and self.template_name:
            if self.template_name.endswith(".html"):
                partial_variant = self.template_name.replace(".html", "_partial.html")
                template_names.append(partial_variant)

        # Always include base template as fallback
        if self.template_name:
            template_names.append(self.template_name)

        return template_names or [self.template_name]

    def get_context_data(self, **kwargs):
        """
        Get template context with Fixi-related metadata.

        Adds:
            - is_fx: Boolean indicating if this is a Fixi request
            - fx_info: Dict with target, swap, trigger info
        """
        context = kwargs.copy()
        context["is_fx"] = self.is_fx
        context["fx_info"] = self.fx_info
        return context

    def render_to_response(self, context=None, **response_kwargs):
        """Render template with context."""
        if context is None:
            context = self.get_context_data()

        template_names = self.get_template_names()

        return TemplateResponse(
            request=self.request, template=template_names, context=context, **response_kwargs
        )

    def render_json(self, context=None, **response_kwargs):
        """
        Render JSON response.

        Uses json_fields to filter context if specified.
        """
        if context is None:
            context = self.get_context_data()

        # Filter to specified fields or exclude Django internals
        if self.json_fields:
            data = {field: context.get(field) for field in self.json_fields}
        else:
            data = {
                k: v
                for k, v in context.items()
                if not k.startswith("_") and k not in ["request", "user", "perms", "view"]
            }

        return JsonResponse(data, **response_kwargs)


class FxTemplateView(FxView):
    """
    Simple template rendering view with Fixi support.

    Like Django's TemplateView but with automatic fragment serving.

    Example:
        path('about/', FxTemplateView.as_view(
            template_name='about.html',
            partial_template='about_partial.html'
        ))
    """

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)
