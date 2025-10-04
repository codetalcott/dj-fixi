"""
LLM tool definitions for Claude/GPT integration.

Defines the function schemas that LLMs can call to generate components.
"""

from typing import Dict, List, Any


def get_tool_definitions() -> List[Dict[str, Any]]:
    """
    Get all tool definitions for LLM integration.

    Compatible with both OpenAI function calling and Anthropic tool use.

    Returns:
        List of tool definition dicts
    """
    return [
        get_table_tool(),
        get_chart_tool(),
        get_form_tool(),
        get_dashboard_tool(),
        get_kpi_tool(),
    ]


def get_table_tool() -> Dict[str, Any]:
    """Tool definition for creating interactive tables."""
    return {
        "name": "create_table",
        "description": (
            "Create an interactive data table with sorting, filtering, and optional editing. "
            "Use this when the user wants to see tabular data, lists, or records. "
            "The table will be sortable, searchable, and can export to CSV/Excel."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "model": {
                    "type": "string",
                    "description": "The Django model to query (e.g., 'products.Product', 'users.User')",
                },
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of model fields to display as columns",
                },
                "filters": {
                    "type": "object",
                    "description": "Django ORM filters to apply (e.g., {'price__gte': 100, 'is_active': True})",
                },
                "editable_fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Fields that can be edited inline (subset of 'fields')",
                },
                "sortable": {
                    "type": "boolean",
                    "description": "Whether columns can be sorted (default: true)",
                },
                "searchable_fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Fields to include in search (default: first 2 fields)",
                },
                "page_size": {
                    "type": "integer",
                    "description": "Number of rows per page (default: 20, max: 100)",
                },
            },
            "required": ["model", "fields"],
        },
    }


def get_chart_tool() -> Dict[str, Any]:
    """Tool definition for creating interactive charts."""
    return {
        "name": "create_chart",
        "description": (
            "Create an interactive chart (line, bar, pie, scatter) to visualize data. "
            "Use this when the user wants to see trends, comparisons, or distributions. "
            "Charts are interactive with tooltips, zoom, and export capabilities."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "model": {
                    "type": "string",
                    "description": "The Django model to query for chart data",
                },
                "chart_type": {
                    "type": "string",
                    "enum": ["line", "bar", "pie", "scatter", "area"],
                    "description": "Type of chart to create",
                },
                "x_field": {
                    "type": "string",
                    "description": "Field for X-axis (labels/categories)",
                },
                "y_field": {
                    "type": "string",
                    "description": "Field for Y-axis (values)",
                },
                "aggregate": {
                    "type": "string",
                    "enum": ["Sum", "Avg", "Count", "Min", "Max"],
                    "description": "Aggregation function for Y values (default: 'Sum')",
                },
                "filters": {
                    "type": "object",
                    "description": "Django ORM filters to apply",
                },
                "group_by": {
                    "type": "string",
                    "description": "Optional field to group data by (creates multiple series)",
                },
            },
            "required": ["model", "chart_type", "x_field", "y_field"],
        },
    }


def get_form_tool() -> Dict[str, Any]:
    """Tool definition for creating interactive forms."""
    return {
        "name": "create_form",
        "description": (
            "Create an interactive form for data entry or editing. "
            "Use this when the user wants to create, update, or collect information. "
            "Forms have real-time validation, auto-save, and helpful error messages."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "model": {
                    "type": "string",
                    "description": "The Django model for this form",
                },
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Model fields to include in the form",
                },
                "field_types": {
                    "type": "object",
                    "description": "Custom field types/widgets (e.g., {'description': 'textarea'})",
                },
                "validators": {
                    "type": "object",
                    "description": "Custom validation rules",
                },
                "initial_data": {
                    "type": "object",
                    "description": "Initial form values",
                },
                "success_message": {
                    "type": "string",
                    "description": "Message to show on successful submission",
                },
            },
            "required": ["model", "fields"],
        },
    }


def get_dashboard_tool() -> Dict[str, Any]:
    """Tool definition for creating multi-widget dashboards."""
    return {
        "name": "create_dashboard",
        "description": (
            "Create a dashboard with multiple widgets (tables, charts, KPIs, etc.). "
            "Use this when the user wants an overview with multiple data visualizations. "
            "Dashboards can have any combination of components in a grid or column layout."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Dashboard title",
                },
                "layout": {
                    "type": "string",
                    "enum": ["grid", "columns", "rows"],
                    "description": "Layout style for widgets (default: 'grid')",
                },
                "widgets": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ["table", "chart", "kpi", "metric"],
                            },
                            "title": {"type": "string"},
                            "config": {"type": "object"},
                            "width": {"type": "string"},  # e.g., "1/2", "1/3", "full"
                        },
                    },
                    "description": "List of widgets to include",
                },
                "refresh_interval": {
                    "type": "integer",
                    "description": "Auto-refresh interval in seconds (0 = no auto-refresh)",
                },
            },
            "required": ["title", "widgets"],
        },
    }


