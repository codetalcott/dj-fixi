# dj-fixi Integration Patterns & Improvements

## Current Implementation Analysis

### Strengths of ExperimentalCourseCRUDView

```python
class ExperimentalCourseCRUDView(FxCRUDView):
    """Clean, declarative CRUD view with FixiPlug integration."""
    
    model = Course
    template_name = "experimental/course_table.html"
    
    # ✅ Clear field configuration
    fields = ['id', 'student', 'class_title', ...]
    searchable_fields = ['class_title', 'subject', ...]
    editable_fields = []  # Safety first
    
    # ✅ Proper queryset optimization
    def get_queryset(self):
        return super().get_queryset().select_related(
            'student', 'school', 'credit_system'
        )
    
    # ✅ Custom serialization handles foreign keys
    def serialize_object(self, obj):
        return {
            'id': obj.pk,
            'student': str(obj.student),
            'student_id': obj.student.pk if obj.student else None,
            ...
        }
    
    # ✅ Frontend configuration
    def get_column_config(self):
        return [
            {'key': 'id', 'label': 'ID', 'sortable': True},
            ...
        ]
```

**Key Benefits:**
1. Single view handles GET, POST, PATCH, DELETE
2. Auto JSON/HTML content negotiation
3. Built-in search, sort, pagination
4. Type-safe field configuration
5. Safety through `editable_fields` control

## Recommended Enhancements

### 1. MCP-Specific Response Mixin

```python
# dj_fixi/mixins.py

from typing import Any, Dict
from django.http import JsonResponse
from django.utils import timezone

class MCPResponseMixin:
    """
    Mixin to ensure MCP-compatible JSON responses.
    
    All responses follow standardized format:
    {
        "success": bool,
        "data": {...},
        "meta": {...}
    }
    """
    
    def get_mcp_meta(self) -> Dict[str, Any]:
        """Override to add custom metadata."""
        return {
            'view': self.__class__.__name__,
            'model': self.model.__name__,
            'timestamp': timezone.now().isoformat()
        }
    
    def mcp_success_response(
        self, 
        data: Any, 
        status: int = 200,
        extra_meta: Dict[str, Any] = None
    ) -> JsonResponse:
        """Create standardized success response."""
        meta = self.get_mcp_meta()
        if extra_meta:
            meta.update(extra_meta)
            
        return JsonResponse({
            'success': True,
            'data': data,
            'meta': meta
        }, status=status)
    
    def mcp_error_response(
        self,
        error: str,
        status: int = 400,
        error_code: str = None
    ) -> JsonResponse:
        """Create standardized error response."""
        return JsonResponse({
            'success': False,
            'error': error,
            'error_code': error_code,
            'meta': self.get_mcp_meta()
        }, status=status)
```

### 2. Enhanced FxCRUDView with MCP Support

```python
# dj_fixi/views.py

from typing import List, Dict, Any
from django.db.models import QuerySet
from .mixins import MCPResponseMixin
import json

class FxCRUDView(MCPResponseMixin, View):
    """Enhanced CRUD view with MCP compatibility."""
    
    # ... existing code ...
    
    # New: Validation rules
    validation_rules: Dict[str, Dict[str, Any]] = {}
    
    # New: Field-level permissions
    read_only_fields: List[str] = []
    
    # New: Change tracking
    enable_audit_log: bool = False
    
    def validate_field(self, field: str, value: Any) -> tuple[bool, str]:
        """
        Validate individual field value.
        
        Returns:
            (is_valid, error_message)
        """
        if field not in self.validation_rules:
            return True, ""
        
        rules = self.validation_rules[field]
        
        # Required check
        if rules.get('required') and not value:
            return False, f"{field} is required"
        
        # Type check
        expected_type = rules.get('type')
        if expected_type and not isinstance(value, expected_type):
            return False, f"{field} must be of type {expected_type.__name__}"
        
        # Custom validator
        validator = rules.get('validator')
        if validator:
            try:
                validator(value)
            except ValueError as e:
                return False, str(e)
        
        return True, ""
    
    def validate_data(self, data: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Validate all provided data.
        
        Returns:
            (is_valid, error_messages)
        """
        errors = []
        
        for field, value in data.items():
            if field not in self.editable_fields:
                errors.append(f"{field} is not editable")
                continue
            
            is_valid, error = self.validate_field(field, value)
            if not is_valid:
                errors.append(error)
        
        return len(errors) == 0, errors
    
    def patch(self, request, pk=None):
        """Enhanced PATCH with validation and MCP response."""
        try:
            # Parse request data
            data = json.loads(request.body)
            
            # Validate data
            is_valid, errors = self.validate_data(data)
            if not is_valid:
                return self.mcp_error_response(
                    error="; ".join(errors),
                    status=400,
                    error_code='VALIDATION_ERROR'
                )
            
            # Get object
            obj = self.model.objects.get(pk=pk)
            
            # Track changes if enabled
            if self.enable_audit_log:
                old_values = {
                    field: getattr(obj, field)
                    for field in data.keys()
                }
            
            # Update fields
            for field, value in data.items():
                if field in self.editable_fields:
                    setattr(obj, field, value)
            
            obj.save()
            
            # Log changes
            if self.enable_audit_log:
                self.log_change(
                    obj=obj,
                    old_values=old_values,
                    new_values=data,
                    user=request.user
                )
            
            return self.mcp_success_response(
                data=self.serialize_object(obj),
                extra_meta={
                    'updated_fields': list(data.keys())
                }
            )
            
        except self.model.DoesNotExist:
            return self.mcp_error_response(
                error="Object not found",
                status=404,
                error_code='NOT_FOUND'
            )
        except json.JSONDecodeError:
            return self.mcp_error_response(
                error="Invalid JSON",
                status=400,
                error_code='INVALID_JSON'
            )
        except Exception as e:
            return self.mcp_error_response(
                error=str(e),
                status=500,
                error_code='INTERNAL_ERROR'
            )
    
    def log_change(
        self,
        obj: Any,
        old_values: Dict,
        new_values: Dict,
        user: Any
    ):
        """Log changes for audit trail."""
        # Implementation depends on audit log system
        pass
```

