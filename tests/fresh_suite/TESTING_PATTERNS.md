# Testing Patterns for AgentMap

This document outlines established testing patterns and utilities for the AgentMap project, combining proven Pure Mock patterns with new centralized Path mocking utilities.

## Core Principles

- ✅ Use pure `unittest.Mock` objects instead of custom mock classes
- ✅ Leverage `MockServiceFactory` for consistent service mocking
- ✅ Focus on interface testing with realistic behavior
- ✅ Use real DI container (not mocked) for container tests
- ✅ **Use centralized Path mocking utilities** (prevents recurring test failures)
- ✅ Follow standard Python testing conventions
- ✅ Focus on actual method interfaces (use service interface auditor)

## Configuration Architecture (CRITICAL)

- **ConfigService**: Pure infrastructure (YAML loading only)
- **AppConfigService**: Domain logic with defaults merging
- **StorageConfigService**: Fail-fast, no defaults

---

## 1. Pure Mock Object Architecture

### The MockServiceFactory Approach

Replace custom mock classes with pure Mock objects using our centralized factory:

```python
from tests.utils.mock_service_factory import MockServiceFactory

# ✅ NEW: Pure Mock objects
mock_logging = MockServiceFactory.create_mock_logging_service()
mock_config = MockServiceFactory.create_mock_app_config_service()
mock_registry = MockServiceFactory.create_mock_node_registry_service()
```

### ❌ Old Hybrid Approach (DON'T USE)
```python
# ❌ OLD: Custom mock classes + patching
from agentmap.migration_utils import MockLoggingService
from unittest.mock import patch

@patch('agentmap.services.some_service.LoggingService')
def test_with_patch(self, mock_logging_class):
    mock_logging_class.return_value = MockLoggingService()
    # Complex patching logic...
```

---

## 2. Service Test Template

### Complete Test Class Structure

```python
import unittest
from unittest.mock import Mock
from agentmap.services.my_service import MyService
from tests.utils.mock_service_factory import MockServiceFactory
from tests.utils.path_mocking_utils import MockServiceConfigHelper


class TestMyService(unittest.TestCase):
    """Unit tests for MyService using pure Mock objects."""
    
    def setUp(self):
        """Set up test fixtures with pure Mock dependencies."""
        # Use MockServiceFactory for consistent behavior
        self.mock_app_config_service = MockServiceFactory.create_mock_app_config_service({
            "my_config": {
                "enabled": True,
                "timeout": 30
            }
        })
        
        # Enhance with proper Path property support (NEW)
        MockServiceConfigHelper.configure_app_config_service(
            self.mock_app_config_service, 
            {
                "csv_path": "graphs/workflow.csv",
                "compiled_graphs_path": "compiled",
                "functions_path": "functions"
            }
        )
        
        # Create mock logging service
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        
        # Create service instance with mocked dependencies
        self.service = MyService(
            app_config_service=self.mock_app_config_service,
            logging_service=self.mock_logging_service
        )
        
        # Get the mock logger for verification
        self.mock_logger = self.service.logger
    
    def test_service_initialization(self):
        """Test that service initializes correctly with all dependencies."""
        # Verify all dependencies are stored
        self.assertEqual(self.service.config, self.mock_app_config_service)
        self.assertEqual(self.service.logging_service, self.mock_logging_service)
        
        # Verify logger is configured
        self.assertIsNotNone(self.service.logger)
        self.assertEqual(self.service.logger.name, "MyService")
        
        # Verify initialization log message using call tracking
        logger_calls = self.mock_logger.calls
        self.assertTrue(any(call[1] == "[MyService] Initialized" 
                          for call in logger_calls if call[0] == "info"))
```

---

## 3. Path Mocking Utilities (NEW - RECOMMENDED)

**Problem**: Path.exists and Path.stat are read-only properties and cannot be mocked directly.

**Solution**: Use the centralized path mocking utilities in `tests.utils.path_mocking_utils`.

### 3.1 Quick Examples:

```python
from tests.utils.path_mocking_utils import PathOperationsMocker, mock_compilation_currency

# Simple path operations
def test_file_operations(self):
    with PathOperationsMocker() as path_mock:
        path_mock.set_exists("/file.txt", True)
        path_mock.set_stat("/file.txt", 1642000000)
        # test code

# Compilation currency scenarios (most common)
def test_compilation_status(self):
    with mock_compilation_currency(output_path, csv_path, is_current=True):
        # test code that checks if compilation is current
```

