"""
Component generators for LLM agents.

LLMs use these to convert natural language into interactive components.
"""

import ast
import textwrap
from typing import Dict, List, Any, Optional
from django.apps import apps
from django.db import models


class ComponentGenerator:
    """
    Base class for generating dj-fixi components from LLM prompts.

    Subclasses implement specific component types (tables, charts, forms).
    """

    def __init__(self, user=None, allowed_models: List[str] = None):
        """
        Initialize generator.

        Args:
            user: Django user for permission checks
            allowed_models: List of model names this user can access
        """
        self.user = user
        self.allowed_models = allowed_models or []

    def get_available_models(self) -> Dict[str, Any]:
        """
        Get models the user can access with their schema.

        Returns:
            Dict mapping model name to schema info
        """
        available = {}

        for model_name in self.allowed_models:
            try:
                model = apps.get_model(model_name)
                available[model_name] = {
                    "verbose_name": model._meta.verbose_name,
                    "fields": self._get_model_fields(model),
                }
            except LookupError:
                continue

        return available

    def _get_model_fields(self, model) -> List[Dict[str, str]]:
        """Extract field information from model."""
        fields = []

        for field in model._meta.get_fields():
            if field.concrete:
                fields.append(
                    {
                        "name": field.name,
                        "type": field.get_internal_type(),
                        "verbose_name": getattr(field, "verbose_name", field.name),
                        "help_text": getattr(field, "help_text", ""),
                    }
                )

        return fields

    def validate_generated_code(self, code: str) -> tuple[bool, Optional[str]]:
        """
        Validate generated Python code for safety.

        Returns:
            (is_valid, error_message)
        """
        try:
            tree = ast.parse(code)

            # Check for disallowed operations
            for node in ast.walk(tree):
                # No imports (we provide everything in namespace)
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    return False, "Imports not allowed"

                # No exec/eval
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if node.func.id in ["exec", "eval", "__import__"]:
                            return False, f"Function {node.func.id} not allowed"

                # No file operations
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if node.func.id in ["open", "file"]:
                            return False, "File operations not allowed"

            return True, None

        except SyntaxError as e:
            return False, f"Syntax error: {str(e)}"

    def generate(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate component from natural language prompt.

        Subclasses must implement this.

        Args:
            prompt: Natural language description
            context: Additional context (filters, user preferences, etc.)

        Returns:
            {
                "component_type": "table|chart|form|...",
                "view_code": "Python code for view",
                "metadata": {...}
            }
        """
        raise NotImplementedError


class TableGenerator(ComponentGenerator):
    """Generate interactive tables from natural language."""

    def generate(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate FxCRUDView from prompt.

        Example:
            prompt = "Show me products with price > 100, sorted by name"
            context = {"default_limit": 20}

        Returns:
            {
                "component_type": "table",
                "view_code": "class GeneratedView(FxCRUDView): ...",
                "metadata": {
                    "model": "products.Product",
                    "fields": ["name", "price"],
                    "editable": false
                }
            }
        """
        # In real implementation, this would call an LLM API
        # For now, we'll create a template-based implementation

        return self._generate_from_template(prompt, context)

    def _generate_from_template(self, prompt: str, context: Dict) -> Dict[str, Any]:
        """
        Template-based generation (placeholder for LLM integration).

        Real implementation would:
        1. Send prompt + available models to LLM
        2. LLM returns structured data (model, fields, filters)
        3. We generate view code from that data
        """
        # Parse simple prompts (this is a simplified example)
        # In production, use LLM for this
        model_name = context.get("model")
        fields = context.get("fields", [])
        filters = context.get("filters", {})
        editable_fields = context.get("editable_fields", [])
        sortable = context.get("sortable", True)

        if not model_name:
            raise ValueError("Model name required in context")

        # Generate view code
        view_code = self._generate_crud_view(
            model_name=model_name,
            fields=fields,
            filters=filters,
            editable_fields=editable_fields,
        )

        # Validate
        is_valid, error = self.validate_generated_code(view_code)
        if not is_valid:
            raise ValueError(f"Generated invalid code: {error}")

        return {
            "component_type": "table",
            "view_code": view_code,
            "metadata": {
                "model": model_name,
                "fields": fields,
                "editable": bool(editable_fields),
                "sortable": sortable,
                "filters": filters,
            },
        }

    def _generate_crud_view(
        self,
        model_name: str,
        fields: List[str],
        filters: Dict[str, Any],
        editable_fields: List[str],
    ) -> str:
        """Generate FxCRUDView code."""
        filter_code = ""
        if filters:
            filter_items = [f"{k}='{v}'" if isinstance(v, str) else f"{k}={v}" for k, v in filters.items()]
            filter_code = f"queryset = queryset.filter({', '.join(filter_items)})"

        code = f"""
class GeneratedView(FxCRUDView):
    model = {model_name}
    fields = {fields}
    editable_fields = {editable_fields}
    searchable_fields = {fields[:2] if len(fields) > 1 else fields}
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()
        {filter_code if filter_code else '# No filters'}
        return queryset
"""
        return textwrap.dedent(code).strip()


class ChartGenerator(ComponentGenerator):
    """Generate interactive charts from natural language."""

    def generate(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate chart view from prompt.

        Example:
            prompt = "Show sales by region as a bar chart"
            context = {"model": "sales.Sale"}
        """
        model_name = context.get("model")
        chart_type = context.get("chart_type", "bar")
        x_field = context.get("x_field")
        y_field = context.get("y_field")
        aggregate = context.get("aggregate", "Sum")

        view_code = f"""
class GeneratedChartView(ChartView):
    chart_type = '{chart_type}'

    def get_data(self):
        from django.db.models import {aggregate}

        qs = {model_name}.objects.values('{x_field}').annotate(
            value={aggregate}('{y_field}')
        )

        return {{
            'labels': [r['{x_field}'] for r in qs],
            'datasets': [{{
                'label': '{y_field.title()}',
                'data': [r['value'] for r in qs]
            }}]
        }}
"""

        return {
            "component_type": "chart",
            "view_code": textwrap.dedent(view_code).strip(),
            "metadata": {
                "model": model_name,
                "chart_type": chart_type,
                "x_field": x_field,
                "y_field": y_field,
            },
        }


class FormGenerator(ComponentGenerator):
    """Generate interactive forms from natural language."""

    def generate(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate form view from prompt.

        Example:
            prompt = "Create a form to collect customer feedback"
            context = {"model": "feedback.Feedback", "fields": [...]}
        """
        model_name = context.get("model")
        fields = context.get("fields", [])

        view_code = f"""
class GeneratedFormView(FxView):
    template_name = 'form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        form = modelform_factory(
            {model_name},
            fields={fields}
        )

        context['form'] = form()
        return context

    def post(self, request, *args, **kwargs):
        form = modelform_factory(
            {model_name},
            fields={fields}
        )(request.POST)

        if form.is_valid():
            obj = form.save()
            return JsonResponse({{'success': True, 'id': obj.pk}})

        return JsonResponse({{'errors': form.errors}}, status=422)
"""

        return {
            "component_type": "form",
            "view_code": textwrap.dedent(view_code).strip(),
            "metadata": {
                "model": model_name,
                "fields": fields,
            },
        }


class DashboardGenerator(ComponentGenerator):
    """Generate multi-component dashboards."""

    def generate(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate dashboard with multiple widgets.

        Example:
            prompt = "Create a sales dashboard"
            context = {"widgets": ["kpi", "chart", "table"]}
        """
        widgets = context.get("widgets", [])

        # Generate sub-components
        components = []
        for widget_config in widgets:
            widget_type = widget_config.get("type")

            if widget_type == "table":
                gen = TableGenerator(self.user, self.allowed_models)
                components.append(gen.generate(widget_config.get("prompt", ""), widget_config))
            elif widget_type == "chart":
                gen = ChartGenerator(self.user, self.allowed_models)
                components.append(gen.generate(widget_config.get("prompt", ""), widget_config))

        view_code = """
class GeneratedDashboardView(FxView):
    template_name = 'dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['widgets'] = []
        # Widget views will be rendered separately
        return context
"""

        return {
            "component_type": "dashboard",
            "view_code": textwrap.dedent(view_code).strip(),
            "components": components,
            "metadata": {
                "layout": context.get("layout", "grid"),
                "widget_count": len(widgets),
            },
        }
