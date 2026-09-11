"""Routes for exercising FxTestClient: the lint wiring and the redirect states."""

from django.http import HttpResponse, HttpResponseRedirect, JsonResponse, StreamingHttpResponse
from django.shortcuts import render
from django.urls import path

from dj_fixi.shortcuts import render_fx


def clean_page(request):
    return render(request, "client/page.html")


def htmx_page(request):
    return render(request, "client/htmx.html")


def fragment(request):
    return render_fx(request, "client/fragment.html", "client/page.html")


def bad_swap(request):
    return HttpResponse('<a fx-action="/client/frag/" fx-swap="outerhtml">x</a>')


def typo(request):
    return HttpResponse('<a fx-action="/client/frag/" fx-targt="#r">x</a>')


def goes_away(request):
    return HttpResponseRedirect("/client/page/")


def needs_slash(request):
    return HttpResponse("ok")


def as_json(request):
    return JsonResponse({"hx-get": "not html, not linted"})


def no_content(request):
    return HttpResponse(status=204)


def streamed(request):
    return StreamingHttpResponse([b'<a fx-action="/x/" fx-swap="outerhtml">'], content_type="text/html")


def echo(request):
    body = request.POST.get("a") or request.GET.get("a") or ""
    return HttpResponse(f"{request.method} fx={request.headers.get('FX-Request')} ct={request.content_type} a={body}")


urlpatterns = [
    path("client/page/", clean_page, name="client-page"),
    path("client/htmx/", htmx_page, name="client-htmx"),
    path("client/frag/", fragment, name="client-frag"),
    path("client/bad-swap/", bad_swap),
    path("client/typo/", typo),
    path("client/goes-away/", goes_away),
    path("client/needs-slash/", needs_slash),
    path("client/json/", as_json),
    path("client/204/", no_content),
    path("client/stream/", streamed),
    path("client/echo/", echo),
]
