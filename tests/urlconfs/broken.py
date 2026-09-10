from django.urls import include, path

urlpatterns = [path("boom/", include("tests.urlconfs.does_not_exist"))]
