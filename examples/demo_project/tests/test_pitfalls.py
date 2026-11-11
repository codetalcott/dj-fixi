"""
Every pitfall, held to what the page says about it, without a browser.

The browser half (the naive version really fails, the fixed one really works)
is in test_pitfalls_browser.py. This half pins the server-side claims: what
the lint reports for each naive snippet, that every fixed snippet is clean, and
what FxTestClient says about the two responses it can judge.
"""

import pytest
from django.test import Client
from django.urls import reverse
from pitfalls.catalog import PITFALLS
from pitfalls.models import Note
from pitfalls.views import render_snippet, snippet_context

from dj_fixi.lint import lint_html
from dj_fixi.testing import FxRedirectError, FxTestClient

pytestmark = pytest.mark.django_db


def rendered(pitfall, side, rf):
    request = rf.get(reverse("pitfalls:index"))
    return render_snippet(getattr(pitfall, side), request, snippet_context(request, "t0ken"))


@pytest.mark.parametrize("pitfall", PITFALLS, ids=lambda p: p.slug)
def test_the_lint_reports_exactly_what_the_catalog_claims(pitfall, rf):
    findings = lint_html(rendered(pitfall, "naive", rf), full_document=False)
    assert tuple(sorted({f.id for f in findings})) == pitfall.lint


@pytest.mark.parametrize("pitfall", PITFALLS, ids=lambda p: p.slug)
def test_every_fixed_snippet_is_clean(pitfall, rf):
    assert lint_html(rendered(pitfall, "fixed", rf), full_document=False) == []


def test_the_page_renders_every_pitfall_and_its_live_findings():
    html = Client().get(reverse("pitfalls:index")).content.decode()
    for pitfall in PITFALLS:
        assert f'id="{pitfall.slug}-naive"' in html and f'id="{pitfall.slug}-fixed"' in html
        for finding_id in pitfall.lint:
            assert f"<code>{finding_id}</code>" in html


def test_full_page_into_a_fragment_target_is_reported():
    naive = FxTestClient().fx_get(reverse("pitfalls:details_page_only"))
    assert [f.id for f in naive.fx_findings] == ["dj_fixi.L111"]
    fixed = FxTestClient().fx_get(reverse("pitfalls:details"))
    assert fixed.fx_findings == [] and b"<h1>" not in fixed.content
    assert "FX-Request" in fixed["Vary"]
    assert b"<h1>" in Client().get(reverse("pitfalls:details")).content  # same URL, the page


def test_a_redirect_answering_a_fixi_post_is_refused_by_the_test_client():
    fx = FxTestClient()
    with pytest.raises(FxRedirectError, match="swaps the redirect target"):
        fx.fx_post(reverse("pitfalls:note_naive"), {"text": "hello"})

    response = fx.fx_post(reverse("pitfalls:note_fixed"), {"text": "hello again"})
    assert response.status_code == 200 and "formSuccess" in response["FX-Trigger"]
    assert 'class="note-form"' in response.content.decode()
    html = response.content.decode()
    assert 'value="hello again"' not in html  # the form is blank after a create
    assert "<li>hello again</li>" in html and "<li>hello</li>" in html  # and the list has both
    assert Note.objects.count() == 2

    invalid = fx.fx_post(reverse("pitfalls:note_fixed"), {"text": ""})
    assert invalid.status_code == 422 and "formError" in invalid["FX-Trigger"]


def test_csrf_is_enforced_on_the_save_endpoint():
    client = Client(enforce_csrf_checks=True)
    assert client.post(reverse("pitfalls:save"), HTTP_FX_REQUEST="true").status_code == 403