def get_kpi_tool() -> Dict[str, Any]:
    """Tool definition for creating KPI/metric cards."""
    return {
        "name": "create_kpi",
        "description": (
            "Create a KPI (Key Performance Indicator) card showing a single metric. "
            "Use this for important numbers like total sales, active users, conversion rate. "
            "KPIs can show trends (up/down), comparisons, and drill-down details."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "label": {
                    "type": "string",
                    "description": "KPI label (e.g., 'Total Revenue', 'Active Users')",
                },
                "model": {
                    "type": "string",
                    "description": "Django model to query",
                },
                "aggregate": {
                    "type": "string",
                    "enum": ["Count", "Sum", "Avg", "Min", "Max"],
                    "description": "Aggregation function",
                },
                "field": {
                    "type": "string",
                    "description": "Field to aggregate (not needed for Count)",
                },
                "filters": {
                    "type": "object",
                    "description": "Filters to apply",
                },
                "format": {
                    "type": "string",
                    "enum": ["number", "currency", "percentage", "duration"],
                    "description": "How to format the value (default: 'number')",
                },
                "trend": {
                    "type": "object",
                    "description": "Comparison period for trend calculation",
                },
            },
            "required": ["label", "model", "aggregate"],
        },
    }


def format_tool_for_openai(tool: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert tool definition to OpenAI function calling format.

    OpenAI uses 'function' wrapper and 'parameters' instead of 'input_schema'.
    """
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool["description"],
            "parameters": tool["input_schema"],
        },
    }


def format_tool_for_anthropic(tool: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert tool definition to Anthropic Claude format.

    Claude uses the format we already have.
    """
    return tool


def get_system_prompt() -> str:
    """
    Get system prompt for LLM to use these tools.

    This explains to the LLM how to use the component generation tools.
    """
    return """You are a helpful assistant that creates interactive web components instead of text.

When users ask to see data, analyze information, or create interfaces, you should:

1. **Use the available tools** to generate interactive components:
   - `create_table` for tabular data, lists, records
   - `create_chart` for visualizations, trends, comparisons
   - `create_form` for data entry, editing
   - `create_dashboard` for multi-widget overviews
   - `create_kpi` for important metrics

2. **Think about the data model**:
   - What Django models are available?
   - What fields does the user want to see?
   - What filters should be applied?

3. **Choose the right component type**:
   - Want to see a list? → Table
   - Want to see trends? → Chart
   - Want to collect data? → Form
   - Want an overview? → Dashboard
   - Want key metrics? → KPIs

4. **Provide context with your components**:
   - Briefly explain what the component shows
   - Suggest next steps (filter, drill-down, export)
   - Offer to refine or add more components

Example interaction:

User: "Show me sales from last month"

You: I'll create an interactive table of last month's sales data.

[Call create_table with:
 - model: "sales.Sale"
 - fields: ["date", "customer", "product", "amount"]
 - filters: {"date__gte": "2024-09-01", "date__lt": "2024-10-01"}
]

You can sort by any column, filter further, or export to Excel. Would you like me to also add a chart showing daily trends?

IMPORTANT: Always use tools to generate components instead of just describing data in text.
"""


def get_examples() -> List[Dict[str, Any]]:
    """
    Get example interactions for few-shot learning.

    These help the LLM understand how to use the tools.
    """
    return [
        {
            "user": "Show me all products",
            "assistant_thought": "User wants to see tabular data. Use create_table.",
            "tool_call": {
                "name": "create_table",
                "arguments": {
                    "model": "products.Product",
                    "fields": ["name", "price", "stock", "is_active"],
                    "sortable": True,
                    "page_size": 20,
                },
            },
            "assistant_response": "Here's an interactive table of all products. You can sort by clicking column headers, search using the search box, or click on any row for details.",
        },
        {
            "user": "Create a sales dashboard",
            "assistant_thought": "User wants an overview with multiple components. Use create_dashboard.",
            "tool_call": {
                "name": "create_dashboard",
                "arguments": {
                    "title": "Sales Dashboard",
                    "layout": "grid",
                    "widgets": [
                        {
                            "type": "kpi",
                            "title": "Total Revenue",
                            "config": {
                                "model": "sales.Sale",
                                "aggregate": "Sum",
                                "field": "amount",
                                "format": "currency",
                            },
                        },
                        {
                            "type": "chart",
                            "title": "Sales Over Time",
                            "config": {
                                "model": "sales.Sale",
                                "chart_type": "line",
                                "x_field": "date",
                                "y_field": "amount",
                                "aggregate": "Sum",
                            },
                        },
                        {
                            "type": "table",
                            "title": "Recent Sales",
                            "config": {
                                "model": "sales.Sale",
                                "fields": ["date", "customer", "amount"],
                                "page_size": 10,
                            },
                        },
                    ],
                },
            },
            "assistant_response": "I've created a sales dashboard with total revenue, a trend chart, and recent sales table. All widgets update in real-time.",
        },
    ]