### 3.2 Available Utilities:

```python
# Import the utilities
from tests.utils.path_mocking_utils import (
    PathOperationsMocker,          # Full-featured with fluent interface  
    mock_compilation_currency,     # For compilation scenarios (most common)
    mock_path_exists,             # Simple existence mocking
    mock_time_progression,        # For timing tests
    MockServiceConfigHelper       # Enhanced mock service configuration
)
```

### 3.3 Common Use Cases:

#### Compilation Currency (80% of cases)
```python
def test_compilation_current(self):
    """Test when compiled file is newer than CSV."""
    with mock_compilation_currency(output_path, csv_path, is_current=True):
        result = self.service._is_compilation_current(graph_name, csv_path)
        self.assertTrue(result)

def test_compilation_outdated(self):
    """Test when CSV is newer than compiled file."""
    with mock_compilation_currency(output_path, csv_path, is_current=False):
        result = self.service._is_compilation_current(graph_name, csv_path)
        self.assertFalse(result)
```

#### Complex Multi-Path Scenarios
```python
def test_multiple_paths(self):
    """Test service behavior when files exist vs don't exist."""
    with PathOperationsMocker() as path_mock:
        (path_mock
         .set_exists("/existing/file.txt", True)
         .set_exists("/missing/file.txt", False)
         .set_stat("/existing/file.txt", 1642000000))
        
        # Test both scenarios
        result = self.service.process_files()
        self.assertEqual(result.found_files, 1)
```

#### Time Progression for Timing Tests
```python
def test_compilation_timing(self):
    """Test compilation timing measurement."""
    from tests.utils.path_mocking_utils import mock_time_progression
    
    with mock_time_progression(start_time=0.0, increment=0.1):
        # time.time() returns 0.0, 0.1, 0.2, ... on successive calls
        result = self.service.compile_graph("test_graph")
        self.assertGreater(result.compilation_time, 0)
```

### 3.4 Manual Path Mocking (Fallback)

If you need custom behavior not covered by the utilities:

```python
def test_custom_path_behavior(self):
    """Test with custom Path mocking logic."""
    def mock_exists(path_self):
        path_str = str(path_self)
        if "compiled" in path_str:
            return False  # No compiled files
        elif "source" in path_str:
            return True   # Source files exist
        else:
            return False
    
    with patch('pathlib.Path.exists', side_effect=mock_exists):
        result = self.service.resolve_execution_path("test_graph")
        self.assertEqual(result.execution_type, "from_source")
```

**See**: `tests/utils/PATH_MOCKING_GUIDE.md` for comprehensive usage examples.

---

## 4. MockServiceFactory Usage Patterns

### 4.1 Logging Service Mocking

```python
# Basic logging service mock
mock_logging = MockServiceFactory.create_mock_logging_service()

# Access the mock logger for verification
service = MyService(logging_service=mock_logging)
mock_logger = service.logger

# Verify log calls using call tracking
logger_calls = mock_logger.calls
assert ("info", "[MyService] Started", (), {}) in logger_calls
```

### 4.2 App Config Service Mocking

```python
# Mock with default configuration
mock_config = MockServiceFactory.create_mock_app_config_service()

# Mock with custom configuration overrides
config_overrides = {
    "tracking": {"enabled": False},
    "execution": {"timeout": 60}
}
mock_config = MockServiceFactory.create_mock_app_config_service(config_overrides)

# Enhance with Path property support (NEW)
MockServiceConfigHelper.configure_app_config_service(
    mock_config,
    {
        "csv_path": "graphs/workflow.csv",
        "compiled_graphs_path": "compiled",
        "functions_path": "functions"
    }
)

# Test configuration access
tracking_config = mock_config.get_tracking_config()
assert not tracking_config["enabled"]
```

### 4.3 Configuration Flexibility

#### Dynamic Configuration Changes
```python
def test_configuration_changes(self):
    """Test service behavior with different configurations."""
    # Test with tracking enabled
    self.mock_app_config_service.get_tracking_config.return_value = {
        "enabled": True,
        "track_inputs": True
    }
    
    tracker1 = self.service.create_tracker()
    self.assertTrue(tracker1.track_inputs)
    
    # Change configuration for next call
    self.mock_app_config_service.get_tracking_config.return_value = {
        "enabled": False,
        "track_inputs": False
    }
    
    tracker2 = self.service.create_tracker()
    self.assertFalse(tracker2.track_inputs)
```

