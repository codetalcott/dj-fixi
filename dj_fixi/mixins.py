"""
Django CBV mixins for Fixi.js integration.

Simplified to include only essential, non-opinionated mixins.
"""

import logging
from typing import Any, Dict, List, Optional, Type
from urllib.parse import urlencode

from django.db import models
from django.http import HttpResponse, JsonResponse
from django.utils import timezone

logger = logging.getLogger(__name__)


class MCPResponseMixin:
    """
    Mixin to ensure MCP-compatible JSON responses.

    All responses follow standardized format:
    {
        "success": bool,
        "data": {...},
        "meta": {...}
    }
    """

    def get_mcp_meta(self) -> Dict[str, Any]:
        """Override to add custom metadata."""
        meta = {
            'timestamp': timezone.now().isoformat()
        }

        # Add view and model info if available
        if hasattr(self, '__class__'):
            meta['view'] = self.__class__.__name__
        if hasattr(self, 'model') and self.model:
            meta['model'] = self.model.__name__

        return meta

    def mcp_success_response(
        self,
        data: Any,
        status: int = 200,
        extra_meta: Dict[str, Any] = None
    ) -> JsonResponse:
        """Create standardized success response."""
        meta = self.get_mcp_meta()
        if extra_meta:
            meta.update(extra_meta)

        return JsonResponse({
            'success': True,
            'data': data,
            'meta': meta
        }, status=status)

    def mcp_error_response(
        self,
        error: str,
        status: int = 400,
        error_code: str = None
    ) -> JsonResponse:
        """Create standardized error response."""
        return JsonResponse({
            'success': False,
            'error': error,
            'error_code': error_code,
            'meta': self.get_mcp_meta()
        }, status=status)


class ContextPersistenceMixin:
    """
    Preserves user context (filters, sorting, pagination) across navigation.

    Works with both Fixi and regular requests.

    Input Contract:
        - request.GET contains filter params, 'sort', and 'page'
        - filterset_class or filterset_fields must be defined on the view

    Output Contract:
        - Adds 'query_string' and 'preserved_params' to template context
        - Modifies queryset based on URL parameters
    """

    filterset_class: Optional[Type] = None
    filterset_fields: Optional[List[str]] = None
    preserved_params: List[str] = ["sort", "page", "q"]

    def get_queryset(self) -> models.QuerySet:
        """Apply filtering and sorting from URL parameters."""
        queryset = super().get_queryset()

        # Apply filtering
        if self.filterset_class or self.filterset_fields:
            filterset = self.get_filterset(queryset)
            if filterset is not None:
                queryset = filterset.qs
                self.filterset = filterset

        # Apply sorting with validation
        sort_param = self.request.GET.get("sort", "")
        if sort_param:
            # Validate sort field exists on model
            field_name = sort_param.lstrip("-")
            try:
                self.model._meta.get_field(field_name)
                queryset = queryset.order_by(sort_param)
            except models.FieldDoesNotExist:
                logger.warning(f"Invalid sort field: {field_name}")

        return queryset

    def get_filterset(self, queryset: models.QuerySet) -> Optional[Any]:
        """Initialize filterset with current queryset and request."""
        if self.filterset_class:
            return self.filterset_class(
                self.request.GET, queryset=queryset, request=self.request
            )
        return None

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        """Add preserved parameters to context."""
        context = super().get_context_data(**kwargs)

        # Build query string for current state
        params = {}
        for key in set(self.preserved_params + list(self.request.GET.keys())):
            value = self.request.GET.get(key)
            if value:
                params[key] = value

        context["query_string"] = urlencode(params)
        context["preserved_params"] = params
        context["current_sort"] = self.request.GET.get("sort", "")

        # Add filterset to context if available
        if hasattr(self, "filterset"):
            context["filter"] = self.filterset

        return context