### 3. Example Usage with Validation

```python
# transcript_manager/experimental_views.py

from dj_fixi.views import FxCRUDView
from transcript_manager.models import Course
from decimal import Decimal

class ExperimentalCourseCRUDView(FxCRUDView):
    model = Course
    template_name = "experimental/course_table.html"
    
    # Define what can be edited
    editable_fields = ['grade', 'credits', 'completion_date']
    
    # Add read-only fields for display
    read_only_fields = ['id', 'student', 'school', 'class_title']
    
    # Enable change tracking
    enable_audit_log = True
    
    # Define validation rules
    validation_rules = {
        'grade': {
            'required': False,
            'type': str,
            'validator': lambda v: _validate_grade(v)
        },
        'credits': {
            'required': True,
            'type': (Decimal, float, int),
            'validator': lambda v: _validate_credits(v)
        },
        'completion_date': {
            'required': False,
            'type': str,  # ISO format string
            'validator': lambda v: _validate_date(v)
        }
    }
    
    def get_queryset(self):
        return super().get_queryset().select_related(
            'student', 'school', 'credit_system'
        )
    
    def get_mcp_meta(self):
        """Add course-specific metadata."""
        meta = super().get_mcp_meta()
        meta.update({
            'editable_fields': self.editable_fields,
            'searchable_fields': self.searchable_fields,
            'total_courses': self.get_queryset().count()
        })
        return meta

def _validate_grade(value):
    """Validate grade format."""
    valid_grades = [
        'A+', 'A', 'A-',
        'B+', 'B', 'B-',
        'C+', 'C', 'C-',
        'D+', 'D', 'D-',
        'F', 'P', 'NP'
    ]
    if value not in valid_grades:
        raise ValueError(f"Invalid grade. Must be one of: {', '.join(valid_grades)}")

def _validate_credits(value):
    """Validate credits value."""
    credit_value = Decimal(str(value))
    if credit_value < 0:
        raise ValueError("Credits cannot be negative")
    if credit_value > 20:
        raise ValueError("Credits cannot exceed 20")

def _validate_date(value):
    """Validate ISO date format."""
    from datetime import datetime
    try:
        datetime.fromisoformat(value)
    except ValueError:
        raise ValueError("Date must be in ISO format (YYYY-MM-DD)")
```

### 4. Middleware Enhancement

```python
# dj_fixi/middleware.py

import time
from django.utils.deprecation import MiddlewareMixin

class FxMiddleware(MiddlewareMixin):
    """Enhanced middleware with MCP support."""
    
    def process_request(self, request):
        """Mark Fixi requests and add timing."""
        # Existing logic
        is_fx = (
            request.headers.get('FX-Request') == 'true' or
            request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        )
        request.is_fx = is_fx
        
        # Add timing
        request._fx_start_time = time.time()
        
        # Add MCP context
        if request.headers.get('X-MCP-Session'):
            request.mcp_session = request.headers['X-MCP-Session']
            request.is_mcp = True
        else:
            request.is_mcp = False
    
    def process_response(self, request, response):
        """Add timing and MCP headers to response."""
        # Add execution time
        if hasattr(request, '_fx_start_time'):
            execution_time = (time.time() - request._fx_start_time) * 1000
            response['X-Execution-Time'] = f"{execution_time:.2f}ms"
        
        # Add MCP headers
        if hasattr(request, 'is_mcp') and request.is_mcp:
            response['X-MCP-Compatible'] = 'true'
        
        return response
```

