"""
Tests for LLM agent integration.
"""

import pytest
from dj_fixi.llm.generator import TableGenerator, ChartGenerator, ComponentGenerator
from dj_fixi.llm.executor import SafeExecutor


class TestComponentGenerator:
    """Test base ComponentGenerator class."""

    def test_validate_safe_code(self):
        """Safe code passes validation."""
        generator = ComponentGenerator()

        code = """
class TestView(FxCRUDView):
    model = Product
    fields = ['name', 'price']
"""

        is_valid, error = generator.validate_generated_code(code)
        assert is_valid is True
        assert error is None

    def test_validate_rejects_imports(self):
        """Code with imports is rejected."""
        generator = ComponentGenerator()

        code = """
import os
class TestView(FxCRUDView):
    model = Product
"""

        is_valid, error = generator.validate_generated_code(code)
        assert is_valid is False
        assert "Import" in error

    def test_validate_rejects_exec(self):
        """Code with exec/eval is rejected."""
        generator = ComponentGenerator()

        code = """
class TestView(FxCRUDView):
    def get_queryset(self):
        exec("print('bad')")
"""

        is_valid, error = generator.validate_generated_code(code)
        assert is_valid is False
        assert "exec" in error.lower()

    def test_validate_rejects_file_ops(self):
        """Code with file operations is rejected."""
        generator = ComponentGenerator()

        code = """
class TestView(FxCRUDView):
    def get_queryset(self):
        open('/etc/passwd')
"""

        is_valid, error = generator.validate_generated_code(code)
        assert is_valid is False
        assert "File" in error


class TestTableGenerator:
    """Test TableGenerator."""

    def test_generate_basic_table(self):
        """Generate basic table component."""
        generator = TableGenerator(allowed_models=["products.Product"])

        component = generator.generate(
            prompt="Show me products",
            context={
                "model": "Product",
                "fields": ["name", "price"],
                "filters": {},
                "editable_fields": [],
            },
        )

        assert component["component_type"] == "table"
        assert "view_code" in component
        assert "metadata" in component
        assert "class GeneratedView(FxCRUDView)" in component["view_code"]

    def test_generate_table_with_filters(self):
        """Generate table with filters."""
        generator = TableGenerator()

        component = generator.generate(
            prompt="Show me expensive products",
            context={
                "model": "Product",
                "fields": ["name", "price"],
                "filters": {"price__gt": 100},
                "editable_fields": [],
            },
        )

        assert "price__gt" in component["view_code"]

    def test_generate_editable_table(self):
        """Generate table with editable fields."""
        generator = TableGenerator()

        component = generator.generate(
            prompt="Show me products",
            context={
                "model": "Product",
                "fields": ["name", "price", "stock"],
                "filters": {},
                "editable_fields": ["stock"],
            },
        )

        assert component["metadata"]["editable"] is True
        assert "stock" in component["metadata"]["editable_fields"]


class TestChartGenerator:
    """Test ChartGenerator."""

    def test_generate_bar_chart(self):
        """Generate bar chart component."""
        generator = ChartGenerator()

        component = generator.generate(
            prompt="Show sales by region",
            context={
                "model": "Sale",
                "chart_type": "bar",
                "x_field": "region",
                "y_field": "amount",
                "aggregate": "Sum",
            },
        )

        assert component["component_type"] == "chart"
        assert "bar" in component["view_code"]
        assert "region" in component["view_code"]
        assert "Sum" in component["view_code"]


class TestSafeExecutor:
    """Test SafeExecutor."""

    def test_validate_safe_code(self):
        """Safe code passes validation."""
        executor = SafeExecutor(user=None, allowed_models=["products.Product"])

        code = """
class GeneratedView(FxCRUDView):
    model = Product
    fields = ['name']
"""

        is_valid, error = executor.validate_code(code)
        assert is_valid is True

    def test_validate_rejects_dangerous_code(self):
        """Dangerous code is rejected."""
        executor = SafeExecutor(user=None, allowed_models=[])

        dangerous_codes = [
            "import os",
            "exec('print(1)')",
            "eval('1+1')",
            "__import__('os')",
            "open('/etc/passwd')",
        ]

        for code in dangerous_codes:
            is_valid, error = executor.validate_code(f"class V: {code}")
            assert is_valid is False, f"Should reject: {code}"

    def test_safe_namespace_has_required_objects(self):
        """Safe namespace includes required classes."""
        executor = SafeExecutor(user=None, allowed_models=["products.Product"])

        namespace = executor.get_safe_namespace()

        assert "FxCRUDView" in namespace
        assert "FxView" in namespace
        assert "models" in namespace
        assert "JsonResponse" in namespace

    def test_safe_namespace_excludes_dangerous_modules(self):
        """Safe namespace excludes dangerous modules."""
        executor = SafeExecutor(user=None, allowed_models=[])

        namespace = executor.get_safe_namespace()

        assert "os" not in namespace
        assert "sys" not in namespace
        assert "subprocess" not in namespace
        assert "__import__" not in namespace


class TestIntegration:
    """Integration tests for complete flow."""

    def test_generate_and_validate(self):
        """Generated code passes validation."""
        # Generate component
        generator = TableGenerator(allowed_models=["products.Product"])
        component = generator.generate(
            prompt="Show products",
            context={
                "model": "Product",
                "fields": ["name", "price"],
                "filters": {},
                "editable_fields": [],
            },
        )

        # Validate with executor
        executor = SafeExecutor(user=None, allowed_models=["products.Product"])
        is_valid, error = executor.validate_code(component["view_code"])

        assert is_valid is True, f"Generated code should be valid: {error}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
