"""
Middleware for detecting Fixi requests and setting up request attributes.

Adapted from django_hypermedia.middleware.negotiation
"""

import time


class FxMiddleware:
    """
    Detects Fixi.js requests and adds fixi-related attributes to request object.

    Enhanced with timing and MCP support.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Add timing
        request._fx_start_time = time.time()

        # Detect Fixi request
        request.is_fx = request.headers.get("FX-Request") == "true"

        # Extract Fixi headers
        request.fx_target = request.headers.get("FX-Target")
        request.fx_swap = request.headers.get("FX-Swap", "innerHTML")
        request.fx_trigger = request.headers.get("FX-Trigger")

        # Add MCP context
        if request.headers.get('X-MCP-Session'):
            request.mcp_session = request.headers['X-MCP-Session']
            request.is_mcp = True
        else:
            request.is_mcp = False

        # Process request
        response = self.get_response(request)

        # Add execution time
        if hasattr(request, '_fx_start_time'):
            execution_time = (time.time() - request._fx_start_time) * 1000
            response['X-Execution-Time'] = f"{execution_time:.2f}ms"

        # Add Fixi header to response for debugging
        if request.is_fx:
            response["X-FX-Response"] = "true"

        # Add MCP headers
        if hasattr(request, 'is_mcp') and request.is_mcp:
            response['X-MCP-Compatible'] = 'true'

        return response
