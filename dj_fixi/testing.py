"""
Testing utilities for Fixi integration.

Provides FxTestClient, a Django test client with helpers for issuing
Fixi (FX-Request) requests.

Fixi.js submits with the browser's FormData (form-encoded / multipart), never
JSON, and routes GET/DELETE parameters into the query string. These helpers
default to form-encoded bodies to mirror real Fixi requests. Pass ``json=...``
only when your endpoint genuinely consumes a JSON body.
"""

import json as _json
from urllib.parse import urlencode

from django.test import Client


class FxTestClient(Client):
    """Test client with Fixi request helpers (form-encoded, ``FX-Request: true``)."""

    def fx_get(self, url, data=None, **kwargs):
        """GET request with the FX-Request header (``data`` -> query string)."""
        return self.get(url, data=data, HTTP_FX_REQUEST="true", **kwargs)

    def fx_post(self, url, data=None, *, json=None, **kwargs):
        """POST with the FX-Request header. ``data`` is form-encoded like Fixi's
        FormData; pass ``json=`` to send a JSON body instead."""
        if json is not None:
            data = _json.dumps(json)
            kwargs.setdefault("content_type", "application/json")
        return self.post(url, data=data, HTTP_FX_REQUEST="true", **kwargs)

    def fx_patch(self, url, data=None, *, json=None, **kwargs):
        """PATCH with the FX-Request header (form-encoded body by default)."""
        if json is not None:
            return self.patch(
                url,
                data=_json.dumps(json),
                content_type="application/json",
                HTTP_FX_REQUEST="true",
                **kwargs,
            )
        if isinstance(data, dict):
            data = urlencode(data)
        return self.patch(
            url,
            data=data or "",
            content_type="application/x-www-form-urlencoded",
            HTTP_FX_REQUEST="true",
            **kwargs,
        )

    def fx_delete(self, url, data=None, *, json=None, **kwargs):
        """DELETE with the FX-Request header. Fixi sends DELETE parameters in the
        query string, so pass them via ``url``; ``json=`` is available if needed."""
        if json is not None:
            data = _json.dumps(json)
            kwargs.setdefault("content_type", "application/json")
        return self.delete(url, data=data, HTTP_FX_REQUEST="true", **kwargs)
