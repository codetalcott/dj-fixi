# LLM Agent Integration - Quick Start

Transform LLM text output into **live interactive web components**.

## Overview

Instead of this:
```
User: "Show me sales data"
LLM: "Here's the sales data:
     - Product A: $1,200
     - Product B: $850
     ..."
```

You get this:
```
User: "Show me sales data"
LLM: [Generates interactive table]
User sees: [Sortable, filterable, exportable table with real data]
```

## Architecture

```
User Prompt
    ↓
LLM (with tools)  →  Calls create_table/create_chart/etc.
    ↓
ComponentGenerator  →  Generates Django view code
    ↓
SafeExecutor  →  Validates & executes code safely
    ↓
Django Response  →  Returns JSON
    ↓
FixiPlug  →  Renders interactive UI
    ↓
User interacts  →  Sorts, filters, edits, exports
```

## Files Created

```
dj_fixi/llm/
├── __init__.py          # Package exports
├── generator.py         # ComponentGenerator, TableGenerator, etc.
├── executor.py          # SafeExecutor, ComponentExecutor
├── tools.py             # LLM tool definitions
└── views.py             # Django endpoints

examples/
└── demo_llm_integration.py  # Runnable demo
```

## Quick Start

### 1. Install Dependencies

```bash
pip install django anthropic  # or openai
```

### 2. Run the Demo

```bash
python examples/demo_llm_integration.py
```

This shows:
- ✅ Table generation from prompts
- ✅ Chart generation
- ✅ Code validation & security
- ✅ Tool definitions
- ✅ Complete flow simulation

### 3. Use in Your App

#### Option A: Direct Tool Use

```python
from dj_fixi.llm import TableGenerator, SafeExecutor

# User prompt
prompt = "Show me products with price > 100"

# Generate component
generator = TableGenerator(user=request.user, allowed_models=["products.Product"])
component = generator.generate(
    prompt=prompt,
    context={
        "model": "products.Product",
        "fields": ["name", "price", "stock"],
        "filters": {"price__gt": 100}
    }
)

# Execute safely
executor = SafeExecutor(user=request.user, allowed_models=["products.Product"])
result = executor.execute_and_get_json(component["view_code"], request)

# Returns JSON for FixiPlug
```

#### Option B: Via Django Endpoints

Add to your `urls.py`:

```python
from dj_fixi.llm.views import LLMComponentView, LLMConversationView

urlpatterns = [
    path('llm/component/', LLMComponentView.as_view()),
    path('llm/chat/', LLMConversationView.as_view()),
]
```

Make requests:

```bash
# Create a table
curl -X POST http://localhost:8000/llm/component/ \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "create_table",
    "arguments": {
      "model": "products.Product",
      "fields": ["name", "price"],
      "filters": {"is_active": true}
    }
  }'
```

#### Option C: With LLM API (Claude, GPT)

```python
from anthropic import Anthropic
from dj_fixi.llm.tools import get_tool_definitions, get_system_prompt

client = Anthropic(api_key="your-key")

# Get tools for Claude
tools = get_tool_definitions()
system = get_system_prompt()

# User message
message = "Show me all products"

# Claude decides which tool to call
response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    system=system,
    tools=tools,
    messages=[{"role": "user", "content": message}]
)

# Execute tool calls
for content_block in response.content:
    if content_block.type == "tool_use":
        tool_name = content_block.name
        arguments = content_block.input

        # Generate & execute component
        # ... (see Option A)
```

## Available Tools

### 1. `create_table`
Generate interactive data tables.

**Arguments:**
- `model`: Django model name (e.g., "products.Product")
- `fields`: List of fields to display
- `filters`: Django ORM filters
- `editable_fields`: Fields that can be edited inline
- `sortable`: Enable column sorting
- `page_size`: Rows per page

**Output:** Sortable, filterable, exportable table

### 2. `create_chart`
Generate interactive charts.

**Arguments:**
- `model`: Django model
- `chart_type`: "line", "bar", "pie", "scatter"
- `x_field`: X-axis field
- `y_field`: Y-axis field
- `aggregate`: "Sum", "Avg", "Count", etc.

**Output:** Interactive chart with zoom, tooltips

### 3. `create_form`
Generate interactive forms.

**Arguments:**
- `model`: Django model
- `fields`: Form fields
- `validators`: Custom validation
- `initial_data`: Default values

**Output:** Form with real-time validation

### 4. `create_dashboard`
Generate multi-widget dashboards.

