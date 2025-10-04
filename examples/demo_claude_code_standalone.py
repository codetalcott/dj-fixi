"""
Standalone Demo: Claude Code as LLM Agent

This demo shows Claude Code generating components WITHOUT needing Django installed.
It just shows the generated code, not actual execution.

Run this:
    python examples/demo_claude_code_standalone.py
"""


def print_section(title):
    """Print a section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def demo_claude_code_capabilities():
    """Show what Claude Code can do as an LLM agent."""
    print_section("Claude Code as LLM Agent")

    print("""
As Claude Code, I can analyze natural language prompts and generate
Django view code for interactive components!

Here's what I understand when you ask for components:
""")

    examples = [
        {
            "prompt": "Show me all products",
            "analysis": {
                "intent": "Display tabular data",
                "model": "Product",
                "component": "Table",
                "features": ["sortable", "searchable", "exportable"]
            },
            "code": """class GeneratedView(FxCRUDView):
    model = Product
    fields = ['name', 'price', 'stock', 'is_active']
    editable_fields = []
    searchable_fields = ['name', 'price']
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()
        # No filters
        return queryset"""
        },
        {
            "prompt": "Show me products with price > 100",
            "analysis": {
                "intent": "Display filtered tabular data",
                "model": "Product",
                "component": "Table",
                "filters": {"price__gt": 100}
            },
            "code": """class GeneratedView(FxCRUDView):
    model = Product
    fields = ['name', 'price', 'stock', 'is_active']
    editable_fields = []
    searchable_fields = ['name', 'price']
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = queryset.filter(price__gt=100)
        return queryset"""
        },
        {
            "prompt": "Create a bar chart of sales by region",
            "analysis": {
                "intent": "Visualize data",
                "model": "Sale",
                "component": "Chart",
                "chart_type": "bar"
            },
            "code": """class GeneratedChartView(ChartView):
    chart_type = 'bar'

    def get_data(self):
        from django.db.models import Sum

        qs = Sale.objects.values('region').annotate(
            value=Sum('amount')
        )

        return {
            'labels': [r['region'] for r in qs],
            'datasets': [{
                'label': 'Amount',
                'data': [r['value'] for r in qs]
            }]
        }"""
        }
    ]

    for i, example in enumerate(examples, 1):
        print(f"\nExample {i}:")
        print(f"User Prompt: \"{example['prompt']}\"\n")

        print("My Analysis:")
        for key, value in example['analysis'].items():
            print(f"  {key}: {value}")

        print(f"\nGenerated Code:\n{example['code']}\n")
        print("-" * 70)


def demo_interactive():
    """Interactive demo where you can ask Claude Code for components."""
    print_section("Interactive Component Generation")

    print("""
I can generate components for you right now!

Try these prompts:
  1. Show me all products
  2. Show me users with email containing '@example.com'
  3. Create a line chart of orders over time
  4. Build a customer feedback form
  5. Create a sales dashboard

