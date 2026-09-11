"""
Fixi request detection, and the response header that must accompany it.

Fixi.js sends exactly one custom request header, ``FX-Request: true``. Detection
reads that header directly, so it works whether or not :class:`FxMiddleware` is
installed. This is deliberate: a ``getattr(request, "is_fx", False)`` default
turns a forgotten middleware entry into a silent, permanent "not a Fixi request",
which serves a full HTML page into every swap target without raising anything.
"""

from django.utils.cache import patch_vary_headers

FX_REQUEST_HEADER = "FX-Request"

__all__ = ["FX_REQUEST_HEADER", "is_fx", "vary_on_fx", "redirect_note"]


def is_fx(request) -> bool:
    """
    Return True when ``request`` is a Fixi request.

    Honors ``request.is_fx`` when something set it (``FxMiddleware``, a test, or
    user code deliberately forcing a full-page render), and otherwise falls back
    to reading the ``FX-Request`` header off the request itself.
    """
    flag = getattr(request, "is_fx", None)
    if flag is not None:
        return bool(flag)
    return request.headers.get(FX_REQUEST_HEADER) == "true"


def vary_on_fx(response):
    """
    Add ``FX-Request`` to the response's ``Vary`` header.

    Any URL that returns a fragment or a full page depending on ``FX-Request``
    must say so, or a shared cache will serve one audience the other's response.
    Returns the response for convenient chaining.
    """
    patch_vary_headers(response, (FX_REQUEST_HEADER,))
    return response


def redirect_note(method: str, path: str, response) -> str:
    """
    One sentence on what fixi will do with a redirect answered to a Fixi request.

    fetch() follows redirects on its own and fixi never sees them: the redirect
    target's response is what gets swapped into the control's target. A 301 or
    302 also turns a POST into a GET; a 303 turns every method into GET; a
    DELETE survives a 301/302 and reaches the target as a DELETE. When the
    redirect is Django's ``APPEND_SLASH`` fix-up, the note says so, because the
    fix is one character in ``fx-action``.
    """
    status = response.status_code
    location = response.get("Location", "")
    note = (
        f"{method} {path} answered a Fixi request with a {status} to {location!r}. fixi's fetch "
        "follows redirects silently, so the browser swaps the redirect target's response into "
        "the control's target"
    )
    if status in (301, 302) and method == "POST":
        note += ", and a 301/302 turns the POST into a GET"
    note += "."
    if location.split("?", 1)[0] == path + "/":
        note += " This is CommonMiddleware's APPEND_SLASH: the fx-action is missing its trailing slash."
    return note
