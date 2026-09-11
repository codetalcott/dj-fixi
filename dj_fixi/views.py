"""
Base views for Fixi.js integration with Django.

Adapted from django_hypermedia.views.base
"""

from django.core.exceptions import ImproperlyConfigured
from django.template.response import TemplateResponse
from django.views import View

from .request import is_fx as _is_fx
from .request import vary_on_fx


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

    FxView supplies no HTTP handlers of its own -- it is a base class. Compose it
    with a Django generic view (which brings ``get``/``post``), or subclass
    ``FxTemplateView``, which supplies ``get``. A subclass with neither answers
    every request with 405 Method Not Allowed.

    Example:
        class ProductListView(FxView, ListView):
            model = Product
            template_name = 'products/list.html'
            partial_template = 'products/list_partial.html'

    Note the base order: dj-fixi classes come *first*. Django's generic view
    mixins do not call ``super()`` in ``get_template_names``/``get_context_data``,
    so anything listed after them in the MRO never runs.
    """

    template_name = None
    partial_template = None

    # Mirrors TemplateResponseMixin so a standalone FxView honors these too.
    response_class = TemplateResponse
    content_type = None
    template_engine = None

    @property
    def is_fx(self):
        """Check if current request is a Fixi request."""
        return _is_fx(self.request)

    def get_template_names(self):
        """
        Get template names with automatic partial template selection.

        For a Fixi request with a ``partial_template``, that name and nothing
        else: a name the author wrote down must not fall through to the full
        page when it is missing, so a typo raises ``TemplateDoesNotExist`` at
        the first request instead of swapping a page into a div. Without one,
        Fixi requests get ``template_name`` like any other request; check W202
        says so at boot. Nothing is derived by convention (0.5 removed the
        ``_partial`` suffix and ``fragments/`` guesses).

        When FxView is mixed with a Django generic view that supplies its own
        ``get_template_names`` (e.g. the model-derived name from
        MultipleObjectTemplateResponseMixin), those names are appended as a final
        fallback. Explicit ``template_name`` takes precedence.
        """
        if self.is_fx and self.partial_template:
            return [self.partial_template]

        template_names = []
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

        Kept self-contained rather than delegating to Django's
        ``TemplateResponseMixin.render_to_response`` because the signatures differ
        (``context`` is required there), but it honors the same
        ``response_class``/``content_type``/``template_engine`` attributes.

        The response always varies on ``FX-Request``: this view returns a fragment
        or a full page for the same URL depending on that header, so a shared cache
        must not treat the two as interchangeable.
        """
        if context is None:
            context = self.get_context_data()

        response_kwargs.setdefault("content_type", self.content_type)

        response = self.response_class(
            request=self.request,
            template=self.get_template_names(),
            context=context,
            using=self.template_engine,
            **response_kwargs,
        )
        return vary_on_fx(response)


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
