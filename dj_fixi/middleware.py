"""
Middleware for detecting Fixi requests and setting up request attributes.

Adapted from django_hypermedia.middleware.negotiation
"""

import time

from django.conf import settings

from .request import FX_REQUEST_HEADER, vary_on_fx


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

        # Add Fixi header to response for debugging
        if request.is_fx:
            response["X-FX-Response"] = "true"

        # Unconditional: a *full-page* response from an Fx-aware URL must also
        # declare that it varies, or a shared cache will serve it into a swap
        # target on the next Fixi request.
        return vary_on_fx(response)
