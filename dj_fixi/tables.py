"""
Backend-driven table rendering with automatic Fixi.js integration.

Generates editable tables with inline editing capabilities without manual template code.
Supports both HTML rendering (server-side) and JSON output (for FixiPlug client-side rendering).
"""

import json
from typing import Any, Dict, List, Optional, Callable
from django.db import models
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.urls import reverse
from django.core.serializers.json import DjangoJSONEncoder


class Column:
    """Represents a table column with optional edit capabilities."""

    def __init__(
        self,
        name: str,
        label: Optional[str] = None,
        sortable: bool = False,
        editable: bool = False,
        field_type: str = "text",
        formatter: Optional[Callable] = None,
    ):
        self.name = name
        self.label = label or name.replace("_", " ").title()
        self.sortable = sortable
        self.editable = editable
        self.field_type = field_type
        self.formatter = formatter

    def get_value(self, obj: models.Model) -> Any:
        """Get the value from the model instance."""
        value = getattr(obj, self.name)
        if self.formatter:
            return self.formatter(value)
        return value

    def render_cell(self, obj: models.Model, editable_mode: bool = False) -> str:
        """Render the table cell HTML."""
        value = self.get_value(obj)

        if editable_mode and self.editable:
            # Render as editable cell with Fixi attributes
            cell_id = f"cell-{obj.pk}-{self.name}"
            return format_html(
                '<td id="{}" class="editable" '
                'fx-action="{}" '
                'fx-method="PATCH" '
                'fx-target="#{}" '
                'fx-trigger="dblclick">'
                '{}</td>',
                cell_id,
                reverse(f"{obj._meta.model_name}_update_field", args=[obj.pk, self.name]),
                cell_id,
                value or "-",
            )
        return format_html("<td>{}</td>", value or "-")


class ActionColumn:
    """Special column for CRUD actions (edit, delete, etc)."""

    def __init__(self, actions: List[str] = None):
        self.actions = actions or ["edit", "delete"]
        self.label = "Actions"
        self.sortable = False

    def render_cell(self, obj: models.Model, view_name_prefix: str = None) -> str:
        """Render action buttons with Fixi attributes."""
        model_name = obj._meta.model_name
        prefix = view_name_prefix or model_name

        buttons = []

        if "edit" in self.actions:
            buttons.append(
                format_html(
                    '<button type="button" '
                    'fx-action="{}" '
                    'fx-method="GET" '
                    'fx-target="#row-{}" '
                    'fx-swap="outerHTML">'
                    "Edit</button>",
                    reverse(f"{prefix}_update", args=[obj.pk]),
                    obj.pk,
                )
            )

        if "delete" in self.actions:
            buttons.append(
                format_html(
                    '<button type="button" '
                    'fx-action="{}" '
                    'fx-method="DELETE" '
                    'fx-target="#row-{}" '
                    'fx-swap="outerHTML" '
                    'onclick="return confirm(\'Delete {}?\');">'
                    "Delete</button>",
                    reverse(f"{prefix}_delete", args=[obj.pk]),
                    obj.pk,
                    obj,
                )
            )

        return format_html("<td>{}</td>", mark_safe(" ".join(buttons)))