**Arguments:**
- `title`: Dashboard title
- `layout`: "grid", "columns", "rows"
- `widgets`: List of components

**Output:** Dashboard with multiple widgets

### 5. `create_kpi`
Generate KPI/metric cards.

**Arguments:**
- `label`: KPI label
- `model`: Django model
- `aggregate`: Aggregation function
- `format`: "number", "currency", "percentage"

**Output:** KPI card with trends

## Security

The `SafeExecutor` provides multiple layers of security:

### 1. Code Validation (AST)
- ❌ No imports allowed
- ❌ No `exec`/`eval`
- ❌ No file operations
- ❌ No access to `__builtins__`

### 2. Sandboxed Namespace
- ✅ Only whitelisted modules
- ✅ Only user's allowed models
- ✅ Safe built-ins only

### 3. Resource Limits
- ⏱️ Execution timeout (5 seconds)
- 📊 Max query rows (1,000)
- 🔒 Permission checks

### 4. Validation Before Execution
```python
executor = SafeExecutor(...)
is_valid, error = executor.validate_code(code)
if not is_valid:
    raise SecurityViolation(error)
```

## Example Use Cases

### Data Analysis
```
User: "Show me sales trends by region"
LLM: [Table + Chart] → Interactive exploration
```

### Dashboards
```
User: "Create a sales dashboard"
LLM: [KPIs + Charts + Tables] → Real-time overview
```

### Forms
```
User: "I need a customer feedback form"
LLM: [Form with validation] → Ready to use
```

### Reports
```
User: "Generate Q4 financial report"
LLM: [Multi-section report] → Interactive, exportable
```

## Integration with FixiPlug

The generated JSON is compatible with FixiPlug plugins:

```json
{
  "type": "table",
  "data": [{...}, {...}],
  "columns": [
    {"key": "name", "label": "Name", "sortable": true, "editable": true},
    {"key": "price", "label": "Price", "sortable": true}
  ],
  "meta": {
    "editable": true,
    "searchable": true
  }
}
```

FixiPlug `django-integration.js` detects this format and routes to `table.js` plugin.

## Iterative Refinement

LLM maintains conversation context:

```
User: "Show me products"
LLM: [Creates table]

User: "Add a chart"
LLM: [Adds chart, keeps table]

User: "Filter to price > 100"
LLM: [Updates both components]

User: "Make it editable"
LLM: [Adds editable_fields]
```

Each step preserves previous components and refines them.

## Next Steps

### Immediate
1. **Test the demo**: `python examples/demo_llm_integration.py`
2. **Review tool definitions**: `dj_fixi/llm/tools.py`
3. **Read full docs**: `docs/LLM_AGENT_INTEGRATION.md`

### Integration
1. **Add LLM API**: Integrate with Claude/GPT
2. **Build frontend**: Create chat interface
3. **Add storage**: Persist generated components
4. **Implement auth**: User permissions for models

### Enhancement
1. **More component types**: Trees, calendars, maps
2. **Self-correction**: LLM fixes errors automatically
3. **Explanation mode**: Components explain themselves
4. **Template library**: Pre-built component templates

## Comparison

| Traditional LLM | LLM + dj-fixi + FixiPlug |
|-----------------|--------------------------|
| Text output | Interactive components |
| Static data | Live, real-time data |
| Can't explore | Sort, filter, drill-down |
| Can't verify | Directly from database |
| Read-only | Can edit inline |
| No exports | Export to CSV/Excel |

## Status

✅ **Implemented:**
- ComponentGenerator (base + 4 types)
- SafeExecutor with security
- Tool definitions (5 tools)
- Django endpoints
- Demo showing flow

🚧 **In Progress:**
- FixiPlug table plugin (see table-plugin-plan.md Phase 1.5)
- Real LLM API integration
- Component storage

📋 **Planned:**
- More component types
- Frontend chat interface
- Authentication/permissions
- Advanced features

## Contributing

To add a new component type:

1. **Create generator** in `dj_fixi/llm/generator.py`:
   ```python
   class NewComponentGenerator(ComponentGenerator):
       def generate(self, prompt, context):
           # Generate view code
           return {"component_type": "new", "view_code": "..."}
   ```

2. **Add tool definition** in `dj_fixi/llm/tools.py`:
   ```python
   def get_new_component_tool():
       return {"name": "create_new", ...}
   ```

3. **Test** in `examples/demo_llm_integration.py`

## License

Same as dj-fixi (see main project LICENSE)

## Questions?

See `docs/LLM_AGENT_INTEGRATION.md` for comprehensive documentation.
