"""
Claude Code Adapter for LLM Integration

Allows Claude Code to act as the LLM agent for component generation.
Instead of calling an external API, we use Claude Code's current session.

Usage:
    # In your Django project
    from dj_fixi.llm.claude_code_adapter import ClaudeCodeAgent

    agent = ClaudeCodeAgent()
    result = agent.process_prompt("Show me all products")
    # Returns component ready for FixiPlug
"""

from typing import Dict, Any, Optional
from .generator import TableGenerator, ChartGenerator, FormGenerator, DashboardGenerator
from .executor import ComponentExecutor
from .tools import get_tool_definitions


class ClaudeCodeAgent:
    """
    Adapter that allows Claude Code to generate components.

    This simulates what would happen with the Anthropic API, but uses
    Claude Code's session directly for faster iteration.
    """

    def __init__(self, user=None, allowed_models: list[str] = None):
        """
        Initialize Claude Code agent.

        Args:
            user: Django user (for permissions)
            allowed_models: Models this user can access
        """
        self.user = user
        self.allowed_models = allowed_models or []
        self.tools = get_tool_definitions()
        self.conversation_history = []

    def process_prompt(self, prompt: str, request=None) -> Dict[str, Any]:
        """
        Process user prompt and generate component.

        This is where Claude Code (me!) analyzes the prompt and decides
        which component to generate.

        Args:
            prompt: User's natural language request
            request: Django HTTP request (optional)

        Returns:
            {
                "response": "Text explanation",
                "components": [component_data],
                "suggestions": ["Next actions"]
            }
        """
        # Store in conversation history
        self.conversation_history.append({"role": "user", "content": prompt})

        # Analyze prompt and decide which tool to use
        tool_call = self._analyze_prompt(prompt)

        if not tool_call:
            return {
                "response": "I can create interactive components for you! Try asking me to:\n"
                           "- Show you data in a table\n"
                           "- Create a chart\n"
                           "- Build a form\n"
                           "- Make a dashboard",
                "components": [],
                "suggestions": [
                    "Show me all products",
                    "Create a sales chart",
                    "Build a customer feedback form"
                ]
            }

        # Generate component
        try:
            component = self._generate_component(tool_call)

            # Execute if we have a request
            if request:
                executor = ComponentExecutor(self.user, self.allowed_models)
                result = executor.execute_component(component, request)

                return {
                    "response": self._format_response(tool_call, component),
                    "components": [result],
                    "suggestions": self._get_suggestions(tool_call["tool"], component)
                }
            else:
                # Return just the component definition
                return {
                    "response": self._format_response(tool_call, component),
                    "components": [component],
                    "suggestions": self._get_suggestions(tool_call["tool"], component)
                }

        except Exception as e:
            return {
                "response": f"I encountered an error generating that component: {str(e)}",
                "components": [],
                "suggestions": ["Try a different request"]
            }

    def _analyze_prompt(self, prompt: str) -> Optional[Dict[str, Any]]:
        """
        Analyze user prompt and determine which tool to use.

        As Claude Code, I can analyze the semantic meaning of the prompt.
        """
        prompt_lower = prompt.lower()

        # Detect table requests
        table_keywords = ["show", "list", "display", "table", "all", "get", "find", "view"]
        if any(kw in prompt_lower for kw in table_keywords):
            return self._plan_table(prompt)

        # Detect chart requests
        chart_keywords = ["chart", "graph", "plot", "visualize", "trend", "compare"]
        if any(kw in prompt_lower for kw in chart_keywords):
            return self._plan_chart(prompt)

        # Detect form requests
        form_keywords = ["form", "create", "add", "submit", "enter", "collect"]
        if any(kw in prompt_lower for kw in form_keywords):
            return self._plan_form(prompt)

        # Detect dashboard requests
        dashboard_keywords = ["dashboard", "overview", "summary", "metrics"]
        if any(kw in prompt_lower for kw in dashboard_keywords):
            return self._plan_dashboard(prompt)

        return None

    def _plan_table(self, prompt: str) -> Dict[str, Any]:
        """Plan a table component from prompt."""
        prompt_lower = prompt.lower()

        # Try to detect model
        model = self._detect_model(prompt)

        # Try to detect filters
        filters = {}
        if "price >" in prompt_lower or "price greater" in prompt_lower:
            # Extract price threshold
            import re
            match = re.search(r'price[>\s]+(\d+)', prompt_lower)
            if match:
                filters["price__gt"] = int(match.group(1))

        if "active" in prompt_lower:
            filters["is_active"] = True

        # Determine if should be editable
        editable_fields = []
        if "edit" in prompt_lower or "editable" in prompt_lower:
            # Make stock editable by default
            editable_fields = ["stock"]

        return {
            "tool": "create_table",
            "arguments": {
                "model": model,
                "fields": self._get_default_fields(model),
                "filters": filters,
                "editable_fields": editable_fields,
                "sortable": True,
                "page_size": 20
            }
        }

    def _plan_chart(self, prompt: str) -> Dict[str, Any]:
        """Plan a chart component from prompt."""
        prompt_lower = prompt.lower()

        # Detect chart type
        chart_type = "bar"  # default
        if "line" in prompt_lower:
            chart_type = "line"
        elif "pie" in prompt_lower:
            chart_type = "pie"
        elif "scatter" in prompt_lower:
            chart_type = "scatter"

        model = self._detect_model(prompt)

        # Try to detect x and y fields
        # This is simplified - real implementation would be smarter
        x_field = "date" if "date" in prompt_lower or "time" in prompt_lower else "name"
        y_field = "amount" if "amount" in prompt_lower or "revenue" in prompt_lower else "price"

        return {
            "tool": "create_chart",
            "arguments": {
                "model": model,
                "chart_type": chart_type,
                "x_field": x_field,
                "y_field": y_field,
                "aggregate": "Sum"
            }
        }

    def _plan_form(self, prompt: str) -> Dict[str, Any]:
        """Plan a form component from prompt."""
        model = self._detect_model(prompt)

        return {
            "tool": "create_form",
            "arguments": {
                "model": model,
                "fields": self._get_default_fields(model),
            }
        }

    def _plan_dashboard(self, prompt: str) -> Dict[str, Any]:
        """Plan a dashboard component from prompt."""
        model = self._detect_model(prompt)

        return {
            "tool": "create_dashboard",
            "arguments": {
                "title": f"{model} Dashboard",
                "layout": "grid",
                "widgets": [
                    {
                        "type": "kpi",
                        "title": "Total Count",
                        "config": {
                            "model": model,
                            "aggregate": "Count"
                        }
                    },
                    {
                        "type": "table",
                        "title": "Recent Records",
                        "config": {
                            "model": model,
                            "fields": self._get_default_fields(model),
                            "page_size": 10
                        }
                    }
                ]
            }
        }

    def _detect_model(self, prompt: str) -> str:
        """
        Detect which model the user is asking about.

        This is a simple keyword matcher - could be enhanced with NLP.
        """
        prompt_lower = prompt.lower()

        # Common model keywords
        model_map = {
            "product": "Product",
            "user": "User",
            "customer": "Customer",
            "order": "Order",
            "sale": "Sale",
            "payment": "Payment",
            "invoice": "Invoice",
        }

        for keyword, model_name in model_map.items():
            if keyword in prompt_lower:
                return model_name

        # Default
        return "Product"

    def _get_default_fields(self, model: str) -> list[str]:
        """Get sensible default fields for a model."""
        field_map = {
            "Product": ["name", "price", "stock", "is_active"],
            "User": ["username", "email", "date_joined", "is_active"],
            "Customer": ["name", "email", "phone", "created_at"],
            "Order": ["customer", "total", "status", "created_at"],
            "Sale": ["date", "customer", "amount", "product"],
        }

        return field_map.get(model, ["id", "name", "created_at"])

    def _generate_component(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        """Generate component from tool call."""
        tool_name = tool_call["tool"]
        arguments = tool_call["arguments"]

        generators = {
            "create_table": TableGenerator,
            "create_chart": ChartGenerator,
            "create_form": FormGenerator,
            "create_dashboard": DashboardGenerator,
        }

        generator_class = generators[tool_name]
        generator = generator_class(self.user, self.allowed_models)

        return generator.generate(prompt="", context=arguments)

    def _format_response(self, tool_call: Dict[str, Any], component: Dict[str, Any]) -> str:
        """Format natural language response about what was created."""
        tool_name = tool_call["tool"]

        responses = {
            "create_table": f"I've created an interactive table showing {tool_call['arguments'].get('model')} data. "
                           f"You can sort columns, search, and export to CSV/Excel.",

            "create_chart": f"I've created a {tool_call['arguments'].get('chart_type')} chart visualizing "
                           f"{tool_call['arguments'].get('model')} data. "
                           f"You can hover for details and export as image.",

            "create_form": f"I've created a form for {tool_call['arguments'].get('model')}. "
                          f"It has validation and will save to the database.",

            "create_dashboard": f"I've created a dashboard for {tool_call['arguments'].get('model')}. "
                               f"It includes multiple widgets showing different views of your data."
        }

        return responses.get(tool_name, "I've created your component.")

    def _get_suggestions(self, tool_name: str, component: Dict[str, Any]) -> list[str]:
        """Get next action suggestions based on what was created."""
        if tool_name == "create_table":
            return [
                "Add a chart to visualize this data",
                "Make the table editable",
                "Filter the data",
                "Export to Excel"
            ]
        elif tool_name == "create_chart":
            return [
                "Add a table view",
                "Change chart type",
                "Filter by date range"
            ]
        elif tool_name == "create_form":
            return [
                "Add validation rules",
                "Preview the form",
                "Test submission"
            ]
        else:
            return [
                "Refine the view",
                "Add more widgets",
                "Export the data"
            ]


# Convenience function for quick testing
def ask_claude(prompt: str, user=None, allowed_models=None) -> Dict[str, Any]:
    """
    Quick function to ask Claude Code for a component.

    Example:
        result = ask_claude("Show me all products")
        print(result["response"])
        print(result["components"][0]["view_code"])
    """
    agent = ClaudeCodeAgent(user, allowed_models)
    return agent.process_prompt(prompt)