#### Side Effect Override Patterns
```python
def test_config_value_override(self):
    """Test service with overridden configuration values."""
    # ✅ CORRECT: Override the side_effect function
    def mock_get_value(key: str, default: Any = None) -> Any:
        if key == "autocompile":
            return True  # Override specific key
        if key == "timeout":
            return 60    # Override another key
        return default   # Use default for other keys
    
    self.mock_app_config_service.get_value.side_effect = mock_get_value
    
    # Now the service will get the overridden values
    options = self.service.get_default_options()
    self.assertTrue(options.autocompile)
```

---

## 5. Advanced Testing Patterns

### 5.1 Exception Testing

```python
def test_exception_handling(self):
    """Test service exception handling."""
    # Configure mock to raise exception
    self.mock_config_service.get_critical_config.side_effect = KeyError("missing_key")
    
    # Test exception handling
    with self.assertRaises(ConfigurationError):
        self.service.initialize_critical_component()
    
    # Verify error logging
    logger_calls = self.mock_logger.calls
    error_calls = [call for call in logger_calls if call[0] == "error"]
    self.assertTrue(len(error_calls) > 0)
    self.assertTrue(any("missing_key" in call[1] for call in error_calls))
```

### 5.2 Multiple Service Dependencies

```python
def test_multiple_service_interactions(self):
    """Test service with multiple mock dependencies."""
    # Create multiple mock services
    mock_storage = MockServiceFactory.create_mock_storage_service()
    mock_llm = MockServiceFactory.create_mock_llm_service()
    
    # Configure coordinated behavior
    mock_storage.get_data.return_value = {"input": "test_data"}
    mock_llm.process.return_value = {"output": "processed_data"}
    
    # Test coordinated behavior
    result = service.process_workflow()
    
    # Verify interactions
    mock_storage.get_data.assert_called_once()
    mock_llm.process.assert_called_once_with({"input": "test_data"})
    self.assertEqual(result["output"], "processed_data")
```

### 5.3 Stateful Mock Behavior

```python
def test_stateful_mock_behavior(self):
    """Test mock with stateful behavior using closures."""
    # Create stateful mock using closure
    call_count = 0
    
    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return f"call_{call_count}"
    
    self.mock_service.process.side_effect = side_effect
    
    # Each call returns different value
    result1 = self.service.process_data("data1")
    result2 = self.service.process_data("data2")
    
    self.assertEqual(result1, "call_1")
    self.assertEqual(result2, "call_2")
```

---

## 6. CLI Testing Patterns

### 6.1 CLI Test Base Class Pattern

```python
from tests.fresh_suite.cli.base_cli_test import BaseCLITest
from typer.testing import CliRunner
from agentmap.core.cli.main_cli import app

class TestMyCommand(BaseCLITest):
    """Test CLI command using established patterns."""
    
    def test_command_success(self):
        """Test successful command execution."""
        # Create test files
        csv_file = self.create_test_csv_file()
        
        # Create mock container
        mock_container = self.create_mock_container()
        
        # Execute CLI command with mocked services
        with self.patch_container_creation(mock_container):
            result = self.run_cli_command(["my-command", "--option", "value"])
        
        # Verify success
        self.assert_cli_success(result, ["✅", "Success message"])
        
        # Verify service delegation
        self.assert_service_called(self.mock_service, "method_name")
```

### 6.2 CLI Service Integration Testing

```python
def test_cli_service_integration(self):
    """Test CLI command properly integrates with services."""
    csv_file = self.create_test_csv_file()
    
    # Configure service behavior
    mock_result = Mock(success=True, data="output")
    self.mock_graph_runner_service.run_graph.return_value = mock_result
    
    mock_container = self.create_mock_container()
    mock_adapter = self.create_adapter_mock()
    
    # Execute with proper service mocking
    with self.patch_container_creation(mock_container), \
         patch('agentmap.core.cli.run_commands.create_service_adapter', return_value=mock_adapter):
        
        result = self.run_cli_command(["run", "--graph", "test_graph"])
    
    # Verify proper delegation chain
    self.assert_cli_success(result)
    mock_adapter.initialize_services.assert_called_once()
    self.mock_graph_runner_service.run_graph.assert_called_once()
```

