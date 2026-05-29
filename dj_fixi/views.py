"""
Base views for Fixi.js integration with Django.

Adapted from django_hypermedia.views.base
"""

from django.core.exceptions import ImproperlyConfigured
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

    @property
    def is_fx(self):
        """Check if current request is a Fixi request."""
        return getattr(self.request, "is_fx", False)

    def get_template_names(self):
        """
        Get template names with automatic partial template selection.

        Returns partial_template for Fixi requests, falls back to template_name.
        Also tries template_name with a ``_partial`` suffix when partial_template
        is not set.

        When FxView is mixed with a Django generic view that supplies its own
        ``get_template_names`` (e.g. the model-derived name from
        MultipleObjectTemplateResponseMixin), those names are appended as a final
        fallback. Explicit ``partial_template``/``template_name`` always take
        precedence.
        """
        template_names = []

        if self.is_fx and self.partial_template:
            template_names.append(self.partial_template)

        # Try _partial suffix variation for Fixi requests
        if self.is_fx and self.template_name and self.template_name.endswith(".html"):
            template_names.append(self.template_name.replace(".html", "_partial.html"))

        # Always include base template as fallback
        if self.template_name:
            template_names.append(self.template_name)

        # Cooperate with generic views (model-derived template names, etc.)
        parent = getattr(super(), "get_template_names", None)
        if callable(parent):
            try:
                for name in parent():
                    if name not in template_names:
                        template_names.append(name)
            except ImproperlyConfigured:
                # Generic mixin couldn't derive a name; rely on ours instead.
                pass

        if not template_names:
            raise ImproperlyConfigured(
                f"{type(self).__name__} requires a 'template_name' or "
                "'partial_template' attribute, or an implementation of "
                "'get_template_names()'."
            )

        return template_names

    def get_context_data(self, **kwargs):
        """
        Get template context with Fixi-related metadata.

        Cooperates with the MRO: when FxView is mixed with a Django generic view
        (ListView/DetailView/FormView/TemplateView), the next class in the MRO
        provides ``get_context_data`` (e.g. MultipleObjectMixin), so we delegate
        to it to preserve ``object_list``, ``page_obj``, ``paginator``,
        ``is_paginated`` and the configured context_object_name. A bare
        FxView/FxTemplateView extends ``django.views.View`` which has no
        ``get_context_data``, so we fall back to building context from kwargs.

        Adds:
            - is_fx: Boolean indicating if this is a Fixi request

        Note: Fixi does not send target/swap in request headers (they are
        client-side concerns), so no fx_target/fx_swap is exposed here.
        """
        parent = getattr(super(), "get_context_data", None)
        if callable(parent):
            context = parent(**kwargs)
        else:
            context = {**kwargs}
            context.setdefault("view", self)
        context["is_fx"] = self.is_fx
        return context

    def render_to_response(self, context=None, **response_kwargs):
        """
        Render template with context.

        Kept intentionally self-contained rather than delegating to Django's
        ``TemplateResponseMixin.render_to_response``: the signatures differ
        (``context`` is required there) and delegating would re-run
        ``get_template_names`` and ignore ``response_class``/``content_type``/
        ``template_engine``. As a result those generic-view attributes are not
        honored here; pass ``response_kwargs`` if you need to override them.
        """
        if context is None:
            context = self.get_context_data()

        template_names = self.get_template_names()

        return TemplateResponse(
            request=self.request, template=template_names, context=context, **response_kwargs
        )


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
