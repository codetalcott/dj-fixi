"""
Django views for LLM agent integration.

Provides endpoints for LLM-generated components.
"""

import json
from typing import Dict, Any
from django.http import JsonResponse, HttpRequest
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .generator import TableGenerator, ChartGenerator, FormGenerator, DashboardGenerator
from .executor import ComponentExecutor


@method_decorator(csrf_exempt, name="dispatch")  # TODO: Use proper auth
class LLMComponentView(View):
    """
    Endpoint for creating components from LLM tool calls.

    LLM calls this with tool arguments, we generate and execute the component.

    POST /llm/component/
    {
        "tool_name": "create_table",
        "arguments": {
            "model": "products.Product",
            "fields": ["name", "price"],
            ...
        },
        "user_id": 123
    }

    Returns:
    {
        "component_id": "comp_abc123",
        "type": "table",
        "data": {...},  # Ready for FixiPlug
        "metadata": {...}
    }
    """

    def post(self, request: HttpRequest) -> JsonResponse:
        """Handle component generation request."""
        try:
            data = json.loads(request.body)

            tool_name = data.get("tool_name")
            arguments = data.get("arguments", {})
            user = request.user if request.user.is_authenticated else None

            # Get user's allowed models (TODO: implement proper permissions)
            allowed_models = self._get_allowed_models(user)

            # Generate component based on tool
            component = self._generate_component(tool_name, arguments, user, allowed_models)

            # Execute component
            executor = ComponentExecutor(user, allowed_models)
            result = executor.execute_component(component, request)

            # Generate unique ID for this component
            import uuid

            component_id = f"comp_{uuid.uuid4().hex[:12]}"

            # Store component for future updates (TODO: implement storage)
            # self._store_component(component_id, component)

            return JsonResponse(
                {
                    "component_id": component_id,
                    "type": result["type"],
                    "data": result["data"],
                    "metadata": result["metadata"],
                    "status": result["status"],
                }
            )

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

    def _get_allowed_models(self, user) -> list[str]:
        """Get models this user can access."""
        # TODO: Implement proper permission checking
        # For demo, allow all models
        from django.apps import apps

        return [f"{model._meta.app_label}.{model._meta.object_name}" for model in apps.get_models()]

    def _generate_component(
        self, tool_name: str, arguments: Dict[str, Any], user, allowed_models: list[str]
    ) -> Dict[str, Any]:
        """Generate component from tool call."""
        generators = {
            "create_table": TableGenerator,
            "create_chart": ChartGenerator,
            "create_form": FormGenerator,
            "create_dashboard": DashboardGenerator,
        }

        generator_class = generators.get(tool_name)
        if not generator_class:
            raise ValueError(f"Unknown tool: {tool_name}")

        generator = generator_class(user, allowed_models)

        # For now, pass arguments as context
        # In production, this would involve actual LLM prompt processing
        return generator.generate(prompt="", context=arguments)


class LLMConversationView(View):
    """
    Endpoint for LLM conversation with component generation.

    This is the main interface for chat-based component creation.

    POST /llm/chat/
    {
        "message": "Show me sales from last month",
        "conversation_id": "conv_123",
        "user_id": 123
    }

    Returns:
    {
        "response": "Here's an interactive table of last month's sales...",
        "components": [
            {
                "component_id": "comp_abc",
                "type": "table",
                "data": {...}
            }
        ],
        "suggestions": ["Add a chart", "Filter by region", "Export to Excel"]
    }
    """

    def post(self, request: HttpRequest) -> JsonResponse:
        """Handle conversation message with component generation."""
        try:
            data = json.loads(request.body)

            message = data.get("message")
            conversation_id = data.get("conversation_id")
            user = request.user if request.user.is_authenticated else None

            # TODO: Integrate with actual LLM API (Claude, GPT, etc.)
            # This is a placeholder for the integration

            # For demo, return a mock response
            response = self._mock_llm_response(message, user, request)

            return JsonResponse(response)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

    def _mock_llm_response(
        self, message: str, user, request: HttpRequest
    ) -> Dict[str, Any]:
        """
        Mock LLM response for demonstration.

        In production, this would:
        1. Send message + tool definitions to LLM API
        2. LLM decides which tools to call
        3. We execute tool calls
        4. Return results to LLM
        5. LLM formats final response
        """
        # Simple keyword detection for demo
        if "table" in message.lower() or "show" in message.lower() or "list" in message.lower():
            # Generate a table component
            generator = TableGenerator(user, self._get_allowed_models(user))

            # Try to infer model from message
            # This is very simplistic - real implementation uses LLM
            model = self._infer_model_from_message(message)

            component = generator.generate(
                prompt=message,
                context={
                    "model": model,
                    "fields": ["id", "name"],  # Simplified
                    "filters": {},
                },
            )

            executor = ComponentExecutor(user, self._get_allowed_models(user))
            result = executor.execute_component(component, request)

            import uuid

            component_id = f"comp_{uuid.uuid4().hex[:12]}"

            return {
                "response": f"Here's an interactive table showing {model} data. You can sort, filter, and export the data.",
                "components": [
                    {
                        "component_id": component_id,
                        "type": result["type"],
                        "data": result["data"],
                        "metadata": result["metadata"],
                    }
                ],
                "suggestions": [
                    "Add a chart",
                    "Filter the data",
                    "Export to Excel",
                    "Make it editable",
                ],
            }

        return {
            "response": "I can help you create interactive components. Try asking me to show you data, create a chart, or build a dashboard!",
            "components": [],
            "suggestions": [
                "Show me all products",
                "Create a sales dashboard",
                "Make a chart of user signups",
            ],
        }

    def _get_allowed_models(self, user) -> list[str]:
        """Get models this user can access."""
        from django.apps import apps

        return [f"{model._meta.app_label}.{model._meta.object_name}" for model in apps.get_models()]

    def _infer_model_from_message(self, message: str) -> str:
        """
        Infer model name from message.

        This is a placeholder - real implementation would use LLM.
        """
        # Very simplistic keyword matching
        keywords = {
            "product": "products.Product",
            "user": "auth.User",
            "order": "orders.Order",
            "sale": "sales.Sale",
        }

        message_lower = message.lower()
        for keyword, model_name in keywords.items():
            if keyword in message_lower:
                return model_name

        # Default fallback
        return "auth.User"


class ComponentRefreshView(View):
    """
    Endpoint to refresh/update an existing component.

    PUT /llm/component/<component_id>/
    {
        "filters": {...},
        "sort": "name",
        "page": 2
    }
    """

    def put(self, request: HttpRequest, component_id: str) -> JsonResponse:
        """Refresh component with new parameters."""
        try:
            # TODO: Retrieve stored component by ID
            # TODO: Apply new parameters
            # TODO: Re-execute and return updated data

            return JsonResponse(
                {"component_id": component_id, "status": "updated", "data": {}}
            )

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)
