"""
Base views for Fixi.js integration with Django.

Adapted from django_hypermedia.views.base
"""

from django.http import HttpResponse, JsonResponse
from django.template.response import TemplateResponse
from django.views import View
from django.shortcuts import get_object_or_404
from django.core.exceptions import FieldDoesNotExist
import json


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


class FxCRUDView(View):
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
    searchable_fields = []  # Fields that can be searched
    template_name = None
    paginate_by = 10
    ordering = None

    def get_queryset(self):
        """Get base queryset."""
        if self.model is None:
            raise ValueError("model must be specified")
        return self.model.objects.all()

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
        """Create new record."""
        try:
            data = json.loads(request.body)

            # Validate fields
            create_data = {}
            for field in self.fields:
                if field in data:
                    create_data[field] = data[field]

            obj = self.model.objects.create(**create_data)

            return JsonResponse({
                'success': True,
                'id': obj.pk,
                'data': self.serialize_object(obj)
            }, status=201)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    def patch(self, request, pk=None, *args, **kwargs):
        """
        Update record.

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
                    return JsonResponse({'error': 'Field not editable'}, status=403)

                # Validate field exists
                try:
                    self.model._meta.get_field(field)
                except FieldDoesNotExist:
                    return JsonResponse({'error': 'Invalid field'}, status=400)

                # Update field
                setattr(obj, field, value)
                obj.full_clean()
                obj.save(update_fields=[field])

                return JsonResponse({
                    'success': True,
                    'id': obj.pk,
                    'column': field,
                    'value': value
                })
            else:
                # Full update
                obj_pk = data.pop('id', pk)
                obj = get_object_or_404(self.model, pk=obj_pk)

                # Update fields
                updated_fields = []
                for field, value in data.items():
                    if field in self.fields:
                        setattr(obj, field, value)
                        updated_fields.append(field)

                obj.full_clean()
                obj.save(update_fields=updated_fields)

                return JsonResponse({
                    'success': True,
                    'id': obj.pk,
                    'data': self.serialize_object(obj)
                })

        except ValueError as e:
            return JsonResponse({'error': f'Validation error: {str(e)}'}, status=422)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    def delete(self, request, pk=None, *args, **kwargs):
        """Delete record(s)."""
        try:
            data = json.loads(request.body) if request.body else {}

            # Bulk delete
            if 'ids' in data:
                ids = data['ids']
                count = self.model.objects.filter(pk__in=ids).delete()[0]
                return JsonResponse({'success': True, 'deleted': count})

            # Single delete
            obj_pk = data.get('id') or pk
            obj = get_object_or_404(self.model, pk=obj_pk)
            obj.delete()

            return HttpResponse('', status=200)  # Empty response for Fixi swap

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

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
