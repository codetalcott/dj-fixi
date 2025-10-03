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
        request.is_fx = self._is_fixi_request(request)
        request.fx_info = self._get_fx_info(request)

        # Process request
        response = self.get_response(request)

        # Add Fixi header to response for debugging
        if request.is_fx:
            response["X-FX-Response"] = "true"

        return response

    def _is_fixi_request(self, request):
        """Check if this is a Fixi.js request"""
        return request.headers.get("FX-Request") == "true"

    def _get_fx_info(self, request):
        """
        Extract Fixi-related information from request headers.

        Returns dict with:
            - is_fx: Boolean flag
            - target: Target selector from FX-Target header
            - swap: Swap strategy from FX-Swap header
            - trigger: Triggering element from FX-Trigger header
        """
        if not self._is_fixi_request(request):
            return {
                "is_fx": False,
                "target": None,
                "swap": None,
                "trigger": None,
            }

        return {
            "is_fx": True,
            "target": request.headers.get("FX-Target"),
            "swap": request.headers.get("FX-Swap", "innerHTML"),
            "trigger": request.headers.get("FX-Trigger"),
        }
