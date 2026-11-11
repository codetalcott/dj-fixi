"""
Django CBV mixins for Fixi.js integration.

``FxResponseMixin`` is the only one: it makes Django's form and delete views
answer Fixi requests with fragments.
"""

import inspect
import json
import logging
from typing import Any

from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse
from django.utils.http import url_has_allowed_host_and_scheme

from .request import is_fx as _is_fx

logger = logging.getLogger(__name__)


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
        Return the fragment for Fixi requests.

        A ``partial_template`` (set on the view, or from FxView when the two are
        composed) is the whole answer for a Fixi request: a name the author wrote
        down must not fall through to the full page when it is missing. Without
        one, Fixi requests get the same names as every other request; W202 names
        the view at boot. Nothing is derived by convention any more.
        """
        explicit = getattr(self, "partial_template", None)
        if explicit and _is_fx(self.request):
            return [explicit]
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

        if obj_pk is None:
            # Delete (or no object to render): nothing to swap.
            return self._fx_deleted(pk_before)

        # Create/update: hand back the rendered fragment for swapping in.
        detail["object_id"] = str(obj_pk)
        rendered_form = self.get_fx_success_form(form, created=pk_before is None)
        fx_response = self.render_to_response(self.get_context_data(form=rendered_form))
        self._trigger_fx_event(fx_response, self.fx_success_event, detail)
        return fx_response

    def delete(self, request, *args, **kwargs) -> HttpResponse:
        """
        Answer an HTTP ``DELETE`` the way a Fixi control expects.

        Django's ``DeletionMixin.delete()`` deletes and returns a redirect
        without going through ``form_valid``, so before 0.4.0 an
        ``fx-method="DELETE"`` control got a 302 that fetch followed *as a
        DELETE*, and the list view's 405 was swapped into the row. For a Fixi
        request this deletes the object and returns the same ``204`` and
        ``FX-Trigger`` event as the POST path; anything else defers to Django.
        Views without a delete path (a ``CreateView``) still answer 405.
        """
        parent = getattr(super(), "delete", None)
        if not callable(parent):
            return self.http_method_not_allowed(request, *args, **kwargs)
        if not _is_fx(request):
            return parent(request, *args, **kwargs)
        self.object = self.get_object()
        pk_before = self.object.pk
        self.object.delete()
        return self._fx_deleted(pk_before)

    def _fx_deleted(self, pk_before) -> HttpResponse:
        """``204 No Content`` plus the success event, naming the deleted object."""
        detail = {"message": self.get_success_message()}
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
        # getattr_static, not getattr: a plain function assigned as a class
        # attribute would otherwise bind as a method and be handed ``self``
        # twice. Four of six implementations hit this and wrapped it in
        # staticmethod to get around it.
        collection = inspect.getattr_static(self, "fx_collection", None)
        if isinstance(collection, (staticmethod, classmethod)):
            collection = collection.__func__
        if collection is None:
            return None
        if hasattr(collection, "all"):
            # Both a manager and a queryset. Cloning a class-level queryset is
            # the point: returned as-is it keeps its result cache for the life of
            # the process and serves the first request's rows forever.
            return collection.all()
        if callable(collection):
            return collection(self)
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
        Set the ``FX-Trigger`` header the ``{% fixi_events %}`` shim turns into a
        DOM event named ``event_name`` (no prefix), dispatched after the swap.

        The shim dispatches on the element that made the request when it is
        still in the document, otherwise on ``<body>``. A string ``detail["target"]``
        names a CSS selector to dispatch on instead, so that key is reserved.
        Without the shim (or an equivalent moxi ``on-fx:swapped`` handler) the
        header does nothing: fixi core reads no response headers.
        """
        if detail:
            # Send event with detail data
            response["FX-Trigger"] = json.dumps({event_name: detail})
        else:
            # Simple event trigger
            response["FX-Trigger"] = event_name