Or type your own prompt!
Type 'examples' to see more examples, or 'quit' to exit.
""")

    while True:
        try:
            user_input = input("\nYou: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\nGoodbye!")
                break

            if user_input.lower() == 'examples':
                show_examples()
                continue

            # Analyze the prompt
            result = analyze_and_generate(user_input)

            print(f"\nClaude Code Analysis:")
            print(f"  Intent: {result['intent']}")
            print(f"  Component Type: {result['component_type']}")
            print(f"  Model: {result['model']}")

            if result.get('filters'):
                print(f"  Filters: {result['filters']}")

            print(f"\nGenerated Code:\n\n{result['code']}\n")

            print("What this component does:")
            for feature in result['features']:
                print(f"  ✓ {feature}")

            print("\nNext steps:")
            for suggestion in result['suggestions']:
                print(f"  • {suggestion}")

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}")


def analyze_and_generate(prompt: str) -> dict:
    """Analyze prompt and generate component code."""
    prompt_lower = prompt.lower()

    # Detect component type
    if any(kw in prompt_lower for kw in ["table", "show", "list", "display", "all"]):
        return generate_table(prompt)
    elif any(kw in prompt_lower for kw in ["chart", "graph", "plot", "visualize"]):
        return generate_chart(prompt)
    elif any(kw in prompt_lower for kw in ["form", "create", "add", "submit"]):
        return generate_form(prompt)
    elif any(kw in prompt_lower for kw in ["dashboard", "overview"]):
        return generate_dashboard(prompt)
    else:
        return generate_table(prompt)  # Default to table


def generate_table(prompt: str) -> dict:
    """Generate table component from prompt."""
    prompt_lower = prompt.lower()

    # Detect model
    model = "Product"  # default
    if "user" in prompt_lower:
        model = "User"
        fields = ["username", "email", "date_joined", "is_active"]
    elif "order" in prompt_lower:
        model = "Order"
        fields = ["customer", "total", "status", "created_at"]
    elif "customer" in prompt_lower:
        model = "Customer"
        fields = ["name", "email", "phone", "created_at"]
    else:
        fields = ["name", "price", "stock", "is_active"]

    # Detect filters
    filters = []
    if "price >" in prompt_lower:
        import re
        match = re.search(r'price[>\s]+(\d+)', prompt_lower)
        if match:
            filters.append(f"price__gt={match.group(1)}")

    if "email containing" in prompt_lower or "email with" in prompt_lower:
        import re
        match = re.search(r'["\']([^"\']+)["\']', prompt)
        if match:
            filters.append(f"email__contains='{match.group(1)}'")

    if "active" in prompt_lower:
        filters.append("is_active=True")

    # Generate code
    filter_code = ""
    if filters:
        filter_code = f"queryset = queryset.filter({', '.join(filters)})"

    code = f"""class GeneratedView(FxCRUDView):
    model = {model}
    fields = {fields}
    editable_fields = []
    searchable_fields = {fields[:2]}
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()
        {filter_code if filter_code else '# No filters'}
        return queryset"""

    return {
        "intent": "Display tabular data",
        "component_type": "Table",
        "model": model,
        "filters": filters,
        "code": code,
        "features": [
            "Sortable columns (click headers)",
            "Search across fields",
            "Pagination (20 rows/page)",
            "Export to CSV/Excel"
        ],
        "suggestions": [
            "Add a chart to visualize this data",
            "Make fields editable",
            "Add more filters"
        ]
    }


def generate_chart(prompt: str) -> dict:
    """Generate chart component from prompt."""
    prompt_lower = prompt.lower()

    chart_type = "bar"
    if "line" in prompt_lower:
        chart_type = "line"
    elif "pie" in prompt_lower:
        chart_type = "pie"

    model = "Sale" if "sale" in prompt_lower or "order" in prompt_lower else "Product"

    code = f"""class GeneratedChartView(ChartView):
    chart_type = '{chart_type}'

    def get_data(self):
        from django.db.models import Sum

        qs = {model}.objects.values('date').annotate(
            value=Sum('amount')
        )

        return {{
            'labels': [r['date'] for r in qs],
            'datasets': [{{
                'label': 'Amount',
                'data': [r['value'] for r in qs]
            }}]
        }}"""

    return {
        "intent": "Visualize data",
        "component_type": "Chart",
        "model": model,
        "chart_type": chart_type,
        "code": code,
        "features": [
            f"Interactive {chart_type} chart",
            "Hover for tooltips",
            "Zoom and pan",
            "Export as image"
        ],
        "suggestions": [
            "Add a table view",
            "Change date range",
            "Group by different field"
        ]
    }


def generate_form(prompt: str) -> dict:
    """Generate form component from prompt."""
    model = "Feedback" if "feedback" in prompt.lower() else "Contact"

    code = f"""class GeneratedFormView(FxView):
    template_name = 'form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = modelform_factory(
            {model},
            fields=['name', 'email', 'message']
        )
        context['form'] = form()
        return context

    def post(self, request, *args, **kwargs):
        form = modelform_factory({model}, fields=['name', 'email', 'message'])(request.POST)
        if form.is_valid():
            obj = form.save()
            return JsonResponse({{'success': True, 'id': obj.pk}})
        return JsonResponse({{'errors': form.errors}}, status=422)"""

    return {
        "intent": "Collect data via form",
        "component_type": "Form",
        "model": model,
        "code": code,
        "features": [
            "Real-time validation",
            "CSRF protection",
            "Error messages",
            "Auto-save on submit"
        ],
        "suggestions": [
            "Add more fields",
            "Add custom validation",
            "Add success message"
        ]
    }


def generate_dashboard(prompt: str) -> dict:
    """Generate dashboard component from prompt."""
    model = "Sale" if "sale" in prompt.lower() else "Product"

    code = f"""class GeneratedDashboardView(FxView):
    template_name = 'dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['widgets'] = [
            # KPI widget
            {{'type': 'kpi', 'value': {model}.objects.count(), 'label': 'Total {model}s'}},
            # Chart widget
            {{'type': 'chart', 'data': self.get_chart_data()}},
            # Table widget
            {{'type': 'table', 'data': {model}.objects.all()[:10]}}
        ]
        return context"""

    return {
        "intent": "Show overview dashboard",
        "component_type": "Dashboard",
        "model": model,
        "code": code,
        "features": [
            "Multiple widgets",
            "Real-time KPIs",
            "Interactive charts",
            "Recent data table"
        ],
        "suggestions": [
            "Add more KPIs",
            "Customize layout",
            "Add filters"
        ]
    }


def show_examples():
    """Show more example prompts."""
    print("\nMore Example Prompts:\n")

    examples = [
        ("Tables", [
            "Show me all active users",
            "Display orders from last month",
            "List products with stock < 10",
            "Show customers sorted by name"
        ]),
        ("Charts", [
            "Create a line chart of revenue over time",
            "Show a pie chart of sales by category",
            "Plot user signups by month",
            "Visualize order distribution"
        ]),
        ("Forms", [
            "Build a contact form",
            "Create a product submission form",
            "Make a customer feedback form",
            "Build a registration form"
        ]),
        ("Dashboards", [
            "Create a sales dashboard",
            "Build an analytics overview",
            "Make a customer dashboard",
            "Create a product metrics dashboard"
        ])
    ]

    for category, prompts in examples:
        print(f"{category}:")
        for prompt in prompts:
            print(f"  • {prompt}")
        print()


def main():
    """Run the demo."""
    print("\n" + "🤖" * 35)
    print("Claude Code as LLM Agent")
    print("Component Generation Demo (Standalone)")
    print("🤖" * 35)

    print("""
This demo shows how Claude Code (me!) can act as an LLM agent to generate
interactive web components from natural language.

Choose a demo:
  1. Show examples of component generation
  2. Interactive mode (try your own prompts!)
  q. Quit
""")

    choice = input("Select (1, 2, or q): ").strip()

    if choice == '1':
        demo_claude_code_capabilities()
    elif choice == '2':
        demo_interactive()
    elif choice.lower() in ['q', 'quit']:
        print("Goodbye!")
    else:
        print("Invalid choice!")


if __name__ == "__main__":
    main()
