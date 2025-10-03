"""
Django CBV mixins for Fixi.js integration.

Adapted from python-modules/crud/core_mixins.py
"""

import logging
from typing import Any, Dict, List, Optional, Type
from urllib.parse import urlencode

from django.contrib import messages
from django.core.cache import cache
from django.db import models
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone

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

    Adapted from HTMXResponseMixin - replaces HTMX-specific logic with Fixi.

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


class BulkActionMixin:
    """
    Enables bulk operations on multiple selected objects.

    Works with both Fixi and regular requests.

    Input Contract:
        - POST request with '_bulk_action' and '_selected[]' parameters
        - bulk_actions list defined on view

    Output Contract:
        - Executes bulk operation on selected queryset
        - Returns updated list view or JSON response
    """

    bulk_actions: List[str] = []
    bulk_action_permission_required: bool = True

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """Intercept POST requests for bulk actions."""
        if "_bulk_action" in request.POST:
            return self.handle_bulk_action(request)

        return super().post(request, *args, **kwargs)

    def handle_bulk_action(self, request: HttpRequest) -> HttpResponse:
        """Process bulk action on selected items."""
        action_name = request.POST.get("_bulk_action", "")
        selected_ids = request.POST.getlist("_selected[]") or request.POST.getlist("_selected")

        # Validate inputs
        if not action_name:
            return self.bulk_action_error(request, "No action specified")

        if not selected_ids:
            return self.bulk_action_error(request, "No items selected")

        if action_name not in self.bulk_actions:
            return self.bulk_action_error(request, f"Invalid action: {action_name}")

        # Check permissions
        if self.bulk_action_permission_required:
            permission = f"{self.model._meta.app_label}.{action_name}_{self.model._meta.model_name}"
            if not request.user.has_perm(permission):
                return self.bulk_action_error(request, "Permission denied")

        # Get queryset
        try:
            queryset = self.get_queryset().filter(pk__in=selected_ids)
        except (ValueError, TypeError):
            return self.bulk_action_error(request, "Invalid selection")

        if not queryset.exists():
            return self.bulk_action_error(request, "No valid items found")

        # Execute action
        handler = getattr(self, f"bulk_{action_name}", None)
        if not handler:
            return self.bulk_action_error(request, f"Handler not found: bulk_{action_name}")

        try:
            result = handler(request, queryset)

            # Return appropriate response for Fixi requests
            if getattr(request, "is_fx", False):
                context = self.get_context_data()
                response = self.render_to_response(context)
                # Trigger bulk action complete event
                if hasattr(self, "_trigger_fx_event"):
                    self._trigger_fx_event(
                        response,
                        "bulkActionComplete",
                        {"action": action_name, "count": queryset.count()},
                    )
                return response

            return result

        except Exception as e:
            logger.error(f"Bulk action failed: {e}", exc_info=True)
            return self.bulk_action_error(request, "Operation failed")

    def bulk_action_error(self, request: HttpRequest, message: str) -> HttpResponse:
        """Handle bulk action errors."""
        messages.error(request, message)

        if getattr(request, "is_fx", False):
            return JsonResponse({"error": message}, status=400)

        return self.get(request)

    def bulk_delete(self, request: HttpRequest, queryset: models.QuerySet) -> HttpResponse:
        """Default bulk delete implementation."""
        count = queryset.count()
        queryset.delete()
        messages.success(request, f"Deleted {count} {self.model._meta.verbose_name_plural}")
        return self.get(request)


class ReversibleDeleteMixin:
    """
    Implements soft delete with undo functionality.

    Adapted from original to work with Fixi custom events instead of HTMX.

    Input Contract:
        - Model has a datetime field for soft delete (default: 'deleted_at')
        - Cache backend is configured

    Output Contract:
        - Soft deletes objects instead of hard delete
        - Provides undo capability within timeout window
    """

    soft_delete_field: str = "deleted_at"
    undo_timeout: int = 10  # seconds
    enable_soft_delete: bool = True

    def delete(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """Override delete to implement soft delete with undo."""
        if not self.enable_soft_delete:
            return super().delete(request, *args, **kwargs)

        self.object = self.get_object()
        success_url = self.get_success_url()

        # Check if model has soft delete field
        if not hasattr(self.object, self.soft_delete_field):
            logger.warning(
                f"Model {self.model} missing soft delete field: {self.soft_delete_field}"
            )
            return super().delete(request, *args, **kwargs)

        # Perform soft delete
        setattr(self.object, self.soft_delete_field, timezone.now())
        self.object.save(update_fields=[self.soft_delete_field])

        # Cache for undo
        cache_key = f"undo_delete_{self.model._meta.label}_{self.object.pk}"
        cache.set(
            cache_key, {"pk": self.object.pk, "deleted_at": timezone.now().isoformat()}, timeout=self.undo_timeout
        )

        # Generate response
        if getattr(request, "is_fx", False):
            response = JsonResponse(
                {
                    "success": True,
                    "message": f"{self.object} deleted",
                    "undo_url": self.get_undo_url(self.object.pk),
                    "undo_timeout": self.undo_timeout,
                }
            )

            # Trigger undo toast event
            if hasattr(self, "_trigger_fx_event"):
                self._trigger_fx_event(
                    response,
                    "showUndoToast",
                    {
                        "id": str(self.object.pk),
                        "timeout": self.undo_timeout,
                        "undo_url": self.get_undo_url(self.object.pk),
                    },
                )

            return response

        messages.success(
            request,
            f'{self.object} deleted. <a href="{self.get_undo_url(self.object.pk)}">Undo</a>',
            extra_tags="safe",
        )

        return (
            HttpResponse(status=204)
            if getattr(request, "is_fx", False)
            else super().delete(request, *args, **kwargs)
        )

    def undo_delete(self, request: HttpRequest, pk: Any) -> HttpResponse:
        """Restore soft-deleted object."""
        cache_key = f"undo_delete_{self.model._meta.label}_{pk}"
        cached_data = cache.get(cache_key)

        if not cached_data:
            return JsonResponse({"error": "Undo period expired"}, status=400)

        try:
            obj = self.model.objects.filter(pk=pk).first()

            if obj and getattr(obj, self.soft_delete_field):
                setattr(obj, self.soft_delete_field, None)
                obj.save(update_fields=[self.soft_delete_field])

                # Clear cache
                cache.delete(cache_key)

                if getattr(request, "is_fx", False):
                    return JsonResponse({"success": True, "message": f"{obj} restored"})

                messages.success(request, f"{obj} restored")
                return self.get(request)

        except Exception as e:
            logger.error(f"Undo delete failed: {e}", exc_info=True)

        return JsonResponse({"error": "Unable to restore"}, status=400)

    def get_undo_url(self, pk: Any) -> str:
        """Generate URL for undo action."""
        from django.urls import reverse

        return reverse(
            f"{self.model._meta.app_label}:{self.model._meta.model_name}_undo", args=[pk]
        )


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