### 5. Testing Utilities

```python
# dj_fixi/testing.py

from django.test import Client
import json

class FxTestClient(Client):
    """Test client with Fixi and MCP support."""
    
    def fx_get(self, url, **kwargs):
        """GET request with FX headers."""
        return self.get(
            url,
            HTTP_FX_REQUEST='true',
            HTTP_ACCEPT='application/json',
            **kwargs
        )
    
    def fx_patch(self, url, data, **kwargs):
        """PATCH request with FX headers."""
        return self.patch(
            url,
            data=json.dumps(data),
            content_type='application/json',
            HTTP_FX_REQUEST='true',
            **kwargs
        )
    
    def mcp_get(self, url, session_id='test-session', **kwargs):
        """GET request with MCP headers."""
        return self.get(
            url,
            HTTP_X_MCP_SESSION=session_id,
            HTTP_ACCEPT='application/json',
            **kwargs
        )

# Example test
from django.test import TestCase
from transcript_manager.models import Course

class CourseViewTest(TestCase):
    def setUp(self):
        self.client = FxTestClient()
        self.course = Course.objects.create(...)
    
    def test_mcp_response_format(self):
        """Test MCP-compatible response."""
        response = self.client.mcp_get('/experimental/courses/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Check MCP response structure
        self.assertIn('success', data)
        self.assertIn('data', data)
        self.assertIn('meta', data)
        
        self.assertTrue(data['success'])
        self.assertIsInstance(data['data'], list)
        self.assertIn('timestamp', data['meta'])
    
    def test_validation_error(self):
        """Test validation error format."""
        response = self.client.fx_patch(
            f'/experimental/courses/{self.course.pk}/',
            data={'grade': 'INVALID'}
        )
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        
        self.assertFalse(data['success'])
        self.assertIn('error', data)
        self.assertEqual(data['error_code'], 'VALIDATION_ERROR')
```

## Migration Path for Existing Views

### Step 1: Add MCPResponseMixin
```python
class ExperimentalCourseCRUDView(MCPResponseMixin, FxCRUDView):
    # No other changes needed - existing code works
    pass
```

### Step 2: Add Validation Rules (Optional)
```python
class ExperimentalCourseCRUDView(MCPResponseMixin, FxCRUDView):
    # ... existing code ...
    
    validation_rules = {
        'grade': {
            'validator': lambda v: _validate_grade(v)
        }
    }
```

### Step 3: Enable Audit Logging (Optional)
```python
class ExperimentalCourseCRUDView(MCPResponseMixin, FxCRUDView):
    # ... existing code ...
    
    enable_audit_log = True
    
    def log_change(self, obj, old_values, new_values, user):
        # Custom audit logging
        AuditLog.objects.create(
            model=self.model.__name__,
            object_id=obj.pk,
            user=user,
            changes=new_values,
            timestamp=timezone.now()
        )
```

## Best Practices

### 1. Always Use select_related/prefetch_related
```python
def get_queryset(self):
    return super().get_queryset().select_related(
        'student',
        'school',
        'credit_system'
    ).prefetch_related(
        'requirements'
    )
```

### 2. Separate Read and Write Fields
```python
# Display fields
fields = ['id', 'student', 'class_title', 'grade', 'credits']

# Editable fields (subset of fields)
editable_fields = ['grade', 'credits']

# Read-only (calculated or protected)
read_only_fields = ['id', 'student', 'class_title']
```

### 3. Provide Custom Serialization for Complex Types
```python
def serialize_object(self, obj):
    return {
        'id': obj.pk,
        'student': {
            'id': obj.student.pk,
            'name': str(obj.student),
            'email': obj.student.email
        },
        'credits': float(obj.credits),  # Decimal to float
        'completion_date': obj.completion_date.isoformat() if obj.completion_date else None,
        'is_in_progress': obj.is_in_progress()  # Method call
    }
```

### 4. Use Validation for Data Integrity
```python
validation_rules = {
    'grade': {
        'type': str,
        'validator': lambda v: v in VALID_GRADES
    },
    'credits': {
        'type': (Decimal, float),
        'validator': lambda v: 0 <= Decimal(str(v)) <= 20
    }
}
```

## Summary

The dj-fixi integration provides strong patterns:
- ✅ Clean declarative views
- ✅ Built-in JSON/HTML negotiation
- ✅ Search, sort, pagination

Recommended enhancements:
1. **MCPResponseMixin** - Standardize all responses
2. **Field validation** - Ensure data integrity
3. **Audit logging** - Track changes
4. **Enhanced middleware** - Better MCP support
5. **Testing utilities** - Comprehensive test coverage

These improvements maintain backward compatibility while adding enterprise-grade features for MCP integration.
