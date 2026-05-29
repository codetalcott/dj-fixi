"""
Testing utilities for Fixi integration.

Provides FxTestClient, a Django test client with helpers for issuing
Fixi (FX-Request) requests.
"""

import json

from django.test import Client


class FxTestClient(Client):
    """Test client with Fixi request helpers."""

    def fx_get(self, url, **kwargs):
        """GET request with FX headers."""
        return self.get(url, HTTP_FX_REQUEST="true", HTTP_ACCEPT="application/json", **kwargs)

    def fx_post(self, url, data=None, **kwargs):
        """POST request with FX headers."""
        if data is not None and not isinstance(data, str):
            data = json.dumps(data)
            kwargs.setdefault("content_type", "application/json")

        return self.post(url, data=data, HTTP_FX_REQUEST="true", **kwargs)

    def fx_patch(self, url, data, **kwargs):
        """PATCH request with FX headers."""
        return self.patch(
            url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_FX_REQUEST="true",
            **kwargs,
        )

    def fx_delete(self, url, data=None, **kwargs):
        """DELETE request with FX headers."""
        if data is not None:
            data = json.dumps(data)
            kwargs.setdefault("content_type", "application/json")

        return self.delete(url, data=data, HTTP_FX_REQUEST="true", **kwargs)
