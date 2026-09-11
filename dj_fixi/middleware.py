"""
Middleware for detecting Fixi requests, and for saying under DEBUG what fixi
would otherwise do silently.

Optional since 0.3.0: ``dj_fixi.is_fx`` reads the header itself. Installing it
still buys ``request.is_fx`` for your own code, ``Vary: FX-Request`` on every
response, and, under ``DEBUG``, three things logged to ``dj_fixi.middleware``:
lint findings for every Fixi response (see :mod:`dj_fixi.lint`), a redirect
that fetch would follow into a fragment target, and the template each Fixi
response came from (also sent as ``X-FX-Template``).

Nothing here raises. A rule with a residual false positive must not become a
500 that blocks development; the test client (``FxTestClient``) is where
strictness lives.
"""

import logging
import time

from django.conf import settings

from .lint import lint_response
from .request import FX_REQUEST_HEADER, redirect_note, vary_on_fx

logger = logging.getLogger("dj_fixi.middleware")

#: fetch keeps the method across a 301/302/307/308 for these, so the redirect
#: target receives a DELETE (or PUT, PATCH) it almost never expects. A POST is
#: turned into a GET, which is the post-redirect-get idiom and is fine.
_METHOD_PRESERVED = ("DELETE", "PUT", "PATCH")


class FxMiddleware:
    """
    Detects Fixi.js requests and adds fixi-related attributes to request object.

    Also records per-request timing via the X-Execution-Time response header.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Add timing
        request._fx_start_time = time.time()

        # Detect Fixi request. Fixi.js sends exactly one custom request header
        # (``FX-Request: true``); it does not send target/swap/trigger headers
        # (those are client-side concerns), so there is nothing else to extract.
        request.is_fx = request.headers.get(FX_REQUEST_HEADER) == "true"

        # Process request
        response = self.get_response(request)

        # Add execution time (debug only, to avoid leaking timing in production)
        if settings.DEBUG:
            execution_time = (time.time() - request._fx_start_time) * 1000
            response["X-Execution-Time"] = f"{execution_time:.2f}ms"
            if request.is_fx:
                self.observe(request, response)

        # Add Fixi header to response for debugging
        if request.is_fx:
            response["X-FX-Response"] = "true"

        # Unconditional: a *full-page* response from an Fx-aware URL must also
        # declare that it varies, or a shared cache will serve it into a swap
        # target on the next Fixi request.
        return vary_on_fx(response)

    def observe(self, request, response) -> None:
        """Under DEBUG, for a Fixi request: log what fixi would do silently."""
        status = response.status_code
        location = response.get("Location", "")
        slash_fixup = location.split("?", 1)[0] == request.path + "/"
        if 300 <= status < 400 and (slash_fixup or request.method in _METHOD_PRESERVED):
            logger.warning(redirect_note(request.method, request.path, response))

        name = template_name_of(response)
        if name:
            response["X-FX-Template"] = name

        for finding in lint_response(response):
            log = logger.error if finding.level == "error" else logger.warning
            log("%s %s: %s", request.method, request.path, finding)


def template_name_of(response) -> str | None:
    """
    The template a rendered ``TemplateResponse`` came from, as ``file`` or
    ``file#partial`` for a Django 6 template partial. ``None`` for anything else.
    """
    resolve = getattr(response, "resolve_template", None)
    names = getattr(response, "template_name", None)
    if resolve is None or not names or not getattr(response, "is_rendered", True):
        return None
    try:
        template = resolve(names)
    except Exception:
        return None
    inner = getattr(template, "template", template)
    origin = getattr(template, "origin", None) or getattr(inner, "origin", None)
    file = getattr(origin, "template_name", None) or getattr(inner, "name", None)
    part = getattr(inner, "name", None)
    if not file:
        return None
    if part and part != file and "#" not in file:
        return f"{file}#{part}"
    return file