class FxTable:
    """
    Declarative table with automatic Fixi.js integration.

    Example:
        table = FxTable(
            queryset=Product.objects.all(),
            columns=[
                Column('name', sortable=True, editable=True),
                Column('price', formatter=lambda p: f'${p}'),
                Column('stock', editable=True),
                ActionColumn(['edit', 'delete']),
            ]
        )
    """

    def __init__(
        self,
        queryset: models.QuerySet,
        columns: List[Column],
        editable: bool = True,
        row_id_template: str = "row-{pk}",
        css_class: str = "fx-table",
        view_name_prefix: Optional[str] = None,
    ):
        self.queryset = queryset
        self.columns = columns
        self.editable = editable
        self.row_id_template = row_id_template
        self.css_class = css_class
        self.view_name_prefix = view_name_prefix

    def render_header(self) -> str:
        """Render table header with optional sort links."""
        headers = []
        for col in self.columns:
            if col.sortable:
                # TODO: Add sort link with Fixi attrs
                headers.append(format_html("<th>{}</th>", col.label))
            else:
                headers.append(format_html("<th>{}</th>", col.label))

        return format_html("<thead><tr>{}</tr></thead>", mark_safe("".join(headers)))

    def render_row(self, obj: models.Model) -> str:
        """Render a single table row."""
        row_id = self.row_id_template.format(pk=obj.pk)
        cells = []

        for col in self.columns:
            if isinstance(col, ActionColumn):
                cells.append(col.render_cell(obj, self.view_name_prefix))
            else:
                cells.append(col.render_cell(obj, editable_mode=self.editable))

        return format_html('<tr id="{}">{}</tr>', row_id, mark_safe("".join(cells)))

    def render_body(self) -> str:
        """Render table body with all rows."""
        rows = [self.render_row(obj) for obj in self.queryset]

        if not rows:
            colspan = len(self.columns)
            rows.append(
                format_html(
                    '<tr><td colspan="{}" class="empty">No records found.</td></tr>',
                    colspan,
                )
            )

        return format_html("<tbody>{}</tbody>", mark_safe("".join(rows)))

    def render(self) -> str:
        """Render complete table HTML."""
        return format_html(
            '<table class="{}">{}{}</table>',
            self.css_class,
            self.render_header(),
            self.render_body(),
        )

    def __str__(self) -> str:
        """Allow {{ table }} in templates."""
        return self.render()

    def to_json(self) -> str:
        """
        Serialize table data for FixiPlug client-side rendering.

        Returns JSON with:
        - data: Array of row objects
        - columns: Column configuration for FixiPlug
        - meta: Additional metadata (sorting, pagination, etc.)
        """
        data = []
        for obj in self.queryset:
            row_data = {}
            for col in self.columns:
                if not isinstance(col, ActionColumn):
                    row_data[col.name] = col.get_value(obj)
            # Add id for row identification
            if hasattr(obj, "pk"):
                row_data["id"] = obj.pk
            data.append(row_data)

        # Build column config for FixiPlug
        columns_config = []
        for col in self.columns:
            if isinstance(col, ActionColumn):
                continue  # Actions handled separately

            col_config = {
                "key": col.name,
                "label": col.label,
                "sortable": col.sortable,
            }

            # Add FixiPlug-specific config
            if col.editable:
                col_config["editable"] = True
                col_config["inputType"] = col.field_type or "text"

            columns_config.append(col_config)

        return json.dumps(
            {
                "data": data,
                "columns": columns_config,
                "meta": {
                    "editable": self.editable,
                    "viewPrefix": self.view_name_prefix,
                },
            },
            cls=DjangoJSONEncoder,
        )

    def to_fixiplug_attrs(self) -> Dict[str, str]:
        """
        Generate FixiPlug table attributes for HTML rendering.

        Use in templates like:
        <div {% for k, v in table.to_fixiplug_attrs.items %}{{ k }}="{{ v }}" {% endfor %}>
            {{ table }}
        </div>
        """
        attrs = {
            "fx-table": "",
            "fx-table-sortable": "",
        }

        if self.editable:
            attrs["fx-table-editable"] = ""

        # Add save endpoint if using inline editing
        if self.view_name_prefix:
            attrs["fx-table-save-url"] = reverse(f"{self.view_name_prefix}_update_field")

        return attrs


class ModelTable(FxTable):
    """
    Automatically builds table from Django model.

    Example:
        table = ModelTable(
            queryset=Product.objects.all(),
            fields=['name', 'price', 'stock'],
            editable_fields=['name', 'stock'],
            actions=['edit', 'delete']
        )
    """

    def __init__(
        self,
        queryset: models.QuerySet,
        fields: List[str],
        editable_fields: List[str] = None,
        actions: List[str] = None,
        formatters: Dict[str, Callable] = None,
        **kwargs,
    ):
        editable_fields = editable_fields or []
        formatters = formatters or {}

        # Build columns from model fields
        columns = []
        model = queryset.model

        for field_name in fields:
            try:
                field = model._meta.get_field(field_name)
                columns.append(
                    Column(
                        name=field_name,
                        label=field.verbose_name.title(),
                        sortable=True,
                        editable=field_name in editable_fields,
                        formatter=formatters.get(field_name),
                    )
                )
            except Exception:
                # Handle non-field attributes
                columns.append(
                    Column(
                        name=field_name,
                        editable=field_name in editable_fields,
                        formatter=formatters.get(field_name),
                    )
                )

        # Add action column if specified
        if actions:
            columns.append(ActionColumn(actions))

        super().__init__(queryset=queryset, columns=columns, **kwargs)
