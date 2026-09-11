"""
Testing utilities for Fixi integration.

``FxTestClient`` is a Django test client that behaves the way an agent needs
the browser to behave: every ``text/html`` response it receives is linted for
what fixi.js would silently ignore (see :mod:`dj_fixi.lint`), and a redirect
answered to a Fixi request is an error unless the test says what it wants,
because fixi's fetch follows redirects and the browser never sees them.

Fixi.js submits with the browser's FormData (form-encoded / multipart), never
JSON, and routes GET/DELETE parameters into the query string. The ``fx_*``
helpers default to form-encoded bodies to mirror real Fixi requests. Pass
``json=...`` only when your endpoint genuinely consumes a JSON body.
"""

from __future__ import annotations

import json as _json
import warnings
from urllib.parse import urlencode

from django.test import Client

from .lint import FxLintError, FxLintWarning, lint_response
from .request import redirect_note

__all__ = [
    "FxTestClient",
    "FxRedirectError",
    "FxLintError",
    "FxLintWarning",
    "fixi_check_messages",
    "assert_no_fixi_check_issues",
]


class FxRedirectError(AssertionError):
    """A redirect answered a Fixi request and the test did not say what it wanted."""


class FxTestClient(Client):
    """
    Test client with Fixi request helpers (form-encoded, ``FX-Request: true``).

    Every ``text/html`` response, from the ``fx_*`` helpers and from plain
    ``get()``/``post()`` alike, is linted; an error-level finding raises
    :class:`FxLintError` and a warning-level one is issued as
    :class:`FxLintWarning`. Findings are also attached as ``response.fx_findings``.
    Switch it off with ``lint=False``, or silence ids with ``lint_ignore=("dj_fixi.L110",)``;
    ``SILENCED_SYSTEM_CHECKS`` silences them too.

    The ``fx_*`` helpers take Django's ``follow`` argument with a third state.
    By default (``follow=None``) a 3xx raises :class:`FxRedirectError`, because a
    Fixi control never sees a redirect: pass ``follow=True`` to get what the
    browser would swap in, or ``follow=False`` to assert on the redirect itself.
    """

    def __init__(self, *args, lint: bool = True, lint_ignore=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.lint = lint
        self.lint_ignore = tuple(lint_ignore)

    def request(self, **request):
        response = super().request(**request)
        if self.lint:
            findings = lint_response(response, ignore=self.lint_ignore)
            response.fx_findings = findings
            errors = [f for f in findings if f.level == "error"]
            if errors:
                where = f"{request.get('REQUEST_METHOD', 'GET')} {request.get('PATH_INFO', '')}"
                raise FxLintError(errors, where)
            for finding in findings:
                if finding.level == "warning":
                    warnings.warn(str(finding), FxLintWarning, stacklevel=3)
        return response

    # ---------------------------------------------------------------- helpers

    def _fx(self, send, url, follow, kwargs):
        response = send(url, follow=bool(follow), HTTP_FX_REQUEST="true", **kwargs)
        if follow is None and 300 <= response.status_code < 400:
            method = kwargs.get("_method") or send.__name__.upper()
            raise FxRedirectError(
                redirect_note(method, url.split("?", 1)[0], response)
                + " Pass follow=True to get what the browser would swap in, or follow=False "
                "to assert on the redirect itself."
            )
        return response

    def fx_get(self, url, data=None, *, follow=None, **kwargs):
        """GET request with the FX-Request header (``data`` -> query string)."""
        return self._fx(self.get, url, follow, {"data": data, **kwargs})

    def fx_post(self, url, data=None, *, json=None, follow=None, **kwargs):
        """POST with the FX-Request header. ``data`` is form-encoded like Fixi's
        FormData; pass ``json=`` to send a JSON body instead."""
        if json is not None:
            data = _json.dumps(json)
            kwargs.setdefault("content_type", "application/json")
        return self._fx(self.post, url, follow, {"data": data, **kwargs})

    def fx_put(self, url, data=None, *, json=None, follow=None, **kwargs):
        """PUT with the FX-Request header (form-encoded body by default)."""
        return self._fx(self.put, url, follow, self._body(data, json, kwargs))

    def fx_patch(self, url, data=None, *, json=None, follow=None, **kwargs):
        """PATCH with the FX-Request header (form-encoded body by default)."""
        return self._fx(self.patch, url, follow, self._body(data, json, kwargs))

    def fx_delete(self, url, data=None, *, json=None, follow=None, **kwargs):
        """DELETE with the FX-Request header. Fixi sends DELETE parameters in the
        query string, so pass them via ``url``; ``json=`` is available if needed."""
        if json is not None:
            data = _json.dumps(json)
            kwargs.setdefault("content_type", "application/json")
        return self._fx(self.delete, url, follow, {"data": data, **kwargs})

    @staticmethod
    def _body(data, json, kwargs):
        if json is not None:
            return {"data": _json.dumps(json), "content_type": "application/json", **kwargs}
        if isinstance(data, dict):
            data = urlencode(data)
        return {"data": data or "", "content_type": "application/x-www-form-urlencoded", **kwargs}


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