class FxResponseMixin:
    """
    Handles Fixi requests with appropriate partial responses.

    Input Contract:
        - request.is_fx attribute available (via FxMiddleware)
        - Templates support fragment rendering

    Output Contract:
        - Returns template fragments for Fixi requests
        - Triggers custom Fixi events for client-side handling
    """

    fx_template_suffix: str = "_partial"
    fx_success_event: str = "formSuccess"
    fx_error_event: str = "formError"

    def get_template_names(self) -> List[str]:
        """Return fragment templates for Fixi requests."""
        if getattr(self.request, "is_fx", False):
            original_templates = super().get_template_names()
            fx_templates = []

            for template in original_templates:
                # Insert suffix before file extension
                name_parts = template.rsplit(".", 1)
                if len(name_parts) == 2:
                    fx_template = f"{name_parts[0]}{self.fx_template_suffix}.{name_parts[1]}"
                    fx_templates.append(fx_template)

                # Also try a fragments subdirectory
                parts = template.rsplit("/", 1)
                if len(parts) == 2:
                    fragment_template = f"{parts[0]}/fragments/{parts[1]}"
                    fx_templates.append(fragment_template)

            return fx_templates + original_templates

        return super().get_template_names()

    def form_valid(self, form) -> HttpResponse:
        """Handle successful form submission for Fixi requests."""
        if getattr(self.request, "is_fx", False):
            self.object = form.save()

            # Prepare success response
            context = self.get_context_data(form=form, object=self.object)
            response = self.render_to_response(context)

            # Trigger custom Fixi event (fx:formSuccess)
            self._trigger_fx_event(
                response,
                self.fx_success_event,
                {"message": self.get_success_message(), "object_id": str(self.object.pk)},
            )

            return response

        return super().form_valid(form)

    def form_invalid(self, form) -> HttpResponse:
        """Handle form validation errors for Fixi requests."""
        if getattr(self.request, "is_fx", False):
            context = self.get_context_data(form=form)
            response = self.render_to_response(context)
            response.status_code = 422

            # Trigger error event
            self._trigger_fx_event(
                response, self.fx_error_event, {"errors": form.errors.get_json_data()}
            )

            return response

        return super().form_invalid(form)

    def get_success_message(self) -> str:
        """Generate success message for the operation."""
        return f"{self.model._meta.verbose_name.title()} saved successfully"

    def _trigger_fx_event(self, response: HttpResponse, event_name: str, detail: dict = None):
        """
        Trigger a custom Fixi event on the client.

        Uses FX-Trigger header similar to HTMX's HX-Trigger.
        Event will be dispatched as 'fx:{event_name}' on the client.
        """
        import json

        if detail:
            # Send event with detail data
            response["FX-Trigger"] = json.dumps({event_name: detail})
        else:
            # Simple event trigger
            response["FX-Trigger"] = event_name


class OptimizedQueryMixin:
    """
    Optimizes database queries with select_related and prefetch_related.

    No library-specific code - works with any Django view.

    Input Contract:
        - select_related_fields: List of foreign key fields
        - prefetch_related_fields: List of many-to-many or reverse FK fields

    Output Contract:
        - Returns optimized queryset with reduced database queries
    """

    select_related_fields: List[str] = []
    prefetch_related_fields: List[str] = []

    def get_queryset(self) -> models.QuerySet:
        """Apply query optimizations."""
        queryset = super().get_queryset()

        if self.select_related_fields:
            queryset = queryset.select_related(*self.select_related_fields)

        if self.prefetch_related_fields:
            queryset = queryset.prefetch_related(*self.prefetch_related_fields)

        return queryset


class FxTableMixin:
    """
    Adds automatic table rendering with Fixi.js integration to ListView.

    Provides backend-driven inline editing without manual template work.

    Input Contract:
        - table_fields: List of model fields to display
        - editable_fields: List of fields that can be edited inline (optional)
        - table_actions: List of actions ['edit', 'delete'] (optional)
        - table_formatters: Dict of field_name -> formatter_function (optional)

    Output Contract:
        - Adds 'table' to context with auto-generated Fixi attributes
        - Table supports inline editing, sorting, and CRUD actions

    Example:
        class ProductListView(FxTableMixin, ListView):
            model = Product
            table_fields = ['name', 'price', 'stock', 'is_active']
            editable_fields = ['name', 'stock']
            table_actions = ['edit', 'delete']
            table_formatters = {'price': lambda p: f'${p:.2f}'}
    """

    table_fields: List[str] = []
    editable_fields: List[str] = []
    table_actions: List[str] = ["edit", "delete"]
    table_formatters: Dict[str, Any] = {}
    table_view_prefix: Optional[str] = None

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        """Add auto-generated table to context."""
        context = super().get_context_data(**kwargs)

        # Only add table if fields are configured
        if self.table_fields:
            from dj_fixi.tables import ModelTable

            context["table"] = ModelTable(
                queryset=context["object_list"],
                fields=self.table_fields,
                editable_fields=self.editable_fields,
                actions=self.table_actions,
                formatters=self.table_formatters,
                view_name_prefix=self.table_view_prefix or self.model._meta.model_name,
            )

        return context
