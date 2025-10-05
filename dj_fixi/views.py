"""
Base views for Fixi.js integration with Django.

Adapted from django_hypermedia.views.base
"""

from django.http import HttpResponse, JsonResponse
from django.template.response import TemplateResponse
from django.views import View
from django.shortcuts import get_object_or_404
from django.core.exceptions import FieldDoesNotExist, ValidationError
from typing import Any, Dict, List, Tuple
import json

from .mixins import MCPResponseMixin


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

    @property
    def is_fx(self):
        """Check if current request is a Fixi request."""
        return getattr(self.request, "is_fx", False)

    def dispatch(self, request, *args, **kwargs):
        """Enhanced dispatch with Fixi detection."""
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
            - fx_target: Target selector
            - fx_swap: Swap strategy
        """
        context = kwargs.copy()
        context["is_fx"] = self.is_fx
        context["fx_target"] = getattr(self.request, "fx_target", None)
        context["fx_swap"] = getattr(self.request, "fx_swap", "innerHTML")
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


class FxCRUDView(MCPResponseMixin, View):
    """
    Unified CRUD view optimized for FixiPlug table plugin.

    Handles all table operations in a single view:
    - GET: List/retrieve (with sorting, filtering, pagination)
    - POST: Create new record
    - PATCH: Update single field (inline editing) or full record
    - DELETE: Delete record(s)

    Automatically returns JSON for FixiPlug, HTML for browsers.

    Example:
        class ProductCRUDView(FxCRUDView):
            model = Product
            fields = ['name', 'price', 'stock', 'is_active']
            editable_fields = ['name', 'stock']
            template_name = 'products/list.html'
            paginate_by = 20

        # urls.py
        path('products/', ProductCRUDView.as_view(), name='product_crud'),
        path('products/<int:pk>/', ProductCRUDView.as_view(), name='product_detail'),
    """

    model = None
    fields = []
    editable_fields = []  # Fields that can be edited inline
    read_only_fields = []  # Fields for display only
    searchable_fields = []  # Fields that can be searched
    template_name = None
    paginate_by = 10
    ordering = None

    # Validation rules
    validation_rules: Dict[str, Dict[str, Any]] = {}

    # Change tracking
    enable_audit_log: bool = False

    def get_queryset(self):
        """Get base queryset."""
        if self.model is None:
            raise ValueError("model must be specified")
        return self.model.objects.all()

    def validate_field(self, field: str, value: Any) -> Tuple[bool, str]:
        """
        Validate individual field value.

        Returns:
            (is_valid, error_message)
        """
        if field not in self.validation_rules:
            return True, ""

        rules = self.validation_rules[field]

        # Required check
        if rules.get('required') and not value:
            return False, f"{field} is required"

        # Type check
        expected_type = rules.get('type')
        if expected_type and value is not None:
            if not isinstance(value, expected_type):
                type_name = expected_type.__name__ if hasattr(expected_type, '__name__') else str(expected_type)
                return False, f"{field} must be of type {type_name}"

        # Custom validator
        validator = rules.get('validator')
        if validator and value is not None:
            try:
                validator(value)
            except (ValueError, ValidationError) as e:
                return False, str(e)

        return True, ""

    def validate_data(self, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate all provided data.

        Returns:
            (is_valid, error_messages)
        """
        errors = []

        for field, value in data.items():
            if field == 'id':
                continue  # Skip id field

            if field not in self.editable_fields:
                errors.append(f"{field} is not editable")
                continue

            is_valid, error = self.validate_field(field, value)
            if not is_valid:
                errors.append(error)

        return len(errors) == 0, errors

    def log_change(
        self,
        obj: Any,
        old_values: Dict,
        new_values: Dict,
        user: Any
    ):
        """
        Log changes for audit trail.

        Override this method to implement custom audit logging.
        """
        pass

    def get_filtered_queryset(self, request):
        """Apply filters, search, and sorting."""
        queryset = self.get_queryset()

        # Search
        search = request.GET.get('q')
        if search and self.searchable_fields:
            from django.db.models import Q
            q_objects = Q()
            for field in self.searchable_fields:
                q_objects |= Q(**{f"{field}__icontains": search})
            queryset = queryset.filter(q_objects)

        # Sorting
        sort = request.GET.get('sort')
        direction = request.GET.get('dir', 'asc')
        if sort:
            # Validate field exists
            try:
                self.model._meta.get_field(sort)
                order = sort if direction == 'asc' else f'-{sort}'
                queryset = queryset.order_by(order)
            except FieldDoesNotExist:
                pass  # Ignore invalid sort field
        elif self.ordering:
            queryset = queryset.order_by(self.ordering)

        return queryset

    def get_paginated_data(self, queryset, request):
        """Apply pagination and return data + metadata."""
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', self.paginate_by))

        total = queryset.count()
        start = (page - 1) * limit
        end = start + limit

        items = list(queryset[start:end])

        return {
            'items': items,
            'pagination': {
                'page': page,
                'limit': limit,
                'total': total,
                'totalPages': (total + limit - 1) // limit if total > 0 else 0,
            }
        }

    def serialize_object(self, obj):
        """Serialize model instance to dict."""
        data = {'id': obj.pk}
        for field in self.fields:
            value = getattr(obj, field)
            # Handle common types
            if hasattr(value, 'isoformat'):  # datetime
                data[field] = value.isoformat()
            else:
                data[field] = value
        return data

    def get(self, request, pk=None, *args, **kwargs):
        """
        Handle GET requests.

        - With pk: Return single object
        - Without pk: Return list (with filtering, sorting, pagination)
        """
        # Single object retrieval
        if pk:
            obj = get_object_or_404(self.model, pk=pk)

            if self.wants_json(request):
                return JsonResponse(self.serialize_object(obj))

            # Return HTML row for table
            from dj_fixi.tables import ModelTable
            table = ModelTable(
                queryset=self.model.objects.filter(pk=pk),
                fields=self.fields,
                editable_fields=self.editable_fields,
            )
            return HttpResponse(table.render_row(obj))

        # List view
        queryset = self.get_filtered_queryset(request)

        # Check if wants JSON (FixiPlug)
        if self.wants_json(request):
            paginated = self.get_paginated_data(queryset, request)

            # Serialize items
            data = {
                'data': [self.serialize_object(obj) for obj in paginated['items']],
                'columns': self.get_column_config(),
                'pagination': paginated['pagination'],
                'meta': {
                    'editable': bool(self.editable_fields),
                    'searchable': bool(self.searchable_fields),
                }
            }
            return JsonResponse(data)

        # Return HTML
        from dj_fixi.tables import ModelTable

        paginated = self.get_paginated_data(queryset, request)
        table = ModelTable(
            queryset=self.model.objects.filter(pk__in=[obj.pk for obj in paginated['items']]),
            fields=self.fields,
            editable_fields=self.editable_fields,
        )

        if self.template_name:
            context = {
                'table': table,
                'pagination': paginated['pagination'],
            }
            from django.shortcuts import render
            return render(request, self.template_name, context)

        return HttpResponse(table.render())

    def post(self, request, *args, **kwargs):
        """Create new record with validation and MCP response."""
        try:
            data = json.loads(request.body)

            # Validate data
            is_valid, errors = self.validate_data(data)
            if not is_valid:
                return self.mcp_error_response(
                    error="; ".join(errors),
                    status=400,
                    error_code='VALIDATION_ERROR'
                )

            # Filter to allowed fields
            create_data = {}
            for field in self.fields:
                if field in data and field != 'id':
                    create_data[field] = data[field]

            obj = self.model.objects.create(**create_data)

            return self.mcp_success_response(
                data=self.serialize_object(obj),
                status=201,
                extra_meta={'created_id': obj.pk}
            )

        except json.JSONDecodeError:
            return self.mcp_error_response(
                error="Invalid JSON",
                status=400,
                error_code='INVALID_JSON'
            )
        except ValidationError as e:
            return self.mcp_error_response(
                error=str(e),
                status=422,
                error_code='VALIDATION_ERROR'
            )
        except Exception as e:
            return self.mcp_error_response(
                error=str(e),
                status=500,
                error_code='INTERNAL_ERROR'
            )

    def patch(self, request, pk=None, *args, **kwargs):
        """
        Update record with validation and MCP response.

        - Inline edit: {id, column, value}
        - Full update: {id, field1: value1, field2: value2, ...}
        """
        try:
            data = json.loads(request.body)

            # Determine if inline edit or full update
            if 'column' in data and 'value' in data:
                # Inline single-field edit
                obj_pk = data.get('id') or pk
                obj = get_object_or_404(self.model, pk=obj_pk)

                field = data['column']
                value = data['value']

                # Validate field is editable
                if field not in self.editable_fields:
                    return self.mcp_error_response(
                        error='Field not editable',
                        status=403,
                        error_code='FIELD_NOT_EDITABLE'
                    )

                # Validate field exists
                try:
                    self.model._meta.get_field(field)
                except FieldDoesNotExist:
                    return self.mcp_error_response(
                        error='Invalid field',
                        status=400,
                        error_code='INVALID_FIELD'
                    )

                # Validate field value
                is_valid, error = self.validate_field(field, value)
                if not is_valid:
                    return self.mcp_error_response(
                        error=error,
                        status=400,
                        error_code='VALIDATION_ERROR'
                    )

                # Track old value if audit enabled
                if self.enable_audit_log:
                    old_value = getattr(obj, field)

                # Update field
                setattr(obj, field, value)
                obj.full_clean()
                obj.save(update_fields=[field])

                # Log change
                if self.enable_audit_log:
                    self.log_change(
                        obj=obj,
                        old_values={field: old_value},
                        new_values={field: value},
                        user=request.user
                    )

                return self.mcp_success_response(
                    data={
                        'id': obj.pk,
                        'column': field,
                        'value': value
                    },
                    extra_meta={'updated_fields': [field]}
                )
            else:
                # Full update
                obj_pk = data.pop('id', pk)
                obj = get_object_or_404(self.model, pk=obj_pk)

                # Validate all data
                is_valid, errors = self.validate_data(data)
                if not is_valid:
                    return self.mcp_error_response(
                        error="; ".join(errors),
                        status=400,
                        error_code='VALIDATION_ERROR'
                    )

                # Track changes if enabled
                if self.enable_audit_log:
                    old_values = {
                        field: getattr(obj, field)
                        for field in data.keys()
                        if hasattr(obj, field)
                    }

                # Update fields
                updated_fields = []
                for field, value in data.items():
                    if field in self.editable_fields:
                        setattr(obj, field, value)
                        updated_fields.append(field)

                obj.full_clean()
                obj.save(update_fields=updated_fields)

                # Log changes
                if self.enable_audit_log:
                    self.log_change(
                        obj=obj,
                        old_values=old_values,
                        new_values=data,
                        user=request.user
                    )

                return self.mcp_success_response(
                    data=self.serialize_object(obj),
                    extra_meta={'updated_fields': updated_fields}
                )

        except self.model.DoesNotExist:
            return self.mcp_error_response(
                error="Object not found",
                status=404,
                error_code='NOT_FOUND'
            )
        except json.JSONDecodeError:
            return self.mcp_error_response(
                error="Invalid JSON",
                status=400,
                error_code='INVALID_JSON'
            )
        except ValidationError as e:
            return self.mcp_error_response(
                error=str(e),
                status=422,
                error_code='VALIDATION_ERROR'
            )
        except Exception as e:
            return self.mcp_error_response(
                error=str(e),
                status=500,
                error_code='INTERNAL_ERROR'
            )

    def delete(self, request, pk=None, *args, **kwargs):
        """Delete record(s) with MCP response support."""
        try:
            data = json.loads(request.body) if request.body else {}

            # Bulk delete
            if 'ids' in data:
                ids = data['ids']
                count = self.model.objects.filter(pk__in=ids).delete()[0]

                if self.wants_json(request):
                    return self.mcp_success_response(
                        data={'deleted': count},
                        extra_meta={'operation': 'bulk_delete'}
                    )
                return HttpResponse('', status=200)

            # Single delete
            obj_pk = data.get('id') or pk
            obj = get_object_or_404(self.model, pk=obj_pk)
            deleted_id = obj.pk
            obj.delete()

            # Return MCP response for JSON requests, empty for HTML/Fixi
            if self.wants_json(request):
                return self.mcp_success_response(
                    data={'deleted': deleted_id},
                    extra_meta={'operation': 'delete'}
                )
            return HttpResponse('', status=200)  # Empty response for Fixi swap

        except self.model.DoesNotExist:
            return self.mcp_error_response(
                error="Object not found",
                status=404,
                error_code='NOT_FOUND'
            )
        except json.JSONDecodeError:
            return self.mcp_error_response(
                error="Invalid JSON",
                status=400,
                error_code='INVALID_JSON'
            )
        except Exception as e:
            return self.mcp_error_response(
                error=str(e),
                status=500,
                error_code='INTERNAL_ERROR'
            )

    def wants_json(self, request):
        """Check if client wants JSON response."""
        return (
            request.headers.get('FX-Data') == 'json'
            or 'application/json' in request.headers.get('Accept', '')
        )

    def get_column_config(self):
        """Get column configuration for FixiPlug."""
        columns = []
        for field_name in self.fields:
            try:
                field = self.model._meta.get_field(field_name)
                columns.append({
                    'key': field_name,
                    'label': field.verbose_name.title(),
                    'sortable': True,
                    'editable': field_name in self.editable_fields,
                })
            except FieldDoesNotExist:
                columns.append({
                    'key': field_name,
                    'label': field_name.replace('_', ' ').title(),
                    'sortable': True,
                    'editable': field_name in self.editable_fields,
                })
        return columns
