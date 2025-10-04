"""
Demo: LLM Agent Integration with dj-fixi + FixiPlug

This demonstrates the complete flow:
1. User sends natural language prompt
2. LLM generates component via tools
3. Django executes safely
4. FixiPlug renders interactive UI

Run this demo:
    python examples/demo_llm_integration.py
"""

import json
from django.test import RequestFactory
from dj_fixi.llm.generator import TableGenerator, ChartGenerator
from dj_fixi.llm.executor import SafeExecutor, ComponentExecutor
from dj_fixi.llm.tools import get_tool_definitions, get_system_prompt


def demo_1_table_generation():
    """Demo 1: Generate an interactive table from natural language."""
    print("=" * 60)
    print("DEMO 1: Table Generation")
    print("=" * 60)

    # User prompt
    user_prompt = "Show me all products with price > 100, sorted by name"
    print(f"\nUser: {user_prompt}")

    # LLM would parse this and call create_table tool with these arguments
    tool_arguments = {
        "model": "products.Product",
        "fields": ["name", "price", "stock", "is_active"],
        "filters": {"price__gt": 100},
        "sortable": True,
        "editable_fields": ["stock"],
        "page_size": 20,
    }

    print(f"\nLLM calls create_table with: {json.dumps(tool_arguments, indent=2)}")

    # Generate component
    generator = TableGenerator(user=None, allowed_models=["products.Product"])
    component = generator.generate(prompt=user_prompt, context=tool_arguments)

    print(f"\nGenerated view code:\n{component['view_code']}")
    print(f"\nMetadata: {json.dumps(component['metadata'], indent=2)}")

    # Execute (in real app, this would be executed by SafeExecutor)
    print("\nExecutor would run this code safely and return JSON for FixiPlug")
    print("FixiPlug would render an interactive, sortable, editable table")


def demo_2_chart_generation():
    """Demo 2: Generate an interactive chart."""
    print("\n" + "=" * 60)
    print("DEMO 2: Chart Generation")
    print("=" * 60)

    user_prompt = "Show me sales by region as a bar chart"
    print(f"\nUser: {user_prompt}")

    tool_arguments = {
        "model": "sales.Sale",
        "chart_type": "bar",
        "x_field": "region",
        "y_field": "amount",
        "aggregate": "Sum",
    }

    print(f"\nLLM calls create_chart with: {json.dumps(tool_arguments, indent=2)}")

    generator = ChartGenerator(user=None, allowed_models=["sales.Sale"])
    component = generator.generate(prompt=user_prompt, context=tool_arguments)

    print(f"\nGenerated view code:\n{component['view_code']}")
    print("\nFixiPlug would render an interactive bar chart")


def demo_3_code_validation():
    """Demo 3: Code validation and security."""
    print("\n" + "=" * 60)
    print("DEMO 3: Code Validation & Security")
    print("=" * 60)

    executor = SafeExecutor(user=None, allowed_models=["products.Product"])

    # Safe code
    safe_code = """
class GeneratedView(FxCRUDView):
    model = Product
    fields = ['name', 'price']
"""

    is_valid, error = executor.validate_code(safe_code)
    print(f"\nSafe code validation: {is_valid}")

    # Unsafe code - import
    unsafe_code_1 = """
import os
class GeneratedView(FxCRUDView):
    model = Product
"""

    is_valid, error = executor.validate_code(unsafe_code_1)
    print(f"\nUnsafe code (import): {is_valid}, Error: {error}")

    # Unsafe code - exec
    unsafe_code_2 = """
class GeneratedView(FxCRUDView):
    def get_queryset(self):
        exec("print('hacked')")
        return Product.objects.all()
"""

    is_valid, error = executor.validate_code(unsafe_code_2)
    print(f"Unsafe code (exec): {is_valid}, Error: {error}")


def demo_4_tool_definitions():
    """Demo 4: Tool definitions for LLM."""
    print("\n" + "=" * 60)
    print("DEMO 4: LLM Tool Definitions")
    print("=" * 60)

    tools = get_tool_definitions()

    print(f"\nAvailable tools: {len(tools)}")
    for tool in tools:
        print(f"\n  - {tool['name']}: {tool['description'][:80]}...")

    # Show detailed schema for create_table
    table_tool = tools[0]
    print(f"\nDetailed schema for '{table_tool['name']}':")
    print(json.dumps(table_tool["input_schema"], indent=2))


def demo_5_system_prompt():
    """Demo 5: System prompt for LLM."""
    print("\n" + "=" * 60)
    print("DEMO 5: System Prompt")
    print("=" * 60)

    system_prompt = get_system_prompt()
    print(f"\nSystem prompt for LLM:\n{system_prompt[:500]}...")


def demo_6_complete_flow():
    """Demo 6: Complete end-to-end flow."""
    print("\n" + "=" * 60)
    print("DEMO 6: Complete Flow (Simulated)")
    print("=" * 60)

    print("""
User: "Show me sales from last month"

Step 1: LLM receives prompt + tool definitions
Step 2: LLM decides to call 'create_table' tool
Step 3: LLM generates tool arguments:
        {
          "model": "sales.Sale",
          "fields": ["date", "customer", "amount"],
          "filters": {"date__gte": "2024-09-01", "date__lt": "2024-10-01"}
        }

Step 4: Django receives tool call
Step 5: TableGenerator creates view code
Step 6: SafeExecutor validates and runs code
Step 7: Django returns JSON:
        {
          "type": "table",
          "data": [{...}, {...}],
          "columns": [{...}, {...}],
          "pagination": {...}
        }

Step 8: FixiPlug receives JSON
Step 9: django-integration.js detects Django table format
Step 10: table.js plugin renders interactive table
Step 11: User sees sortable, filterable, exportable table

Step 12: User clicks "Add a chart"
Step 13: LLM adds chart component using same data
Step 14: Both components update together
""")


def main():
    """Run all demos."""
    print("\n" + "🚀" * 30)
    print("dj-fixi + FixiPlug + LLM Integration Demo")
    print("🚀" * 30)

    demo_1_table_generation()
    demo_2_chart_generation()
    demo_3_code_validation()
    demo_4_tool_definitions()
    demo_5_system_prompt()
    demo_6_complete_flow()

    print("\n" + "=" * 60)
    print("✅ All demos completed!")
    print("=" * 60)
    print("""
Next steps:
1. Integrate with real LLM API (Claude, GPT-4, etc.)
2. Add component storage and state management
3. Build FixiPlug table plugin (Phase 1 + 1.5 from plan)
4. Create demo web interface
5. Add authentication and permissions
""")


if __name__ == "__main__":
    # This demo doesn't need Django setup
    # It's just showing the code generation flow
    main()
