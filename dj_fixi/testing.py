"""
Testing utilities for Fixi and MCP integration.

Provides test clients and helpers for testing Fixi views with MCP compatibility.
"""

import json
from django.test import Client


class FxTestClient(Client):
    """Test client with Fixi and MCP support."""

    def fx_get(self, url, **kwargs):
        """GET request with FX headers."""
        return self.get(
            url,
            HTTP_FX_REQUEST='true',
            HTTP_ACCEPT='application/json',
            **kwargs
        )

    def fx_post(self, url, data=None, **kwargs):
        """POST request with FX headers."""
        if data is not None and not isinstance(data, str):
            data = json.dumps(data)
            kwargs.setdefault('content_type', 'application/json')

        return self.post(
            url,
            data=data,
            HTTP_FX_REQUEST='true',
            **kwargs
        )

    def fx_patch(self, url, data, **kwargs):
        """PATCH request with FX headers."""
        return self.patch(
            url,
            data=json.dumps(data),
            content_type='application/json',
            HTTP_FX_REQUEST='true',
            **kwargs
        )

    def fx_delete(self, url, data=None, **kwargs):
        """DELETE request with FX headers."""
        if data is not None:
            data = json.dumps(data)
            kwargs.setdefault('content_type', 'application/json')

        return self.delete(
            url,
            data=data,
            HTTP_FX_REQUEST='true',
            **kwargs
        )

    def mcp_get(self, url, session_id='test-session', **kwargs):
        """GET request with MCP headers."""
        return self.get(
            url,
            HTTP_X_MCP_SESSION=session_id,
            HTTP_ACCEPT='application/json',
            **kwargs
        )

    def mcp_post(self, url, data=None, session_id='test-session', **kwargs):
        """POST request with MCP headers."""
        if data is not None and not isinstance(data, str):
            data = json.dumps(data)
            kwargs.setdefault('content_type', 'application/json')

        return self.post(
            url,
            data=data,
            HTTP_X_MCP_SESSION=session_id,
            HTTP_ACCEPT='application/json',
            **kwargs
        )

    def mcp_patch(self, url, data, session_id='test-session', **kwargs):
        """PATCH request with MCP headers."""
        return self.patch(
            url,
            data=json.dumps(data),
            content_type='application/json',
            HTTP_X_MCP_SESSION=session_id,
            **kwargs
        )

    def mcp_delete(self, url, data=None, session_id='test-session', **kwargs):
        """DELETE request with MCP headers."""
        if data is not None:
            data = json.dumps(data)
            kwargs.setdefault('content_type', 'application/json')

        return self.delete(
            url,
            data=data,
            HTTP_X_MCP_SESSION=session_id,
            **kwargs
        )


def assert_mcp_response(response, success=True):
    """
    Assert response follows MCP format.

    Args:
        response: Django test response
        success: Expected success value (default: True)

    Returns:
        dict: Response JSON data

    Raises:
        AssertionError: If response doesn't match MCP format
    """
    assert response.status_code in (200, 201, 400, 403, 404, 422, 500), \
        f"Unexpected status code: {response.status_code}"

    data = response.json()

    # Check required fields
    assert 'success' in data, "Response missing 'success' field"
    assert 'meta' in data, "Response missing 'meta' field"

    # Check success value
    assert data['success'] == success, \
        f"Expected success={success}, got {data['success']}"

    if success:
        # Success response should have data
        assert 'data' in data, "Success response missing 'data' field"
    else:
        # Error response should have error
        assert 'error' in data, "Error response missing 'error' field"

    # Check meta fields
    assert 'timestamp' in data['meta'], "Meta missing 'timestamp' field"

    return data


def assert_validation_error(response, expected_errors=None):
    """
    Assert response is a validation error.

    Args:
        response: Django test response
        expected_errors: Optional list of expected error messages

    Returns:
        dict: Response JSON data
    """
    data = assert_mcp_response(response, success=False)

    assert response.status_code in (400, 422), \
        f"Expected validation error status, got {response.status_code}"

    assert data.get('error_code') == 'VALIDATION_ERROR', \
        f"Expected VALIDATION_ERROR code, got {data.get('error_code')}"

    if expected_errors:
        error_text = data['error']
        for expected in expected_errors:
            assert expected in error_text, \
                f"Expected error '{expected}' not found in '{error_text}'"

    return data
