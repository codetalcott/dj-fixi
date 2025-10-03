"""
Field-type aware CRUD table renderers for Fixi.js integration.

Adapted from python-modules/crud/crud-generator-proposal-2.md
"""

from typing import Any, Dict, List, Optional, Type

from django.db import models
from django.urls import reverse


class ModelTableRenderer:
    """
    Base class for rendering CRUD tables with field-type aware inline editing.

    Generates Fixi.js attributes instead of HTMX attributes.

    Usage:
        renderer = ModelTableRenderer(
            objects=User.objects.all(),
            resource_name='users',
            edit_field='email',
            edit_obj=user_instance
        )
    """

    resource_name: str = None  # e.g. "users" - used for URL generation
    id_field: str = "id"
    include_actions: bool = True
    fields: list = None  # Override to specify field order/subset

    def __init__(self, objects, model=None, edit_field=None, edit_obj=None):
        """
        Args:
            objects: Queryset or iterable of model instances
            model: Django model class (inferred from queryset if not provided)
            edit_field: Field name currently in edit mode
            edit_obj: Model instance currently in edit mode
        """
        self.objects = objects
        self.model = model or self._infer_model(objects)
        self.edit_field = edit_field
        self.edit_obj = edit_obj

        # Build field list if not explicitly set
        if self.fields is None:
            self.fields = self._get_model_fields()

        if self.include_actions and "actions" not in self.fields:
            self.fields.append("actions")

    def _infer_model(self, objects):
        """Infer model from queryset or first object."""
        if hasattr(objects, "model"):
            return objects.model
        try:
            return type(next(iter(objects)))
        except (StopIteration, TypeError):
            raise ValueError("Cannot infer model from empty objects")

    def _get_model_fields(self):
        """Get concrete model fields, excluding reverse relations."""
        return [f.name for f in self.model._meta.get_fields() if hasattr(f, "attname")]

    # ---- Permission Hooks ----

    def can_edit_field(self, obj, field_name):
        """
        Override to implement field-level edit permissions.

        Returns:
            bool: True if field can be edited
        """
        return True

    def get_action_url(self, obj, action):
        """
        Generate URL for an action.

        Args:
            obj: Model instance
            action: Action name ('edit', 'update', 'delete')

        Returns:
            str: URL for the action
        """
        obj_id = getattr(obj, self.id_field)
        return f"/{self.resource_name}/{obj_id}/{action}"

    # ---- Widget Configuration ----

    def _widget_context(self, field, value, obj):
        """
        Return widget configuration dict based on Django field type.

        Returns:
            dict: Widget configuration with keys:
                - type: Widget type (checkbox, date, select, text, etc.)
                - name: Field name
                - value: Current value (formatted for widget)
                - attrs: Additional HTML attributes
                - choices: For select widgets
                - selected: For select widgets
        """
        base_attrs = "onblur='this.form.requestSubmit()'"

        if isinstance(field, models.BooleanField):
            return {
                "type": "checkbox",
                "name": field.name,
                "checked": value is True,
                "attrs": "onchange='this.form.requestSubmit()'",
            }

        elif isinstance(field, models.DateTimeField):
            formatted_value = value.strftime("%Y-%m-%dT%H:%M") if value else ""
            return {"type": "datetime-local", "name": field.name, "value": formatted_value, "attrs": base_attrs}

        elif isinstance(field, models.DateField):
            formatted_value = value.isoformat() if value else ""
            return {"type": "date", "name": field.name, "value": formatted_value, "attrs": base_attrs}

        elif isinstance(field, models.TimeField):
            formatted_value = value.strftime("%H:%M:%S") if value else ""
            return {"type": "time", "name": field.name, "value": formatted_value, "attrs": base_attrs}

        elif isinstance(field, models.IntegerField):
            return {
                "type": "number",
                "name": field.name,
                "value": value if value is not None else "",
                "attrs": base_attrs,
                "step": "1",
            }

        elif isinstance(field, models.FloatField):
            return {
                "type": "number",
                "name": field.name,
                "value": value if value is not None else "",
                "attrs": base_attrs,
                "step": "any",
            }

        elif isinstance(field, models.DecimalField):
            return {
                "type": "number",
                "name": field.name,
                "value": str(value) if value is not None else "",
                "attrs": base_attrs,
                "step": "0.01",
            }

        elif isinstance(field, models.ForeignKey):
            # Build choices from related model
            related_qs = self._get_foreignkey_queryset(field, obj)
            choices = [(rel_obj.pk, str(rel_obj)) for rel_obj in related_qs]

            # Add blank option if field is nullable
            if field.null:
                choices.insert(0, (None, "---"))

            return {
                "type": "select",
                "name": field.name,
                "choices": choices,
                "selected": value.pk if value else None,
                "attrs": "onchange='this.form.requestSubmit()'",
            }

        elif hasattr(field, "choices") and field.choices:
            # Handle fields with choices
            return {
                "type": "select",
                "name": field.name,
                "choices": field.choices,
                "selected": value,
                "attrs": "onchange='this.form.requestSubmit()'",
            }

        elif isinstance(field, models.TextField):
            return {
                "type": "textarea",
                "name": field.name,
                "value": str(value) if value is not None else "",
                "attrs": base_attrs,
                "rows": 3,
            }

        elif isinstance(field, models.EmailField):
            return {
                "type": "email",
                "name": field.name,
                "value": str(value) if value is not None else "",
                "attrs": base_attrs,
            }

        elif isinstance(field, models.URLField):
            return {
                "type": "url",
                "name": field.name,
                "value": str(value) if value is not None else "",
                "attrs": base_attrs,
            }

        else:
            # Default to text input
            return {
                "type": "text",
                "name": field.name,
                "value": str(value) if value is not None else "",
                "attrs": base_attrs,
                "maxlength": getattr(field, "max_length", None),
            }

    def _get_foreignkey_queryset(self, field, obj):
        """
        Get queryset for ForeignKey choices.

        Args:
            field: ForeignKey field
            obj: Current model instance

        Returns:
            QuerySet: Related model objects
        """
        return field.related_model.objects.all()

    # ---- Display Formatting ----

    def format_value(self, obj, field_name, value):
        """
        Format a field value for display.

        Args:
            obj: Model instance
            field_name: Field name
            value: Raw field value

        Returns:
            str: Formatted value for display
        """
        if value is None:
            return ""

        field = self.model._meta.get_field(field_name)

        if isinstance(field, models.BooleanField):
            return "✓" if value else "✗"
        elif isinstance(field, models.DateTimeField):
            return value.strftime("%Y-%m-%d %H:%M")
        elif isinstance(field, models.DateField):
            return value.strftime("%Y-%m-%d")
        elif isinstance(field, models.DecimalField):
            return f"{value:.2f}"
        elif isinstance(field, models.ForeignKey):
            return str(value)
        else:
            return str(value)

    # ---- Context Building ----

    def cell_context(self, obj, field_name):
        """
        Build context dict for a single cell.

        Returns:
            dict: Cell context with keys:
                - value: Formatted display value
                - attrs: HTML attributes for <td> (Fixi attributes)
                - actions: List of action dicts (for actions column)
                - widget: Widget configuration dict (for edit mode)
                - edit_url: URL for update action (for edit mode)
                - is_editing: Boolean flag
        """
        obj_id = getattr(obj, self.id_field)

        # Actions column
        if field_name == "actions":
            return {"actions": self.get_actions(obj), "attrs": ""}

        # Get field and value
        field = self.model._meta.get_field(field_name)
        value = getattr(obj, field_name)

        # Check if this cell is in edit mode
        is_editing = (
            self.edit_field == field_name
            and self.edit_obj
            and obj.pk == self.edit_obj.pk
            and self.can_edit_field(obj, field_name)
        )

        if is_editing:
            return {
                "widget": self._widget_context(field, value, obj),
                "edit_url": self.get_action_url(obj, "update"),
                "is_editing": True,
                "attrs": "",
            }

        # Display mode - make clickable if editable (using Fixi attributes)
        if self.can_edit_field(obj, field_name):
            edit_url = self.get_action_url(obj, "edit")
            attrs = (
                f'fx-action="{edit_url}?field={field_name}" '
                f'fx-method="GET" '
                f'fx-target="this" '
                f'fx-swap="outerHTML" '
                f'style="cursor: pointer;"'
            )
        else:
            attrs = ""

        return {"value": self.format_value(obj, field_name, value), "attrs": attrs, "is_editing": False}

    def get_actions(self, obj):
        """
        Get list of action configurations for an object.

        Returns:
            list: List of action dicts with keys:
                - label: Button label
                - fx_action: Fixi action URL
                - fx_method: HTTP method (GET, POST, DELETE)
                - classes: CSS classes for button
                - confirm: Confirmation message (optional)
        """
        return [
            {
                "label": "Edit",
                "fx_action": self.get_action_url(obj, "edit"),
                "fx_method": "GET",
                "classes": "btn-edit",
            },
            {
                "label": "Delete",
                "fx_action": self.get_action_url(obj, "delete"),
                "fx_method": "DELETE",
                "classes": "btn-delete",
                "confirm": f"Delete this {self.model._meta.verbose_name}?",
            },
        ]

    def row_context(self, obj):
        """
        Build context list for all cells in a row.

        Returns:
            list: List of cell context dicts
        """
        return [self.cell_context(obj, field_name) for field_name in self.fields]

    def get_header_display(self, field_name):
        """
        Get display name for table header.

        Args:
            field_name: Field name

        Returns:
            str: Display name for header
        """
        if field_name == "actions":
            return "Actions"

        field = self.model._meta.get_field(field_name)
        return field.verbose_name.title()
