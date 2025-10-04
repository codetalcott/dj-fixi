# dj-fixi + FixiPlug Integration Patterns

This document explores integration patterns beyond basic CRUD tables, focusing on complex data interactions.

## Overview

**Pattern:** Django provides structured data + metadata → FixiPlug provides interactive UI components

**Key Principle:** Backend-driven configuration, client-side interactivity

---

## 1. DataFrames & Scientific Data 📊

### Use Case
Display pandas DataFrames, numpy arrays, or scientific datasets with interactive exploration.

### Django Side (dj-fixi)

```python
from dj_fixi.dataframe import DataFrameView
import pandas as pd

class DataAnalysisView(DataFrameView):
    def get_dataframe(self):
        # From pandas
        df = pd.read_csv('data.csv')
        return df

    # Or from database
    def get_dataframe_from_queryset(self):
        qs = Measurement.objects.all()
        df = pd.DataFrame(list(qs.values()))
        return df
```

**Output JSON:**
```json
{
  "type": "dataframe",
  "data": [...],
  "columns": [...],
  "dtypes": {"value": "float64", "timestamp": "datetime64"},
  "index": [0, 1, 2, ...],
  "stats": {
    "value": {"mean": 42.5, "std": 12.3, "min": 10, "max": 100}
  },
  "meta": {
    "shape": [1000, 5],
    "memory_usage": "40KB"
  }
}
```

### FixiPlug Side

**Plugin: `dataframe.js`**

Features:
- Interactive column sorting/filtering
- Statistical summaries on hover
- Data type indicators (numeric, datetime, categorical)
- Column operations (sum, mean, count)
- Export to CSV/Excel
- Inline plotting (histograms, scatter plots)

```html
<div
  fx-action="/api/analysis/"
  fx-trigger="load"
  fx-dataframe
  fx-show-stats
  fx-enable-plots>
</div>
```

---

## 2. Code Editors & Syntax Highlighting 💻

### Use Case
Editable code snippets with syntax highlighting, validation, and execution.

### Django Side (dj-fixi)

```python
from dj_fixi.code import CodeSnippetView

class PythonPlaygroundView(CodeSnippetView):
    model = CodeSnippet
    language = 'python'
    allow_execution = True

    def execute_code(self, code):
        # Safe execution with restrictions
        result = run_in_sandbox(code)
        return {
            'output': result.stdout,
            'error': result.stderr,
            'execution_time': result.duration
        }
```

**Output JSON:**
```json
{
  "type": "code",
  "content": "def hello():\n    print('world')",
  "language": "python",
  "metadata": {
    "editable": true,
    "executable": true,
    "theme": "monokai"
  },
  "validation": {
    "syntax_errors": [],
    "linter_warnings": ["Line too long (90 > 79)"]
  }
}
```

### FixiPlug Side

**Plugin: `code-editor.js`**

Features:
- Syntax highlighting (using Prism.js/highlight.js pattern)
- Line numbers
- Auto-indent
- Code execution with output display
- Diff viewer for changes
- Collaborative editing indicators

```html
<div
  fx-action="/snippets/123/"
  fx-code-editor
  fx-language="python"
  fx-theme="monokai"
  fx-execute-url="/snippets/123/execute/">
</div>
```

**Integration with Django:**
- `POST /execute/` → Run code in Django sandbox
- Django validates + executes → Returns output
- FixiPlug displays results inline

---

## 3. Rich Text Editors (WYSIWYG) 📝

### Use Case
Content editing with real-time preview, markdown support, and media embedding.

### Django Side (dj-fixi)

```python
from dj_fixi.richtext import RichTextView

class ArticleEditorView(RichTextView):
    model = Article
    field = 'content'
    format = 'markdown'  # or 'html', 'wysiwg'

    allowed_tags = ['p', 'strong', 'em', 'a', 'img', 'code', 'pre']
    media_upload_url = '/api/media/upload/'

    def process_content(self, content):
        # Sanitize HTML
        # Process markdown
        # Extract metadata (reading time, headings)
        return {
            'html': rendered_html,
            'toc': table_of_contents,
            'reading_time': estimated_minutes
        }
```

**Output JSON:**
```json
{
  "type": "richtext",
  "content": "# Hello\n\nThis is **markdown**",
  "format": "markdown",
  "rendered": "<h1>Hello</h1><p>This is <strong>markdown</strong></p>",
  "metadata": {
    "editable": true,
    "allowed_tags": ["p", "strong", "em"],
    "media_upload": "/api/media/upload/",
    "autosave_interval": 5000
  },
  "toc": [
    {"level": 1, "text": "Hello", "id": "hello"}
  ]
}
```

