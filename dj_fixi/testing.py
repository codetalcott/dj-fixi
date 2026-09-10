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


def fixi_check_messages(*, include_warnings: bool = True) -> list:
    """
    dj-fixi's system-check messages for the current settings.

    Django runs system checks on ``runserver``, ``migrate``, and inside its own
    test runner -- but **not** under pytest, which is what most Django projects
    use. So the checks that make dj-fixi's misconfigurations loud are invisible
    in the one workflow where a wrong answer is cheapest to catch. Call this (or
    ``assert_no_fixi_check_issues``) from your suite to close that gap.

    Honors ``SILENCED_SYSTEM_CHECKS``. Pass ``include_warnings=False`` to keep
    only the errors.
    """
    from django.conf import settings
    from django.core.checks import ERROR, run_checks

    silenced = set(getattr(settings, "SILENCED_SYSTEM_CHECKS", []))
    messages = [m for m in run_checks(tags=["dj_fixi"]) if m.id not in silenced]
    if not include_warnings:
        messages = [m for m in messages if m.is_serious(ERROR)]
    return messages


def assert_no_fixi_check_issues(*, include_warnings: bool = True) -> None:
    """
    Fail with the full check output if dj-fixi has anything to report.

    Drop this into your test suite in one line::

        from dj_fixi.testing import assert_no_fixi_check_issues

        def test_dj_fixi_is_configured_correctly():
            assert_no_fixi_check_issues()

    The failure text carries each message and its hint verbatim, because the hint
    is the part that says what to actually change.
    """
    messages = fixi_check_messages(include_warnings=include_warnings)
    if not messages:
        return

    lines = [f"dj-fixi reported {len(messages)} system check issue(s):", ""]
    for message in messages:
        where = f"{message.obj}: " if message.obj is not None else ""
        lines.append(f"({message.id}) {where}{message.msg}")
        if message.hint:
            lines.append(f"    HINT: {message.hint}")
        lines.append("")
    lines.append(
        "Silence any of these with SILENCED_SYSTEM_CHECKS in settings if they "
        "do not apply to your project."
    )
    raise AssertionError("\n".join(lines))
