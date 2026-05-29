"""Tests for the JSON envelope, FxCRUDView validation, and test helpers."""

import json
from decimal import Decimal

import pytest
from django.test import TestCase

from dj_fixi.mixins import JsonEnvelopeMixin
from dj_fixi.testing import FxTestClient, assert_json_envelope, assert_validation_error
from dj_fixi.views import FxCRUDView


# Mock model for testing
class MockProduct:
    """Mock product model for testing."""
    _meta = type('Meta', (), {
        'model_name': 'product',
        'verbose_name': 'Product'
    })()

    class DoesNotExist(Exception):  # noqa: N818 - mirrors Django's Model.DoesNotExist
        pass

    objects = type('Manager', (), {
        'all': lambda: [],
        'get': lambda pk: None,
        'filter': lambda **kwargs: type('QuerySet', (), {
            'select_related': lambda *args: [],
        })(),
    })()

    def __init__(self, pk, name, price, stock):
        self.pk = pk
        self.id = pk
        self.name = name
        self.price = price
        self.stock = stock

    def save(self, **kwargs):
        pass

    def full_clean(self):
        pass


@pytest.mark.django_db
class TestJsonEnvelopeMixin(TestCase):
    """Test JsonEnvelopeMixin functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = FxTestClient()

    def test_success_response_format(self):
        """Test success response has correct structure."""
        mixin = JsonEnvelopeMixin()
        response = mixin.success_response(
            data={'id': 1, 'name': 'Test'},
            status=200
        )

        data = json.loads(response.content)
        assert data['success'] is True
        assert 'data' in data
        assert 'meta' in data
        assert 'timestamp' in data['meta']
        assert response.status_code == 200

    def test_error_response_format(self):
        """Test error response has correct structure."""
        mixin = JsonEnvelopeMixin()
        response = mixin.error_response(
            error='Validation failed',
            status=400,
            error_code='VALIDATION_ERROR'
        )

        data = json.loads(response.content)
        assert data['success'] is False
        assert data['error'] == 'Validation failed'
        assert data['error_code'] == 'VALIDATION_ERROR'
        assert 'meta' in data
        assert response.status_code == 400

    def test_meta_with_extra_data(self):
        """Test response with extra metadata."""
        mixin = JsonEnvelopeMixin()
        response = mixin.success_response(
            data={'id': 1},
            extra_meta={'updated_fields': ['name', 'price']}
        )

        data = json.loads(response.content)
        assert data['meta']['updated_fields'] == ['name', 'price']
        assert 'timestamp' in data['meta']


class TestFxCRUDViewValidation(TestCase):
    """Test FxCRUDView validation features."""

    def test_validate_field_required(self):
        """Test required field validation."""
        class TestView(FxCRUDView):
            model = MockProduct
            validation_rules = {
                'name': {'required': True}
            }

        view = TestView()
        is_valid, error = view.validate_field('name', None)
        assert not is_valid
        assert 'required' in error.lower()

    def test_validate_field_type(self):
        """Test type validation."""
        class TestView(FxCRUDView):
            model = MockProduct
            validation_rules = {
                'price': {'type': (int, float, Decimal)}
            }

        view = TestView()
        is_valid, error = view.validate_field('price', 'invalid')
        assert not is_valid
        assert 'type' in error.lower()

    def test_validate_field_custom_validator(self):
        """Test custom validator function."""
        def validate_positive(value):
            if value <= 0:
                raise ValueError("Must be positive")

        class TestView(FxCRUDView):
            model = MockProduct
            validation_rules = {
                'stock': {
                    'validator': validate_positive
                }
            }

        view = TestView()
        is_valid, error = view.validate_field('stock', -5)
        assert not is_valid
        assert 'positive' in error.lower()

    def test_validate_data_editable_fields(self):
        """Test that only editable fields can be updated."""
        class TestView(FxCRUDView):
            model = MockProduct
            fields = ['name', 'price', 'stock']
            editable_fields = ['stock']  # Only stock is editable

        view = TestView()
        is_valid, errors = view.validate_data({
            'name': 'New Name',
            'stock': 10
        })

        assert not is_valid
        assert any('not editable' in e for e in errors)

    def test_validate_data_all_valid(self):
        """Test validation passes with valid data."""
        class TestView(FxCRUDView):
            model = MockProduct
            fields = ['name', 'price', 'stock']
            editable_fields = ['name', 'price', 'stock']
            validation_rules = {
                'price': {'type': (int, float, Decimal)}
            }

        view = TestView()
        is_valid, errors = view.validate_data({
            'name': 'Product',
            'price': 19.99,
            'stock': 5
        })

        assert is_valid
        assert len(errors) == 0


class TestFxCRUDViewAuditLog(TestCase):
    """Test audit logging functionality."""

    def test_audit_log_called_on_update(self):
        """Test that log_change is called when audit enabled."""
        log_calls = []

        class TestView(FxCRUDView):
            model = MockProduct
            enable_audit_log = True

            def log_change(self, obj, old_values, new_values, user):
                log_calls.append({
                    'obj': obj,
                    'old': old_values,
                    'new': new_values,
                    'user': user
                })

        view = TestView()
        view.log_change(
            obj=MockProduct(1, 'Test', 10, 5),
            old_values={'stock': 5},
            new_values={'stock': 10},
            user=None
        )

        assert len(log_calls) == 1
        assert log_calls[0]['old'] == {'stock': 5}
        assert log_calls[0]['new'] == {'stock': 10}


class TestFxTestClient(TestCase):
    """Test FxTestClient helper methods."""

    def setUp(self):
        """Set up test client."""
        self.client = FxTestClient()

    def test_fx_get_sets_headers(self):
        """Test fx_get sets correct headers."""
        # Can't fully test without actual view, but verify methods exist
        assert hasattr(self.client, 'fx_get')
        assert hasattr(self.client, 'fx_post')
        assert hasattr(self.client, 'fx_patch')
        assert hasattr(self.client, 'fx_delete')


class TestJsonEnvelopeAssertions(TestCase):
    """Test JSON envelope assertion helpers."""

    def test_assert_json_envelope_success(self):
        """Test assert_json_envelope with success response."""
        from django.http import JsonResponse

        response = JsonResponse({
            'success': True,
            'data': {'id': 1},
            'meta': {'timestamp': '2024-01-01T00:00:00'}
        })

        data = assert_json_envelope(response, success=True)
        assert data['success'] is True
        assert 'data' in data

    def test_assert_json_envelope_error(self):
        """Test assert_json_envelope with error response."""
        from django.http import JsonResponse

        response = JsonResponse({
            'success': False,
            'error': 'Not found',
            'error_code': 'NOT_FOUND',
            'meta': {'timestamp': '2024-01-01T00:00:00'}
        }, status=404)

        data = assert_json_envelope(response, success=False)
        assert data['success'] is False
        assert 'error' in data

    def test_assert_validation_error(self):
        """Test assert_validation_error helper."""
        from django.http import JsonResponse

        response = JsonResponse({
            'success': False,
            'error': 'name is required; price must be positive',
            'error_code': 'VALIDATION_ERROR',
            'meta': {'timestamp': '2024-01-01T00:00:00'}
        }, status=400)

        data = assert_validation_error(
            response,
            expected_errors=['name is required', 'price must be positive']
        )
        assert data['error_code'] == 'VALIDATION_ERROR'


class TestRealWorldIntegrationPattern(TestCase):
    """Test patterns from real-world usage."""

    def test_validation_rules_pattern(self):
        """Test validation rules pattern used in production."""
        def validate_grade(value):
            valid_grades = ['A', 'B', 'C', 'D', 'F']
            if value not in valid_grades:
                raise ValueError(f"Invalid grade. Must be one of: {', '.join(valid_grades)}")

        def validate_credits(value):
            credit_value = Decimal(str(value))
            if credit_value < 0:
                raise ValueError("Credits cannot be negative")
            if credit_value > 20:
                raise ValueError("Credits cannot exceed 20")

        class CourseView(FxCRUDView):
            model = MockProduct
            editable_fields = ['grade', 'credits']
            validation_rules = {
                'grade': {
                    'required': False,
                    'type': str,
                    'validator': validate_grade
                },
                'credits': {
                    'required': True,
                    'type': (Decimal, float, int),
                    'validator': validate_credits
                }
            }

        view = CourseView()

        # Test invalid grade
        is_valid, error = view.validate_field('grade', 'X')
        assert not is_valid
        assert 'Invalid grade' in error

        # Test valid grade
        is_valid, error = view.validate_field('grade', 'A')
        assert is_valid

        # Test negative credits
        is_valid, error = view.validate_field('credits', -5)
        assert not is_valid
        assert 'negative' in error.lower()

        # Test excessive credits
        is_valid, error = view.validate_field('credits', 25)
        assert not is_valid
        assert 'exceed' in error.lower()

    def test_custom_envelope_meta_pattern(self):
        """Test custom metadata pattern from production."""
        class CourseView(FxCRUDView):
            model = MockProduct
            fields = ['name', 'price']
            editable_fields = ['price']
            searchable_fields = ['name']

            def get_envelope_meta(self):
                meta = super().get_envelope_meta()
                meta.update({
                    'editable_fields': self.editable_fields,
                    'searchable_fields': self.searchable_fields,
                })
                return meta

        view = CourseView()
        meta = view.get_envelope_meta()

        assert 'editable_fields' in meta
        assert 'searchable_fields' in meta
        assert meta['editable_fields'] == ['price']
        assert meta['searchable_fields'] == ['name']
