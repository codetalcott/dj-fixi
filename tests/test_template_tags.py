"""Tests for template tags"""

import pytest
from django.template import Context, Template
from django.test import RequestFactory


@pytest.fixture
def rf():
    return RequestFactory()


def test_fx_attrs_basic():
    """Test basic fx_attrs generation"""
    template = Template("{% load fixi_tags %}{% fx_attrs action='/test' %}")
    rendered = template.render(Context({}))

    assert 'fx-action="/test"' in rendered


def test_fx_attrs_with_method():
    """Test fx_attrs with method"""
    template = Template("{% load fixi_tags %}{% fx_attrs action='/test' method='POST' %}")
    rendered = template.render(Context({}))

    assert 'fx-action="/test"' in rendered
    assert 'fx-method="POST"' in rendered


def test_fx_attrs_with_target():
    """Test fx_attrs with target"""
    template = Template("{% load fixi_tags %}{% fx_attrs action='/test' target='#content' %}")
    rendered = template.render(Context({}))

    assert 'fx-target="#content"' in rendered


def test_fx_attrs_with_swap():
    """A non-default swap strategy is rendered as an attribute."""
    template = Template("{% load fixi_tags %}{% fx_attrs action='/test' swap='beforeend' %}")
    rendered = template.render(Context({}))

    assert 'fx-swap="beforeend"' in rendered


def test_fx_attrs_omits_defaults():
    """fx_attrs omits Fixi's own defaults (GET, click, outerHTML swap)."""
    template = Template(
        "{% load fixi_tags %}{% fx_attrs action='/test' method='GET' swap='outerHTML' trigger='click' %}"
    )
    rendered = template.render(Context({}))

    # Should only have action since the rest match Fixi's defaults.
    assert 'fx-action="/test"' in rendered
    assert "fx-method" not in rendered
    assert "fx-swap" not in rendered
    assert "fx-trigger" not in rendered


def test_fx_attrs_emits_innerhtml_swap():
    """Regression: innerHTML is NOT Fixi's default (outerHTML is), so an explicit
    swap='innerHTML' must be emitted rather than silently dropped."""
    template = Template("{% load fixi_tags %}{% fx_attrs action='/test' swap='innerHTML' %}")
    rendered = template.render(Context({}))

    assert 'fx-swap="innerHTML"' in rendered


def test_fx_attrs_omits_swap_when_absent():
    """No swap arg -> no fx-swap attribute (Fixi applies its outerHTML default)."""
    template = Template("{% load fixi_tags %}{% fx_attrs action='/test' %}")
    rendered = template.render(Context({}))

    assert "fx-swap" not in rendered


def test_fx_csrf_token(rf):
    """Test CSRF token generation"""
    request = rf.get("/")
    template = Template("{% load fixi_tags %}{% fx_csrf_token %}")
    rendered = template.render(Context({"request": request}))

    assert 'name="csrfmiddlewaretoken"' in rendered
    assert 'type="hidden"' in rendered


def test_fixi_js_emits_static_script():
    """{% fixi_js %} serves the vendored copy from this package's static files."""
    template = Template("{% load fixi_tags %}{% fixi_js %}")
    rendered = template.render(Context({}))

    assert "<script" in rendered
    assert "dj_fixi/fixi.js" in rendered


def test_fixi_events_emits_static_script():
    """{% fixi_events %} serves the optional FX-Trigger event bridge."""
    template = Template("{% load fixi_tags %}{% fixi_events %}")
    rendered = template.render(Context({}))

    assert "dj_fixi/fixi-events.js" in rendered


def test_fixi_cdn_points_at_real_package():
    """The deprecated CDN tag now points at the real the-fixi-project package."""
    template = Template("{% load fixi_tags %}{% fixi_cdn %}")
    rendered = template.render(Context({}))

    assert "<script" in rendered
    assert "the-fixi-project" in rendered
