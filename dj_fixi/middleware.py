"""
Middleware for detecting Fixi requests and setting up request attributes.

Adapted from django_hypermedia.middleware.negotiation
"""


class FxMiddleware:
    """
    Detects Fixi.js requests and adds fixi-related attributes to request object.

    Sets request.is_fx (bool) and request.fx_info (dict) for use in views.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Detect Fixi request
        request.is_fx = request.headers.get("FX-Request") == "true"

        # Extract Fixi headers
        request.fx_target = request.headers.get("FX-Target")
        request.fx_swap = request.headers.get("FX-Swap", "innerHTML")
        request.fx_trigger = request.headers.get("FX-Trigger")

        # Process request
        response = self.get_response(request)

        # Add Fixi header to response for debugging
        if request.is_fx:
            response["X-FX-Response"] = "true"

        return response