---

## 7. Migration Guide: Old → New

### 7.1 Import Changes

```python
# ❌ OLD: Custom mock classes
from agentmap.migration_utils import (
    MockLoggingService,
    MockAppConfigService,
    MockNodeRegistryService
)

# ✅ NEW: Pure Mock factory + Path utilities
from tests.utils.mock_service_factory import MockServiceFactory
from tests.utils.path_mocking_utils import (
    PathOperationsMocker,
    mock_compilation_currency,
    MockServiceConfigHelper
)
```

### 7.2 Setup Method Changes

```python
# ❌ OLD: Custom mock class instances
def setUp(self):
    self.mock_logging_service = MockLoggingService()
    self.mock_config_service = MockAppConfigService(config_overrides)

# ✅ NEW: Factory-created pure Mocks with Path support
def setUp(self):
    self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
    self.mock_config_service = MockServiceFactory.create_mock_app_config_service(config_overrides)
    
    # Enhance with Path property support
    MockServiceConfigHelper.configure_app_config_service(
        self.mock_config_service,
        {"csv_path": "graphs/workflow.csv", "compiled_graphs_path": "compiled"}
    )
```

### 7.3 Path Mocking Changes

```python
# ❌ OLD: Direct attribute assignment (fails)
output_path.exists = Mock(return_value=True)  # AttributeError!

# ❌ OLD: Complex manual side_effect functions
def complex_side_effect(self):
    # lots of string manipulation...

# ✅ NEW: Use Path utilities
from tests.utils.path_mocking_utils import PathOperationsMocker
with PathOperationsMocker() as path_mock:
    path_mock.set_exists(output_path, True)

# ✅ NEW: Use convenience functions for common scenarios
with mock_compilation_currency(output_path, csv_path, is_current=True):
    # test code
```

---

## 8. Anti-Patterns to Avoid

### ❌ Path Mocking Anti-Patterns
```python
# DON'T: Direct attribute assignment (fails)
output_path.exists = Mock(return_value=True)  # AttributeError!

# DON'T: patch.object on Path instances (fails) 
with patch.object(output_path, 'exists', return_value=True):  # AttributeError!

# DON'T: Complex manual side_effect functions
def complex_mock_exists(self):
    # lots of string manipulation...
```

### ❌ General Anti-Patterns
- Don't create missing modules to make tests pass
- Don't test business logic in model tests
- Don't mock the DI container in container tests
- Don't add business logic to ConfigService
- Don't create a new test to see if a failed test passes. Just run the failing test.

### ❌ Configuration Anti-Patterns
- Don't add business logic to ConfigService (pure infrastructure only)
- Don't create defaults in StorageConfigService (fail-fast only)

---

## 9. Troubleshooting Common Issues

### 9.1 Path Mocking Issues

#### Issue: "Still getting file not found errors"
**Solution**: Use the centralized utilities:
```python
# ✅ CORRECT
from tests.utils.path_mocking_utils import mock_path_exists
with mock_path_exists({"/file.txt": True}):
    # Path.exists() calls are properly intercepted
```

#### Issue: "AttributeError: 'WindowsPath' object attribute 'exists' is read-only"
**Solution**: You're trying to mock directly. Use utilities instead:
```python
# ❌ WRONG
path.exists = Mock(return_value=True)

# ✅ CORRECT
from tests.utils.path_mocking_utils import PathOperationsMocker
with PathOperationsMocker() as path_mock:
    path_mock.set_exists(path, True)
```

### 9.2 Mock Call Verification Failures

```python
# ❌ Problem: Incorrect call verification
mock_service.method.assert_called_with("wrong_args")  # AssertionError

# ✅ Solution: Debug actual calls
print(mock_service.method.call_args_list)  # See actual calls
mock_service.method.assert_called_with("correct_args")

# Alternative: Use any() for flexible verification
calls = mock_service.method.call_args_list
self.assertTrue(any("expected_substring" in str(call) for call in calls))
```

### 9.3 Configuration Override Issues

```python
# ❌ Problem: return_value doesn't work with MockServiceFactory
self.mock_config_service.get_value.return_value = True  # Ignored due to side_effect

# ✅ Solution: Override the side_effect function
def mock_get_value(key: str, default: Any = None) -> Any:
    if key == "special_key":
        return True
    return default

self.mock_config_service.get_value.side_effect = mock_get_value
```