### FixiPlug Side

**Plugin: `richtext-editor.js`**

Features:
- Split view: markdown editor + live preview
- Toolbar (bold, italic, links, images)
- Auto-save to Django backend
- Image drag-and-drop upload
- Table of contents generation
- Word count

```html
<div
  fx-action="/articles/123/"
  fx-richtext
  fx-format="markdown"
  fx-autosave
  fx-upload-url="/api/media/upload/">
</div>
```

---

## 4. Forms with Complex Validation 📋

### Use Case
Multi-step forms, conditional fields, async validation.

### Django Side (dj-fixi)

```python
from dj_fixi.forms import FxModelForm, ConditionalField

class ApplicationForm(FxModelForm):
    class Meta:
        model = Application
        fields = '__all__'

    # Define field dependencies
    conditional_fields = {
        'employment_status': {
            'employed': ['company_name', 'job_title'],
            'student': ['university', 'major'],
            'unemployed': []
        }
    }

    # Async validators
    async_validators = {
        'email': '/api/validate/email/',
        'username': '/api/validate/username/'
    }

    def to_json(self):
        return {
            'type': 'form',
            'fields': [...],
            'conditional_fields': self.conditional_fields,
            'validators': self.async_validators,
            'steps': [
                {'title': 'Personal Info', 'fields': ['name', 'email']},
                {'title': 'Employment', 'fields': ['employment_status', ...]},
            ]
        }
```

### FixiPlug Side

**Plugin: `smart-forms.js`**

Features:
- Show/hide fields based on selections
- Async validation (check username availability)
- Multi-step progress indicator
- Field dependencies
- Real-time error display
- Auto-save drafts

```html
<form
  fx-action="/applications/create/"
  fx-smart-form
  fx-multi-step
  fx-autosave>
</form>
```

---

## 5. File Upload with Processing 📁

### Use Case
Drag-and-drop file upload with progress, previews, and server-side processing.

### Django Side (dj-fixi)

```python
from dj_fixi.upload import FileUploadView

class ImageUploadView(FileUploadView):
    allowed_types = ['image/jpeg', 'image/png', 'image/webp']
    max_size = 10 * 1024 * 1024  # 10MB

    def process_file(self, file):
        # Resize image
        # Generate thumbnails
        # Extract EXIF data
        # Run virus scan

        return {
            'id': saved_file.id,
            'url': saved_file.url,
            'thumbnail': thumbnail_url,
            'metadata': {
                'width': 1920,
                'height': 1080,
                'format': 'JPEG',
                'size': '2.4MB'
            }
        }
```

### FixiPlug Side

**Plugin: `file-upload.js`**

Features:
- Drag-and-drop zone
- Multiple file upload
- Progress bars
- Image previews
- Client-side validation
- Chunked upload for large files
- Resume failed uploads

```html
<div
  fx-upload
  fx-action="/api/upload/"
  fx-accept="image/*"
  fx-max-size="10485760"
  fx-preview>
</div>
```

---

## 6. Real-Time Collaboration 🤝

### Use Case
Google Docs-style collaborative editing with presence indicators.

### Django Side (dj-fixi)

```python
from dj_fixi.collaboration import CollaborativeView
from channels.layers import get_channel_layer

class DocumentCollaborationView(CollaborativeView):
    model = Document

    def get_active_users(self):
        # Track who's editing
        return {
            'users': [
                {'id': 1, 'name': 'Alice', 'cursor_position': 42, 'color': '#ff0000'},
                {'id': 2, 'name': 'Bob', 'cursor_position': 108, 'color': '#00ff00'}
            ]
        }

    def broadcast_change(self, change):
        # Send to WebSocket
        channel_layer = get_channel_layer()
        channel_layer.group_send(f'doc_{self.object.id}', {
            'type': 'content_update',
            'change': change
        })
```

### FixiPlug Side

**Plugin: `collaboration.js`**

