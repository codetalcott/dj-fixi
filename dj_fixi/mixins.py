"""
Django CBV mixins for Fixi.js integration.

Simplified to include only essential, non-opinionated mixins.
"""

import json
import logging
from typing import Any
from urllib.parse import urlencode

from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.http import HttpResponse

logger = logging.getLogger(__name__)


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

    filterset_class: type | None = None
    filterset_fields: list[str] | None = None
    preserved_params: list[str] = ["sort", "page", "q"]

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
            # Validate the sort field against the queryset's model, which is
            # always available even when the view sets ``queryset`` not ``model``.
            field_name = sort_param.lstrip("-")
            try:
                queryset.model._meta.get_field(field_name)
                queryset = queryset.order_by(sort_param)
            except FieldDoesNotExist:
                logger.warning(f"Invalid sort field: {field_name}")

        return queryset

    def get_filterset(self, queryset: models.QuerySet) -> Any | None:
        """Initialize filterset with current queryset and request."""
        if self.filterset_class:
            return self.filterset_class(self.request.GET, queryset=queryset, request=self.request)
        return None

    def get_context_data(self, **kwargs) -> dict[str, Any]:
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

    def get_template_names(self) -> list[str]:
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
        """
        Handle successful form submission for Fixi requests.

        Delegates the actual mutation to ``super().form_valid()`` so that
        create/update (``ModelFormMixin``) save the instance and delete
        (``DeletionMixin``) deletes it — each computing ``success_url``. For
        non-Fixi requests Django's redirect is returned unchanged.

        For Fixi requests the redirect is replaced:
          - create/update (object still has a pk) -> render the fragment and
            attach the success FX-Trigger event with the object id;
          - delete or no renderable object -> return ``204 No Content`` with the
            success FX-Trigger event (the deleted object's id is preserved so the
            client can remove its row).
        """
        # Capture the pk before delegating: DeletionMixin clears it on delete.
        existing = getattr(self, "object", None)
        pk_before = getattr(existing, "pk", None)

        response = super().form_valid(form)

        if not getattr(self.request, "is_fx", False):
            return response

        detail = {"message": self.get_success_message()}
        obj = getattr(self, "object", None)
        obj_pk = getattr(obj, "pk", None)

        if obj_pk is not None:
            # Create/update: hand back the rendered fragment for swapping in.
            detail["object_id"] = str(obj_pk)
            fx_response = self.render_to_response(self.get_context_data(form=form))
        else:
            # Delete (or no object to render): nothing to swap.
            if pk_before is not None:
                detail["object_id"] = str(pk_before)
            fx_response = HttpResponse(status=204)

        self._trigger_fx_event(fx_response, self.fx_success_event, detail)
        return fx_response

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

    def _trigger_fx_event(
        self, response: HttpResponse, event_name: str, detail: dict | None = None
    ):
        """
        Trigger a custom Fixi event on the client.

        Uses FX-Trigger header similar to HTMX's HX-Trigger.
        Event will be dispatched as 'fx:{event_name}' on the client.
        """
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

    select_related_fields: list[str] = []
    prefetch_related_fields: list[str] = []

    def get_queryset(self) -> models.QuerySet:
        """Apply query optimizations."""
        queryset = super().get_queryset()

        if self.select_related_fields:
            queryset = queryset.select_related(*self.select_related_fields)

        if self.prefetch_related_fields:
            queryset = queryset.prefetch_related(*self.prefetch_related_fields)

        return queryset
