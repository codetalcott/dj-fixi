"""
Django CBV mixins for Fixi.js integration.

Simplified to include only essential, non-opinionated mixins.
"""

import json
import logging
from typing import Any
from urllib.parse import urlencode

from django.core.exceptions import FieldDoesNotExist, ImproperlyConfigured
from django.db import models
from django.http import HttpResponse
from django.utils.http import url_has_allowed_host_and_scheme

from .request import is_fx as _is_fx

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
        if self.filterset_class:
            filterset = self.get_filterset(queryset)
            if filterset is not None:
                queryset = filterset.qs
                self.filterset = filterset
        elif self.filterset_fields:
            queryset = self.filter_queryset(queryset)

        # Apply sorting with validation
        sort_param = self.request.GET.get("sort", "")
        if sort_param:
            # Validate against the queryset's model, which is always available
            # even when the view sets ``queryset`` rather than ``model``. Sort
            # values come from the query string, so an unknown one is ignored
            # rather than raised -- but a *valid* related-field sort such as
            # ``category__name`` must work, which means walking the segments.
            if self._is_sortable(queryset.model, sort_param.lstrip("-")):
                queryset = queryset.order_by(sort_param)
            else:
                logger.warning("Invalid sort field: %s", sort_param.lstrip("-"))

        return queryset

    def get_filterset(self, queryset: models.QuerySet) -> Any | None:
        """Initialize filterset with current queryset and request."""
        if self.filterset_class:
            return self.filterset_class(self.request.GET, queryset=queryset, request=self.request)
        return None

    def filter_queryset(self, queryset: models.QuerySet) -> models.QuerySet:
        """
        Apply ``filterset_fields`` from ``request.GET``, without a filter library.

        Each declared name is checked against the model up front, so a typo in
        ``filterset_fields`` raises ImproperlyConfigured instead of quietly
        filtering nothing. Values absent from the query string are skipped, so
        this is a no-op until the user actually filters.

        Only exact matches on concrete fields are supported. For lookups
        (``price__gte``), relations, or custom widgets, set ``filterset_class``.
        """
        lookups = {}
        for field_name in self.filterset_fields:
            if "__" in field_name:
                raise ImproperlyConfigured(
                    f"{type(self).__name__}.filterset_fields contains "
                    f"{field_name!r}, but filterset_fields only supports exact "
                    "matches on concrete fields. Use filterset_class for lookups."
                )
            try:
                queryset.model._meta.get_field(field_name)
            except FieldDoesNotExist as exc:
                raise ImproperlyConfigured(
                    f"{type(self).__name__}.filterset_fields contains "
                    f"{field_name!r}, which is not a field on "
                    f"{queryset.model.__name__}."
                ) from exc

            value = self.request.GET.get(field_name)
            if value:
                lookups[field_name] = value

        return queryset.filter(**lookups) if lookups else queryset

    @staticmethod
    def _is_sortable(model: type[models.Model], path: str) -> bool:
        """True when ``path`` (possibly ``a__b__c``) resolves to a field."""
        for segment in path.split("__"):
            if model is None:
                return False
            try:
                field = model._meta.get_field(segment)
            except FieldDoesNotExist:
                return False
            model = field.related_model
        return True

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

    #: After a successful *create*, render a fresh unbound form rather than the
    #: bound one. Without this the fragment echoes back the values just saved,
    #: into a form the user is about to type into again. Updates are unaffected:
    #: their bound values are the object's current state.
    fx_reset_form_after_create: bool = True

    #: The collection this view's fragment displays. A create view's success
    #: fragment almost always shows the list the new object just joined, but
    #: ``ModelFormMixin`` has no ``object_list``, so every project re-queried the
    #: list view's queryset by hand in ``get_context_data``. Accepts a queryset,
    #: a manager, or a callable taking the view.
    fx_collection: Any = None

    #: Context name for :attr:`fx_collection`. Defaults to the model's
    #: ``model_name_list``, matching what ``ListView`` would produce.
    fx_collection_name: str | None = None

    #: Where a non-Fixi POST redirects when neither ``success_url`` nor the
    #: object's ``get_absolute_url()`` supplies one. Falls back to the page the
    #: form was submitted from, which for a fragment-driven page is the list the
    #: user is already looking at. Set to ``False`` to restore Django's
    #: ``ImproperlyConfigured``.
    fx_default_success_url: str | bool | None = None

    def get_template_names(self) -> list[str]:
        """
        Return fragment templates for Fixi requests.

        An explicit ``partial_template`` (from FxView, when the two are composed)
        wins outright. Names this mixin *derives* by convention go behind it:
        letting a guessed ``foo_partial.html`` outrank the fragment the author
        actually named is the silent-failure shape this library exists to avoid.
        Deriving from the explicit partial is skipped too, since it is already a
        fragment and only produced nonsense like ``_panel_partial.html``.
        """
        if not _is_fx(self.request):
            return super().get_template_names()

        original_templates = super().get_template_names()
        explicit = getattr(self, "partial_template", None)
        fx_templates = []

        for template in original_templates:
            if template == explicit:
                continue

            # Insert suffix before file extension
            name_parts = template.rsplit(".", 1)
            if len(name_parts) == 2:
                # Skip names that already carry the suffix -- FxView derives its
                # own "_partial" variant, and suffixing that again only produced
                # a "_partial_partial.html" lookup that can never resolve.
                if not name_parts[0].endswith(self.fx_template_suffix):
                    fx_templates.append(f"{name_parts[0]}{self.fx_template_suffix}.{name_parts[1]}")

            # Also try a fragments subdirectory
            parts = template.rsplit("/", 1)
            if len(parts) == 2:
                fragment_template = f"{parts[0]}/fragments/{parts[1]}"
                fx_templates.append(fragment_template)

        ordered = ([explicit] if explicit else []) + fx_templates + original_templates
        return list(dict.fromkeys(ordered))

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

        try:
            response = super().form_valid(form)
        except ImproperlyConfigured:
            # ModelFormMixin saves the object and *then* builds the success
            # redirect. A Fixi request discards that redirect entirely, so a
            # missing success_url must not turn an already-committed save into a
            # 500 -- the row exists by the time this raises. Non-Fixi requests
            # still need the redirect, so they re-raise as before.
            if not _is_fx(self.request) or getattr(self, "object", None) is None:
                raise
            response = None

        if not _is_fx(self.request):
            return response

        detail = {"message": self.get_success_message()}
        obj = getattr(self, "object", None)
        obj_pk = getattr(obj, "pk", None)

        if obj_pk is not None:
            # Create/update: hand back the rendered fragment for swapping in.
            detail["object_id"] = str(obj_pk)
            rendered_form = self.get_fx_success_form(form, created=pk_before is None)
            fx_response = self.render_to_response(self.get_context_data(form=rendered_form))
        else:
            # Delete (or no object to render): nothing to swap.
            if pk_before is not None:
                detail["object_id"] = str(pk_before)
            fx_response = HttpResponse(status=204)

        self._trigger_fx_event(fx_response, self.fx_success_event, detail)
        return fx_response

    def get_fx_success_form(self, form, created: bool):
        """
        The form to render back into the fragment after a successful save.

        Returns a fresh unbound form for a create (see
        ``fx_reset_form_after_create``) and the bound form for an update.
        Override for anything more specific -- a form whose constructor needs
        arguments, for instance.
        """
        if not created or not self.fx_reset_form_after_create:
            return form

        get_form_class = getattr(self, "get_form_class", None)
        if not callable(get_form_class):
            return form
        try:
            return get_form_class()()
        except TypeError:
            # The form needs constructor arguments we cannot guess. Keep the
            # bound form rather than failing a save that already committed.
            logger.warning(
                "%s could not build an unbound %s to reset the form after "
                "create; override get_fx_success_form() to control this.",
                type(self).__name__,
                getattr(get_form_class(), "__name__", "form"),
            )
            return form

    def get_fx_collection(self):
        """
        Resolve :attr:`fx_collection` to something a template can iterate.

        Returns ``None`` when the view does not declare one, which leaves the
        context exactly as it was.
        """
        collection = self.fx_collection
        if collection is None:
            return None
        if callable(collection) and not hasattr(collection, "all"):
            return collection(self)
        if hasattr(collection, "all") and not isinstance(collection, models.QuerySet):
            return collection.all()  # a manager
        return collection

    def get_fx_collection_name(self) -> str:
        """Context key for the collection. Mirrors ListView's default name."""
        if self.fx_collection_name:
            return self.fx_collection_name
        model = getattr(self, "model", None)
        if model is None:
            queryset = getattr(self, "queryset", None)
            model = getattr(queryset, "model", None)
        if model is not None:
            return f"{model._meta.model_name}_list"
        return "object_list"

    def get_context_data(self, **kwargs) -> dict[str, Any]:
        """Add the declared collection so a form view's fragment can render it."""
        context = super().get_context_data(**kwargs)
        collection = self.get_fx_collection()
        if collection is not None:
            context.setdefault(self.get_fx_collection_name(), collection)
            context.setdefault("object_list", collection)
        return context

    def get_success_url(self) -> str:
        """
        Django's success URL, with a fallback so Fixi-only views need not invent one.

        ``ModelFormMixin`` requires ``success_url`` or ``get_absolute_url()`` even
        on a view whose Fixi path discards the redirect entirely. Six of six
        implementations declared one purely to satisfy that. When neither is
        present the referring page is used, which is where a fragment-driven form
        was submitted from.
        """
        try:
            return super().get_success_url()
        except ImproperlyConfigured:
            if self.fx_default_success_url is False:
                raise
            url = self.fx_default_success_url
            if url:
                return str(url)
            referer = self.request.META.get("HTTP_REFERER")
            if referer and url_has_allowed_host_and_scheme(
                referer,
                allowed_hosts={self.request.get_host()},
                require_https=self.request.is_secure(),
            ):
                return referer
            raise

    def form_invalid(self, form) -> HttpResponse:
        """Handle form validation errors for Fixi requests."""
        if _is_fx(self.request):
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
        """
        Generate a success message for the operation.

        Falls back to the saved object's own class, then to a generic message:
        a FormView composed with this mixin has no ``model``, and reading it
        blindly raised AttributeError on the *success* path only.
        """
        model = getattr(self, "model", None)
        if model is None:
            obj = getattr(self, "object", None)
            model = type(obj) if obj is not None else None
        meta = getattr(model, "_meta", None)
        if meta is not None:
            return f"{meta.verbose_name.title()} saved successfully"
        return "Saved successfully"

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