Features:
- Cursor position indicators
- User presence (who's viewing/editing)
- Conflict resolution
- Operational transformation
- Activity feed

```html
<div
  fx-collaborative
  fx-document-id="123"
  fx-websocket-url="/ws/documents/123/"
  fx-show-cursors>
</div>
```

---

## 7. Data Visualization & Charts 📈

### Use Case
Interactive charts generated from Django querysets.

### Django Side (dj-fixi)

```python
from dj_fixi.charts import ChartView

class SalesChartView(ChartView):
    def get_chart_data(self):
        sales = Sale.objects.filter(date__year=2024)

        return {
            'type': 'chart',
            'chart_type': 'line',
            'data': {
                'labels': ['Jan', 'Feb', 'Mar', ...],
                'datasets': [
                    {
                        'label': 'Revenue',
                        'data': [1200, 1900, 3000, ...],
                        'color': '#4CAF50'
                    }
                ]
            },
            'options': {
                'responsive': true,
                'interactive': true,
                'export': ['png', 'svg', 'csv']
            }
        }
```

### FixiPlug Side

**Plugin: `charts.js`**

Features:
- Interactive tooltips
- Zoom/pan
- Data point selection
- Real-time updates
- Export options
- Multiple chart types

```html
<div
  fx-action="/api/sales/chart/"
  fx-chart
  fx-type="line"
  fx-interactive
  fx-realtime>
</div>
```

---

## 8. Search with Autocomplete 🔍

### Use Case
Smart search with suggestions, filters, and instant results.

### Django Side (dj-fixi)

```python
from dj_fixi.search import SearchView

class ProductSearchView(SearchView):
    model = Product
    search_fields = ['name', 'description', 'tags']

    def get_suggestions(self, query):
        # Fuzzy matching
        # Popular searches
        # Recent searches

        return {
            'type': 'search',
            'query': query,
            'suggestions': [
                {'text': 'iPhone 15', 'count': 23, 'type': 'product'},
                {'text': 'iPhone 15 Pro', 'count': 12, 'type': 'product'}
            ],
            'filters': [
                {'key': 'category', 'label': 'Category', 'options': [...]},
                {'key': 'price_range', 'label': 'Price', 'type': 'range'}
            ]
        }
```

### FixiPlug Side

**Plugin: `smart-search.js`**

Features:
- Instant suggestions (debounced)
- Keyboard navigation
- Filter UI
- Search history
- Highlighting matches
- Voice search

```html
<input
  type="search"
  fx-search
  fx-action="/api/search/"
  fx-suggestions
  fx-min-chars="2"
  fx-debounce="300">
```

---

## 9. Kanban Boards & Drag-and-Drop 📌

### Use Case
Trello-style task boards with drag-and-drop.

### Django Side (dj-fixi)

```python
from dj_fixi.kanban import KanbanView

class TaskBoardView(KanbanView):
    model = Task

    def get_board_data(self):
        return {
            'type': 'kanban',
            'columns': [
                {
                    'id': 'todo',
                    'title': 'To Do',
                    'cards': [
                        {'id': 1, 'title': 'Task 1', 'assigned_to': 'Alice'},
                        {'id': 2, 'title': 'Task 2', 'assigned_to': 'Bob'}
                    ]
                },
                {
                    'id': 'in_progress',
                    'title': 'In Progress',
                    'cards': [...]
                }
            ],
            'actions': {
                'move': '/api/tasks/move/',
                'create': '/api/tasks/create/',
                'update': '/api/tasks/{id}/update/'
            }
        }
```

### FixiPlug Side

**Plugin: `kanban.js`**

Features:
- Drag-and-drop cards
- Column reordering
- Card creation inline
- Quick edit on double-click
- Swimlanes
- WIP limits

```html
<div
  fx-action="/api/board/"
  fx-kanban
  fx-draggable
  fx-wip-limit="5">
</div>
```

---

## Common Pattern: JSON Protocol

All integrations follow this protocol:

```json
{
  "type": "component_type",
  "data": {...},
  "metadata": {
    "editable": true,
    "permissions": ["view", "edit"],
    "features": ["autosave", "export"]
  },
  "actions": {
    "save": "/api/endpoint/",
    "delete": "/api/endpoint/delete/",
    "validate": "/api/endpoint/validate/"
  }
}
```

## Implementation Strategy

1. **Create base classes in dj-fixi:**
   - `DataFrameView`
   - `CodeSnippetView`
   - `RichTextView`
   - `ChartView`
   - etc.

2. **Create FixiPlug plugins:**
   - `dataframe.js`
   - `code-editor.js`
   - `richtext-editor.js`
   - `charts.js`
   - etc.

3. **Django integration plugin extensions:**
   - Detect component types
   - Route to appropriate FixiPlug plugin
   - Handle authentication/authorization
   - Manage WebSocket connections

## Next Steps

Which integration pattern is most valuable for your use case?

1. **DataFrames** - Scientific/analytical data
2. **Code editors** - Developer tools
3. **Rich text** - Content management
4. **Smart forms** - Complex data entry
5. **Collaboration** - Real-time editing
6. **Visualization** - Charts and dashboards
