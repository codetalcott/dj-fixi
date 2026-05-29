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
    """Test fx_attrs with swap strategy"""
    template = Template("{% load fixi_tags %}{% fx_attrs action='/test' swap='outerHTML' %}")
    rendered = template.render(Context({}))

    assert 'fx-swap="outerHTML"' in rendered


def test_fx_attrs_omits_defaults():
    """Test that fx_attrs omits default values"""
    template = Template(
        "{% load fixi_tags %}{% fx_attrs action='/test' method='GET' swap='innerHTML' trigger='click' %}"
    )
    rendered = template.render(Context({}))

    # Should only have action since others are defaults
    assert 'fx-action="/test"' in rendered
    assert "fx-method" not in rendered
    assert "fx-swap" not in rendered
    assert "fx-trigger" not in rendered


def test_fx_csrf_token(rf):
    """Test CSRF token generation"""
    request = rf.get("/")
    template = Template("{% load fixi_tags %}{% fx_csrf_token %}")
    rendered = template.render(Context({"request": request}))

    assert 'name="csrfmiddlewaretoken"' in rendered
    assert 'type="hidden"' in rendered


def test_fixi_cdn():
    """Test Fixi CDN script tag generation"""
    template = Template("{% load fixi_tags %}{% fixi_cdn %}")
    rendered = template.render(Context({}))

    assert "<script" in rendered
    assert "fixi" in rendered.lower()
