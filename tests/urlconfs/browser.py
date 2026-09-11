"""A page and two fragments for driving the shim through a real browser."""

import json

from django.http import HttpResponse
from django.shortcuts import render
from django.urls import path


def page(request):
    return render(request, "browser/page.html")


def fragment(request):
    response = HttpResponse("NEW")
    response["FX-Trigger"] = json.dumps({"ping": {"x": 1}})
    return response


def fragment_targeted(request):
    response = HttpResponse("NEWER")
    response["FX-Trigger"] = json.dumps({"ping": {"target": "#out", "x": 2}})
    return response


urlpatterns = [
    path("b/page/", page),
    path("b/frag/", fragment),
    path("b/frag-target/", fragment_targeted),
]