---

## 10. Testing Best Practices

### 10.1 Test Organization

```python
class TestMyService(unittest.TestCase):
    """Organize tests by functionality, not implementation."""
    
    # =============================================================================
    # 1. Service Initialization Tests
    # =============================================================================
    
    def test_service_initialization(self):
        """Test service initializes with dependencies."""
        pass
    
    # =============================================================================
    # 2. Core Business Logic Tests  
    # =============================================================================
    
    def test_process_data_success(self):
        """Test successful data processing."""
        pass
    
    # =============================================================================
    # 3. Path Operations Tests (with utilities)
    # =============================================================================
    
    def test_file_operations(self):
        """Test file operations using Path utilities."""
        with mock_compilation_currency(output_path, csv_path, is_current=True):
            # test code
```

### 10.2 Test Execution

After completing a unit test, always verify:
1. Run the specific test to ensure it passes
2. Run the entire test file to check for side effects
3. Ask for confirmation that all tests pass before proceeding

### 10.3 Realistic Test Data

```python
def test_with_realistic_data(self):
    """Test with realistic data scenarios."""
    # Use realistic configuration
    realistic_config = {
        "execution": {"timeout": 300, "max_retries": 3},
        "tracking": {"enabled": True, "track_inputs": True}
    }
    
    self.mock_config_service.get_execution_config.return_value = realistic_config["execution"]
    
    # Use realistic Path scenarios
    with mock_compilation_currency(
        Path("compiled/customer_onboarding_workflow.pkl"),
        Path("graphs/customer_workflows.csv"),
        is_current=True
    ):
        result = self.service.process_workflow(realistic_config)
        self.assertIsNotNone(result)
```

---

## 11. Quick Reference

### 11.1 Essential Imports
```python
import unittest
from unittest.mock import Mock, patch
from tests.utils.mock_service_factory import MockServiceFactory
from tests.utils.path_mocking_utils import (
    PathOperationsMocker,
    mock_compilation_currency,
    mock_path_exists,
    mock_time_progression,
    MockServiceConfigHelper
)
```

### 11.2 Common Test Scenarios

#### Service Initialization
```python
def test_service_initialization(self):
    # Verify dependencies, logger, initialization messages
```

#### Configuration Access
```python
def test_configuration_access(self):
    # Mock config service, test config retrieval
```

#### File Operations
```python
def test_file_operations(self):
    with mock_compilation_currency(output_path, csv_path, is_current=True):
        # Test file-based operations
```

#### Exception Handling
```python
def test_exception_handling(self):
    # Configure mock to raise exception, verify graceful handling
```

#### Timing Operations
```python
def test_timing(self):
    with mock_time_progression(start_time=0.0, increment=0.1):
        # Test operations that measure time
```

---

## 12. Resources

- **Path Mocking Guide**: `tests/utils/PATH_MOCKING_GUIDE.md`
- **Mock Services**: `tests/utils/mock_service_factory.py`
- **Service Auditing**: `tests/utils/service_interface_auditor.py`
- **CLI Testing**: `tests/fresh_suite/cli/base_cli_test.py`
- **Examples**: `tests/utils/PATH_MOCKING_EXAMPLES.py`

---

## 13. Summary

**Key Benefits of This Testing Approach:**
- ✅ Standard Python testing patterns with centralized utilities
- ✅ Elimination of read-only Path attribute errors
- ✅ Consistent behavior across all tests
- ✅ Better IDE support and debugging
- ✅ Cleaner, more maintainable tests
- ✅ Proven patterns that prevent recurring issues

**Migration Checklist:**
- [ ] Replace `migration_utils` imports with `MockServiceFactory`
- [ ] Add Path mocking utilities imports
- [ ] Update `setUp()` methods to use factory methods + Path utilities
- [ ] Replace direct Path attribute assignments with utilities
- [ ] Use `MockServiceConfigHelper.configure_app_config_service()`
- [ ] Verify logging call tracking still works
- [ ] Test configuration override patterns
- [ ] Remove @patch decorators where possible

**Remember**: The goal is clean, maintainable tests that focus on interface behavior rather than implementation details. The combination of Pure Mock objects and centralized Path utilities provides the flexibility and standard patterns needed for robust test suites without recurring technical issues.

---

*This guide represents the established patterns for AgentMap's fresh test suite. Follow these patterns for consistency and maintainability across all service tests.*
