from django.contrib.auth.decorators import login_required
from django.urls import path

from . import views

app_name = "inner"

urlpatterns = [
    path("deep/", login_required(views.GoodList.as_view()), name="deep"),
    path(
        "configured/",
        views.GoodTemplate.as_view(template_name="good/at_urlconf.html"),
        name="configured",
    ),
]
