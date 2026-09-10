"""
Tests for dj_fixi.urlconf -- the URLconf walk the system checks are built on.

This module is public API that dj-fixi-tables will import, so it gets the most
coverage. The load-bearing guarantee is that it never raises: a broken URLconf
yields fewer results, and Django's own urls.E00x reports the real problem.
"""

from django.test import override_settings

from dj_fixi.urlconf import RoutedView, iter_routed_views, routed_view_classes
from dj_fixi.views import FxView

from .urlconfs import views as fixture_views


def names(urlconf):
    return [r.url_name for r in iter_routed_views(urlconf)]


class TestWalk:
    def test_finds_every_route(self):
        assert names("tests.urlconfs.good") == [
            "good-list",
            "good-create",
            "good-stack",
            "good-template",
            "good-fbv",
        ]

    def test_empty_urlconf(self):
        assert list(iter_routed_views("tests.urlconfs.empty")) == []

    def test_resolves_view_class_for_cbvs(self):
        routed = next(iter_routed_views("tests.urlconfs.good"))
        assert routed.view_class is fixture_views.GoodList

    def test_function_views_have_no_view_class(self):
        """This is what makes render_fx-only projects invisible to every check."""
        fbvs = [r for r in iter_routed_views("tests.urlconfs.fbv_only")]
        assert len(fbvs) == 2
        assert all(r.view_class is None for r in fbvs)
        assert all(r.initkwargs == {} for r in fbvs)


class TestNesting:
    def test_descends_into_includes(self):
        assert "deep" in names("tests.urlconfs.nested")

    def test_joins_namespaces(self):
        routed = {r.url_name: r for r in iter_routed_views("tests.urlconfs.nested")}
        assert routed["deep"].namespace == "shop"
        assert routed["deep"].full_name == "shop:deep"

    def test_unnamespaced_include_has_empty_namespace(self):
        routed = {r.url_name: r for r in iter_routed_views("tests.urlconfs.nested")}
        assert routed["good-list"].namespace == ""
        assert routed["good-list"].full_name == "good-list"

    def test_builds_the_full_route(self):
        routed = {r.url_name: r for r in iter_routed_views("tests.urlconfs.nested")}
        assert routed["deep"].route == "shop/deep/"


class TestDecoratorsAndInitkwargs:
    def test_login_required_preserves_the_view_class(self):
        """functools.wraps copies __dict__, where as_view() stores these."""
        routed = {r.url_name: r for r in iter_routed_views("tests.urlconfs.nested")}
        assert routed["deep"].view_class is fixture_views.GoodList

    def test_initkwargs_are_captured(self):
        routed = {r.url_name: r for r in iter_routed_views("tests.urlconfs.nested")}
        assert routed["configured"].initkwargs["template_name"] == "good/at_urlconf.html"

    def test_attr_prefers_initkwargs_over_the_class(self):
        """Reading view_class.template_name alone would report the wrong name."""
        routed = {r.url_name: r for r in iter_routed_views("tests.urlconfs.nested")}
        assert routed["configured"].attr("template_name") == "good/at_urlconf.html"
        assert fixture_views.GoodTemplate.template_name != "good/at_urlconf.html"

    def test_attr_falls_back_to_the_class_then_the_default(self):
        routed = next(iter_routed_views("tests.urlconfs.good"))
        assert routed.attr("partial_template") == fixture_views.PARTIAL
        assert routed.attr("nonexistent", "fallback") == "fallback"


class TestNeverRaises:
    def test_broken_include_yields_nothing_instead_of_raising(self):
        assert list(iter_routed_views("tests.urlconfs.broken")) == []

    def test_missing_urlconf_module_yields_nothing(self):
        assert list(iter_routed_views("tests.urlconfs.no_such_module")) == []

    def test_max_depth_is_bounded(self):
        assert list(iter_routed_views("tests.urlconfs.nested", max_depth=0)) != []


class TestRoutedViewClasses:
    def test_filters_by_base_class(self):
        found = routed_view_classes(FxView, "tests.urlconfs.good")
        assert fixture_views.GoodList in found
        assert fixture_views.GoodCreate not in found  # FxResponseMixin, not FxView

    def test_deduplicates_a_class_routed_more_than_once(self):
        """One class routed at several paths must not produce several findings."""
        found = routed_view_classes(FxView, "tests.urlconfs.nested")
        assert list(found).count(fixture_views.GoodList) == 1

    def test_returns_the_first_route_for_each_class(self):
        found = routed_view_classes(FxView, "tests.urlconfs.nested")
        assert found[fixture_views.GoodList].route == "top/"

    def test_accepts_a_tuple_of_bases(self):
        from dj_fixi.mixins import FxResponseMixin

        found = routed_view_classes((FxView, FxResponseMixin), "tests.urlconfs.good")
        assert fixture_views.GoodCreate in found

    def test_empty_for_an_fbv_only_project(self):
        assert routed_view_classes(FxView, "tests.urlconfs.fbv_only") == {}


class TestDefaultUrlconf:
    @override_settings(ROOT_URLCONF="tests.urlconfs.good")
    def test_defaults_to_root_urlconf(self):
        assert "good-list" in [r.url_name for r in iter_routed_views()]

    def test_returns_routed_view_instances(self):
        assert all(isinstance(r, RoutedView) for r in iter_routed_views("tests.urlconfs.good"))
