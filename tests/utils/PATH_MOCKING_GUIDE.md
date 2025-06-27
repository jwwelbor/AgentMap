"""
Path Mocking Utilities - Usage Guide

This guide explains how to use the centralized path mocking utilities to avoid 
common testing issues with pathlib.Path operations.

## Common Problems Solved

### ❌ Problem: Direct Path Attribute Mocking Fails
```python
# This FAILS - Path.exists and Path.stat are read-only
output_path.exists = Mock(return_value=True)  # AttributeError!
output_path.stat = Mock(return_value=Mock(st_mtime=1642000000))  # AttributeError!
```

### ✅ Solution: Use Path Mocking Utilities
```python
from tests.utils.path_mocking_utils import PathOperationsMocker, mock_compilation_currency

# Simple approach for most cases
with PathOperationsMocker() as path_mock:
    path_mock.set_exists(output_path, True)
    path_mock.set_stat(output_path, 1642000000)
    # test code here
```

## Quick Reference

### 1. Simple Path Existence Mocking
```python
from tests.utils.path_mocking_utils import mock_path_exists

def test_file_operations(self):
    with mock_path_exists({
        "/existing/file.txt": True,
        "/missing/file.txt": False
    }):
        # Test code that checks file existence
        assert Path("/existing/file.txt").exists()
        assert not Path("/missing/file.txt").exists()
```

### 2. File Timestamp Mocking
```python
from tests.utils.path_mocking_utils import mock_path_stat

def test_file_timestamps(self):
    with mock_path_stat({
        "/newer/file.txt": 1642000000,  # Newer timestamp
        "/older/file.txt": 1641000000   # Older timestamp  
    }):
        # Test code that checks file modification times
        newer_stat = Path("/newer/file.txt").stat()
        assert newer_stat.st_mtime == 1642000000
```

### 3. Compilation Currency Scenarios (Most Common)
```python
from tests.utils.path_mocking_utils import mock_compilation_currency

def test_compilation_current(self):
    output_path = Path("compiled/graph.pkl")
    csv_path = Path("graphs/workflow.csv")
    
    # Test current compilation (compiled file newer than CSV)
    with mock_compilation_currency(output_path, csv_path, is_current=True):
        result = self.service._is_compilation_current("graph", csv_path)
        self.assertTrue(result)

def test_compilation_outdated(self):
    output_path = Path("compiled/graph.pkl") 
    csv_path = Path("graphs/workflow.csv")
    
    # Test outdated compilation (CSV newer than compiled file)
    with mock_compilation_currency(output_path, csv_path, is_current=False):
        result = self.service._is_compilation_current("graph", csv_path)
        self.assertFalse(result)
```

### 4. Complex Scenarios with Fluent Interface
```python
from tests.utils.path_mocking_utils import PathOperationsMocker

def test_complex_path_operations(self):
    with PathOperationsMocker() as path_mock:
        # Chain multiple operations
        (path_mock
         .set_exists("/file1.txt", True)
         .set_exists("/file2.txt", False)
         .set_stat("/file1.txt", 1642000000)
         .set_file_newer_than("/newer.txt", "/older.txt"))
        
        # Test code using multiple paths
```

### 5. Time Progression Mocking
```python
from tests.utils.path_mocking_utils import mock_time_progression

def test_compilation_timing(self):
    with mock_time_progression(start_time=0.0, increment=0.1):
        # time.time() will return 0.0, 0.1, 0.2, ... on successive calls
        result = self.service.compile_graph("test_graph")
        self.assertGreater(result.compilation_time, 0)
```

### 6. Mock Service Enhancement
```python
from tests.utils.path_mocking_utils import MockServiceConfigHelper

def setUp(self):
    # Create mock service as usual
    self.mock_app_config_service = MockServiceFactory.create_mock_app_config_service({
        "csv_path": "graphs/workflow.csv",
        "compiled_graphs_path": "compiled"
    })
    
    # Enhance with proper Path property support
    MockServiceConfigHelper.configure_app_config_service(
        self.mock_app_config_service, 
        {
            "csv_path": "graphs/workflow.csv",
            "compiled_graphs_path": "compiled", 
            "functions_path": "functions"
        }
    )
```

## Migration Examples

### Before (Problematic)
```python
def test_get_compilation_status_compiled_current(self):
    with patch.object(output_path, 'exists', return_value=True), \
         patch.object(csv_path, 'exists', return_value=True):  # ❌ Fails!
        # test code
```

### After (Working)
```python
def test_get_compilation_status_compiled_current(self):
    with PathOperationsMocker() as path_mock:
        path_mock.set_exists(output_path, True).set_exists(csv_path, True)
        # test code
```

### Before (Complex Setup)
```python
def test_outdated_compilation(self):
    def mock_stat_side_effect(self):
        mock_stat_result = Mock()
        if "output.pkl" in str(self):
            mock_stat_result.st_mtime = 1641000000  # Older
        else:
            mock_stat_result.st_mtime = 1642000000  # Newer
        return mock_stat_result
    
    with patch('pathlib.Path.stat', side_effect=mock_stat_side_effect):
        # test code
```

### After (Simple)
```python
def test_outdated_compilation(self):
    with mock_compilation_currency(output_path, csv_path, is_current=False):
        # test code
```

## Anti-Patterns to Avoid

### ❌ Don't: Direct attribute assignment
```python
path.exists = Mock(return_value=True)  # Read-only attribute error
```

### ❌ Don't: Complex manual side_effect functions
```python
def complex_side_effect(self):
    # Lots of path string manipulation logic
    pass
```

### ❌ Don't: patch.object on Path instances  
```python
patch.object(specific_path_instance, 'exists', ...)  # Fails
```

### ✅ Do: Use the utilities
```python
with PathOperationsMocker() as path_mock:
    path_mock.set_exists(path, True)
```

## Integration with Existing Tests

These utilities are designed to work seamlessly with:
- MockServiceFactory patterns
- unittest.TestCase classes
- pytest fixtures
- Existing patch() decorators and context managers

## Performance Notes

- The utilities use global patching which is slightly slower than direct mocking
- For performance-critical tests, consider batching path operations
- The fluent interface creates minimal overhead

## Troubleshooting

### Issue: Mock not working
**Check**: Are you using the correct path strings? Utilities normalize to string comparison.

### Issue: Unexpected exists() behavior
**Check**: Default existence is False. Explicitly set all paths you need.

### Issue: Time progression not working
**Check**: Make sure you're importing time correctly and not using datetime.

### Issue: Mock service properties not working
**Check**: Use MockServiceConfigHelper.configure_app_config_service() to set both method and property access.
"""