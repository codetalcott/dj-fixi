"""
Tests for the pytest-facing check helper.

Django runs system checks on runserver, migrate, and in its own test runner, but
pytest-django does not run them at all -- verified by grepping the installed
package for any reference to the check framework. So for the majority of Django
projects the checks are invisible during testing, which is the workflow where a
wrong answer is cheapest to catch. These helpers close that gap.
"""

import pytest
from django.test import override_settings

from dj_fixi.testing import assert_no_fixi_check_issues, fixi_check_messages

from .checks_support import TEMPLATES


def test_clean_project_reports_nothing():
    with override_settings(ROOT_URLCONF="tests.urlconfs.good", TEMPLATES=TEMPLATES):
        assert fixi_check_messages() == []
        assert_no_fixi_check_issues()  # must not raise


def test_failure_lists_every_message_and_hint():
    with override_settings(ROOT_URLCONF="tests.urlconfs.bad_mro", TEMPLATES=TEMPLATES):
        with pytest.raises(AssertionError) as exc:
            assert_no_fixi_check_issues()
    text = str(exc.value)
    assert "dj_fixi.E101" in text
    assert "HINT:" in text
    assert "Reorder the bases" in text  # the actionable part must survive


def test_silenced_checks_are_honored():
    """A project that silenced a check must not fail on it here."""
    with override_settings(ROOT_URLCONF="tests.urlconfs.bad_mro", TEMPLATES=TEMPLATES):
        before = {m.id for m in fixi_check_messages()}
        with override_settings(SILENCED_SYSTEM_CHECKS=["dj_fixi.E101"]):
            after = {m.id for m in fixi_check_messages()}
    assert "dj_fixi.E101" in before
    assert "dj_fixi.E101" not in after


def test_warnings_can_be_excluded():
    with override_settings(
        ROOT_URLCONF="tests.urlconfs.templates",
        TEMPLATES=TEMPLATES,
        MIDDLEWARE=["django.middleware.common.CommonMiddleware"],
    ):
        assert {m.id for m in fixi_check_messages()} >= {"dj_fixi.W001", "dj_fixi.W201"}
        assert fixi_check_messages(include_warnings=False) == []


def test_errors_survive_the_warning_filter():
    with override_settings(ROOT_URLCONF="tests.urlconfs.bad_mro", TEMPLATES=TEMPLATES):
        assert {m.id for m in fixi_check_messages(include_warnings=False)} == {"dj_fixi.E101"}
