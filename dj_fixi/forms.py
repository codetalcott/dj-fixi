"""
Backend-driven form rendering with automatic Fixi.js integration.

Provides Django forms with built-in Fixi attributes for inline editing and updates.
"""

from django import forms
from django.forms.utils import flatatt
from django.utils.html import format_html
from django.utils.safestring import mark_safe


class FxForm:
    """
    Wraps a Django form with automatic Fixi.js attributes.

    Example:
        fx_form = FxForm(
            form=ProductForm(instance=product),
            action=reverse('product_update', args=[product.pk]),
            target=f'#row-{product.pk}',
            swap='outerHTML'
        )
        # In template: {{ fx_form.render }}
    """

    def __init__(
        self,
        form: forms.Form,
        action: str,
        method: str = "POST",
        target: str | None = None,
        swap: str = "innerHTML",
        trigger: str = "submit",
        css_class: str = "fx-form",
        cancel_action: str | None = None,
    ):
        self.form = form
        self.action = action
        self.method = method
        self.target = target
        self.swap = swap
        self.trigger = trigger
        self.css_class = css_class
        # Endpoint the Cancel button GETs to restore the original view; falls
        # back to ``action`` when not supplied.
        self.cancel_action = cancel_action

    def render_attrs(self) -> str:
        """Generate Fixi.js attributes for the form tag (values HTML-escaped)."""
        attrs = {
            "fx-action": self.action,
            "fx-method": self.method,
            "fx-swap": self.swap,
            "fx-trigger": self.trigger,
        }

        if self.target:
            attrs["fx-target"] = self.target

        return mark_safe(flatatt(attrs).lstrip())

    def render(self) -> str:
        """Render complete form with Fixi attributes."""
        return format_html(
            '<form class="{}" {}>'
            "{}"
            '<button type="submit">Save</button>'
            '<button type="button" fx-action="" fx-target="{}" fx-swap="outerHTML">Cancel</button>'
            "</form>",
            self.css_class,
            self.render_attrs(),
            self.form.as_p(),
            self.target or "",
        )

    def __str__(self) -> str:
        """Allow {{ fx_form }} in templates."""
        return self.render()


class InlineEditForm(FxForm):
    """
    Specialized form for inline table row editing.

    Automatically configures Fixi attributes for row replacement.

    Example:
        inline_form = InlineEditForm(
            form=ProductForm(instance=product),
            action=reverse('product_update', args=[product.pk]),
            row_id=f'row-{product.pk}',
            cancel_action=reverse('product_row', args=[product.pk]),
        )
    """

    def __init__(
        self,
        form: forms.Form,
        action: str,
        row_id: str,
        cancel_action: str | None = None,
        **kwargs,
    ):
        super().__init__(
            form=form,
            action=action,
            target=f"#{row_id}",
            swap="outerHTML",
            method="POST",
            cancel_action=cancel_action,
            **kwargs,
        )
        self.row_id = row_id

    def render(self) -> str:
        """Render inline edit form as table row."""
        cells = []

        for field in self.form:
            cells.append(format_html("<td>{}</td>", field))

        # Actions cell
        cells.append(
            format_html(
                "<td>"
                '<button type="submit">Save</button> '
                '<button type="button" '
                'fx-action="{}" '
                'fx-method="GET" '
                'fx-target="#{}" '
                'fx-swap="outerHTML">'
                "Cancel</button>"
                "</td>",
                self.cancel_action or self.action,  # GET endpoint that restores the row
                self.row_id,
            )
        )

        return format_html(
            '<tr id="{}" class="editing"><form {}>{}</form></tr>',
            self.row_id,
            self.render_attrs(),
            mark_safe("".join(cells)),
        )


class FxModelForm(forms.ModelForm):
    """
    ModelForm with Fixi-aware rendering helpers.

    Provides methods to render forms with automatic Fixi attributes.
    """

    def as_fx_inline(self, target: str, action: str, cancel_action: str | None = None) -> str:
        """Render as inline editable form."""
        return InlineEditForm(
            form=self, action=action, row_id=target.lstrip("#"), cancel_action=cancel_action
        ).render()

    def as_fx_form(self, action: str, target: str | None = None, **kwargs) -> str:
        """Render as standard Fixi form."""
        return FxForm(form=self, action=action, target=target, **kwargs).render()
