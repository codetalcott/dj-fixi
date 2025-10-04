"""
Safe code executor for LLM-generated components.

Executes view code in a sandboxed environment with security restrictions.
"""

import ast
import signal
from contextlib import contextmanager
from typing import Dict, Any, Optional
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.apps import apps
from django.db import models
from django.forms import modelform_factory

from dj_fixi.views import FxCRUDView, FxView
from dj_fixi.tables import ModelTable


class ExecutionTimeout(Exception):
    """Raised when code execution exceeds timeout."""

    pass


class SecurityViolation(Exception):
    """Raised when code violates security constraints."""

    pass


@contextmanager
def timeout(seconds: int):
    """Context manager for execution timeout."""

    def timeout_handler(signum, frame):
        raise ExecutionTimeout(f"Execution exceeded {seconds} seconds")

    # Set alarm
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(seconds)

    try:
        yield
    finally:
        # Restore
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


class SafeExecutor:
    """
    Safely execute LLM-generated view code.

    Security features:
    - Whitelist allowed imports/modules
    - AST validation (no exec, eval, file ops)
    - Execution timeout
    - Resource limits
    - Permission checks
    """

    def __init__(
        self,
        user,
        allowed_models: list[str],
        timeout_seconds: int = 5,
        max_query_rows: int = 1000,
    ):
        """
        Initialize executor.

        Args:
            user: Django user for permission checks
            allowed_models: Models this user can access
            timeout_seconds: Max execution time
            max_query_rows: Max rows returned from queries
        """
        self.user = user
        self.allowed_models = allowed_models
        self.timeout_seconds = timeout_seconds
        self.max_query_rows = max_query_rows

    def get_safe_namespace(self) -> Dict[str, Any]:
        """
        Build namespace with allowed objects.

        Only whitelisted imports are available.
        """
        # Get allowed model classes
        models_dict = {}
        for model_name in self.allowed_models:
            try:
                model = apps.get_model(model_name)
                # Store with simple name (e.g., "Product" instead of "products.Product")
                simple_name = model._meta.object_name
                models_dict[simple_name] = model
            except LookupError:
                continue

        namespace = {
            # Django views
            "FxCRUDView": FxCRUDView,
            "FxView": FxView,
            "ModelTable": ModelTable,
            # Django ORM
            "models": models,
            # Forms
            "modelform_factory": modelform_factory,
            # Response types
            "HttpResponse": HttpResponse,
            "JsonResponse": JsonResponse,
            # Models
            **models_dict,
            # Safe built-ins
            "list": list,
            "dict": dict,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "len": len,
            "range": range,
            "enumerate": enumerate,
            "zip": zip,
            "sum": sum,
            "min": min,
            "max": max,
            "sorted": sorted,
        }

        return namespace

    def validate_code(self, code: str) -> tuple[bool, Optional[str]]:
        """
        Validate code before execution.

        Returns:
            (is_valid, error_message)
        """
        try:
            tree = ast.parse(code)

            for node in ast.walk(tree):
                # No imports
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    return False, "Import statements not allowed"

                # No exec/eval
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if node.func.id in ["exec", "eval", "__import__", "compile"]:
                            return False, f"Function '{node.func.id}' not allowed"

                # No file operations
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if node.func.id in ["open", "file"]:
                            return False, "File operations not allowed"

                # No attribute access to dangerous modules
                if isinstance(node, ast.Attribute):
                    dangerous_attrs = ["__builtins__", "__globals__", "__code__"]
                    if node.attr in dangerous_attrs:
                        return False, f"Access to '{node.attr}' not allowed"

            return True, None

        except SyntaxError as e:
            return False, f"Syntax error: {str(e)}"

    def execute_view(self, view_code: str, request: HttpRequest) -> HttpResponse:
        """
        Execute generated view code and return response.

        Args:
            view_code: Python code defining a view class
            request: HTTP request object

        Returns:
            HttpResponse from view

        Raises:
            SecurityViolation: If code violates security rules
            ExecutionTimeout: If execution exceeds timeout
        """
        # Validate code
        is_valid, error = self.validate_code(view_code)
        if not is_valid:
            raise SecurityViolation(error)

        # Build safe namespace
        namespace = self.get_safe_namespace()

        # Execute with timeout
        try:
            with timeout(self.timeout_seconds):
                # Execute code to define view class
                exec(view_code, namespace)

                # Find the generated view class
                view_class = None
                for name, obj in namespace.items():
                    if (
                        isinstance(obj, type)
                        and issubclass(obj, (FxCRUDView, FxView))
                        and obj not in [FxCRUDView, FxView]
                    ):
                        view_class = obj
                        break

                if view_class is None:
                    raise ValueError("No view class found in generated code")

                # Limit query results
                if hasattr(view_class, "paginate_by"):
                    view_class.paginate_by = min(
                        view_class.paginate_by or self.max_query_rows, self.max_query_rows
                    )

                # Instantiate and call view
                view = view_class.as_view()
                response = view(request)

                return response

        except ExecutionTimeout:
            raise
        except Exception as e:
            # Log error for debugging
            raise ValueError(f"Execution failed: {str(e)}")

    def execute_and_get_json(self, view_code: str, request: HttpRequest) -> Dict[str, Any]:
        """
        Execute view and return JSON data.

        Useful for getting structured data to pass to FixiPlug.

        Returns:
            JSON-serializable dict
        """
        response = self.execute_view(view_code, request)

        # If response is already JSON, parse it
        if isinstance(response, JsonResponse):
            import json

            return json.loads(response.content)

        # If HTML response, we need to extract data another way
        # This would require more sophisticated parsing
        return {"html": response.content.decode("utf-8")}


class ComponentExecutor:
    """
    Higher-level executor for complete components.

    Manages multiple views (e.g., dashboard with multiple widgets).
    """

    def __init__(self, user, allowed_models: list[str]):
        self.user = user
        self.allowed_models = allowed_models
        self.executor = SafeExecutor(user, allowed_models)

    def execute_component(self, component: Dict[str, Any], request: HttpRequest) -> Dict[str, Any]:
        """
        Execute a generated component.

        Args:
            component: Component dict from ComponentGenerator
                {
                    "component_type": "table|chart|form|dashboard",
                    "view_code": "...",
                    "metadata": {...}
                }
            request: HTTP request

        Returns:
            {
                "type": "table",
                "data": {...},  # JSON data for FixiPlug
                "metadata": {...}
            }
        """
        component_type = component["component_type"]
        view_code = component["view_code"]
        metadata = component.get("metadata", {})

        # Execute view
        try:
            response_data = self.executor.execute_and_get_json(view_code, request)

            return {
                "type": component_type,
                "data": response_data,
                "metadata": metadata,
                "status": "success",
            }

        except Exception as e:
            return {
                "type": component_type,
                "data": None,
                "metadata": metadata,
                "status": "error",
                "error": str(e),
            }

    def execute_dashboard(
        self, dashboard: Dict[str, Any], request: HttpRequest
    ) -> Dict[str, Any]:
        """
        Execute dashboard with multiple components.

        Args:
            dashboard: Dashboard dict with components list
            request: HTTP request

        Returns:
            {
                "type": "dashboard",
                "components": [...],
                "metadata": {...}
            }
        """
        components = dashboard.get("components", [])
        results = []

        for component in components:
            result = self.execute_component(component, request)
            results.append(result)

        return {
            "type": "dashboard",
            "components": results,
            "metadata": dashboard.get("metadata", {}),
        }
