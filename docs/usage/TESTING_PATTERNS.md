# Fresh Test Suite Testing Patterns Guide

## Overview

This guide documents the **pure Mock testing patterns** used in AgentMap's fresh test suite. These patterns replace the hybrid approach (custom mock classes + @patch decorators) with clean, standard Python testing using `unittest.Mock` objects.

**Key Principles:**
- ✅ Use pure `unittest.Mock` objects instead of custom mock classes
- ✅ Leverage `MockServiceFactory` for consistent service mocking
- ✅ Focus on interface testing with realistic behavior
- ✅ Eliminate @patch decorators in favor of dependency injection
- ✅ Follow standard Python testing conventions
- ✅ **Use proper Path/filesystem mocking patterns** (prevents recurring test failures)

---

## 1. Pure Mock Object Architecture

### The New Approach: MockServiceFactory

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
    
    def test_method_with_config_access(self):
        """Test method that accesses configuration."""
        # Configure specific return value for this test
        self.mock_app_config_service.get_my_config.return_value = {
            "enabled": True,
            "timeout": 60
        }
        
        # Execute method
        result = self.service.process_with_config()
        
        # Verify config method was called
        self.mock_app_config_service.get_my_config.assert_called_once()
        
        # Verify result based on configured behavior
        self.assertTrue(result)
    
    def test_method_with_logging(self):
        """Test method that performs logging."""
        # Execute method
        self.service.do_something("test_input")
        
        # Verify logging behavior using call tracking
        logger_calls = self.mock_logger.calls
        expected_calls = [
            ("info", "[MyService] Starting process with: test_input"),
            ("debug", "[MyService] Process completed successfully")
        ]
        
        for expected_call in expected_calls:
            self.assertTrue(any(call == expected_call for call in logger_calls))
    
    def test_error_handling_with_logging(self):
        """Test error handling and error logging."""
        # Configure mock to raise exception
        self.mock_app_config_service.get_my_config.side_effect = Exception("Config error")
        
        # Execute method that should handle error
        with self.assertRaises(Exception):
            self.service.process_with_config()
        
        # Verify error was logged
        logger_calls = self.mock_logger.calls
        self.assertTrue(any("Error" in call[1] for call in logger_calls 
                          if call[0] == "error"))
```

---

## 3. MockServiceFactory Usage Patterns

### 3.1 Logging Service Mocking

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

### 3.2 App Config Service Mocking

```python
# Mock with default configuration
mock_config = MockServiceFactory.create_mock_app_config_service()

# Mock with custom configuration overrides
config_overrides = {
    "tracking": {"enabled": False},
    "execution": {"timeout": 60}
}
mock_config = MockServiceFactory.create_mock_app_config_service(config_overrides)

# Test configuration access
tracking_config = mock_config.get_tracking_config()
assert not tracking_config["enabled"]
```

### 3.3 Node Registry Service Mocking

```python
# Create mock with realistic behavior
mock_registry = MockServiceFactory.create_mock_node_registry_service()

# Test node registration (actually stores the data)
mock_registry.register_node("test_node", {"type": "processor"})
node_data = mock_registry.get_node("test_node")
assert node_data["type"] == "processor"

# Test node listing
nodes = mock_registry.list_nodes()
assert "test_node" in nodes
```

---

## 4. Configuration Flexibility

### 4.1 Dynamic Configuration Changes

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
    
    # Verify both calls were made
    self.assertEqual(self.mock_app_config_service.get_tracking_config.call_count, 2)
```

### 4.2 Side Effect Override Patterns

```python
def test_config_value_override(self):
    """Test service with overridden configuration values."""
    # ❌ WRONG: This won't work with MockServiceFactory app config
    # The factory uses side_effect, so return_value is ignored
    self.mock_app_config_service.get_value.return_value = True
    
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

### 4.3 Multiple Configuration Scenarios

```python
def test_multiple_configuration_scenarios(self):
    """Test service behavior with different configuration scenarios."""
    scenarios = [
        {"autocompile": True, "timeout": 30, "expected_behavior": "fast_compile"},
        {"autocompile": False, "timeout": 60, "expected_behavior": "no_compile"},
        {"autocompile": True, "timeout": 120, "expected_behavior": "slow_compile"}
    ]
    
    for scenario in scenarios:
        with self.subTest(scenario=scenario):
            # Configure mock for this scenario
            def mock_get_value(key: str, default: Any = None) -> Any:
                return scenario.get(key, default)
            
            self.mock_app_config_service.get_value.side_effect = mock_get_value
            
            # Test behavior for this configuration
            result = self.service.process_with_config()
            self.assertEqual(result.behavior, scenario["expected_behavior"])
```

### 4.4 Side Effects for Multiple Calls

```python
def test_multiple_calls_with_side_effects(self):
    """Test service with different behavior on subsequent calls."""
    # Configure side effects for multiple calls
    self.mock_app_config_service.get_execution_config.side_effect = [
        {"timeout": 30},  # First call
        {"timeout": 60},  # Second call
        {"timeout": 90}   # Third call
    ]
    
    # Each call gets different config
    config1 = self.service.get_execution_timeout()
    config2 = self.service.get_execution_timeout() 
    config3 = self.service.get_execution_timeout()
    
    self.assertEqual(config1, 30)
    self.assertEqual(config2, 60)
    self.assertEqual(config3, 90)
```

---

## 5. Migration Guide: Old → New

### 5.1 Import Changes

```python
# ❌ OLD: Custom mock classes
from agentmap.migration_utils import (
    MockLoggingService,
    MockAppConfigService,
    MockNodeRegistryService
)

# ✅ NEW: Pure Mock factory
from tests.utils.mock_service_factory import MockServiceFactory
```

### 5.2 Setup Method Changes

```python
# ❌ OLD: Custom mock class instances
def setUp(self):
    self.mock_logging_service = MockLoggingService()
    self.mock_config_service = MockAppConfigService(config_overrides)

# ✅ NEW: Factory-created pure Mocks
def setUp(self):
    self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
    self.mock_config_service = MockServiceFactory.create_mock_app_config_service(config_overrides)
```

### 5.3 Verification Changes

```python
# ❌ OLD: Direct access to custom logger
def test_logging(self):
    # MockLoggingService creates MockLogger instances
    logger_calls = self.service.logger.calls
    self.assertTrue(any(call[1] == "Expected message" for call in logger_calls))

# ✅ NEW: Same pattern but with pure Mocks
def test_logging(self):
    # MockServiceFactory creates Mock loggers with same interface
    logger_calls = self.mock_logger.calls
    self.assertTrue(any(call[1] == "Expected message" for call in logger_calls))
```

---

## 6. Mock vs MagicMock Guidelines

### 6.1 When to Use Mock (Recommended)

```python
# ✅ Use Mock for most service dependencies
mock_service = Mock()
mock_service.get_config.return_value = {"enabled": True}
mock_service.process_data.return_value = "processed"

# Good for:
# - Service interfaces with known methods
# - Configuration services
# - Simple return value mocking
```

### 6.2 When to Use MagicMock

```python
from unittest.mock import MagicMock

# Use MagicMock when you need magic method support
mock_container = MagicMock()
# Supports: __getitem__, __setitem__, __contains__, etc.
mock_container["service_name"] = mock_service
assert "service_name" in mock_container

# Good for:
# - Container-like objects
# - Objects that need __getitem__, __setitem__
# - Complex iteration or subscription operations
```

### 6.3 MockServiceFactory Default Choice

```python
# MockServiceFactory uses Mock by default (not MagicMock)
# This is intentional for better error detection and cleaner tests

mock_service = MockServiceFactory.create_mock_logging_service()
# Returns Mock, not MagicMock

# If you need MagicMock behavior, override specific methods:
mock_service.__getitem__ = Mock(return_value="value")
```

---

## 7. Advanced Patterns

### 7.1 Stateful Mock Behavior

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

### 7.2 Exception Testing

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

### 7.3 Multiple Service Dependencies

```python
def test_multiple_service_interactions(self):
    """Test service with multiple mock dependencies."""
    # Create multiple mock services
    mock_storage = MockServiceFactory.create_mock_storage_service()
    mock_llm = MockServiceFactory.create_mock_llm_service()
    
    # Configure coordinated behavior
    mock_storage.get_data.return_value = {"input": "test_data"}
    mock_llm.process.return_value = {"output": "processed_data"}
    
    # Create service with multiple dependencies
    service = ComplexService(
        app_config_service=self.mock_config_service,
        logging_service=self.mock_logging_service,
        storage_service=mock_storage,
        llm_service=mock_llm
    )
    
    # Test coordinated behavior
    result = service.process_workflow()
    
    # Verify interactions
    mock_storage.get_data.assert_called_once()
    mock_llm.process.assert_called_once_with({"input": "test_data"})
    self.assertEqual(result["output"], "processed_data")
```

---

## 8. Troubleshooting Common Issues

### 8.1 AttributeError: Mock object has no attribute 'X'

```python
# ❌ Problem: Accessing undefined mock attributes
mock_service = Mock()
result = mock_service.undefined_method()  # Returns another Mock
real_attribute = mock_service.real_attribute  # AttributeError if strict

# ✅ Solution: Configure mock properly
mock_service = Mock()
mock_service.get_config.return_value = {"enabled": True}
# Or use spec to restrict available attributes
mock_service = Mock(spec=RealService)
```

### 8.2 Mock Call Verification Failures

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

### 8.3 Side Effect Configuration Issues

```python
# ❌ Problem: Incorrect side effect setup
mock_service.method.side_effect = "not_callable"  # TypeError

# ✅ Solution: Use callable or iterable
mock_service.method.side_effect = lambda x: f"processed_{x}"
# Or use list for multiple calls
mock_service.method.side_effect = ["result1", "result2", "result3"]
```

### 8.4 MockServiceFactory Configuration

```python
# ❌ Problem: Expecting custom mock class behavior
mock_logging = MockServiceFactory.create_mock_logging_service()
logger = mock_logging.get_logger("test")
# logger is Mock, not custom MockLogger class

# ✅ Solution: Use call tracking attribute
logger_calls = logger.calls  # This attribute is configured by factory
self.assertTrue(("info", "message", (), {}) in logger_calls)
```

---

## 9. Testing Best Practices

### 9.1 Test Organization

```python
class TestMyService(unittest.TestCase):
    """Organize tests by functionality, not implementation."""
    
    # =============================================================================
    # 1. Service Initialization Tests
    # =============================================================================
    
    def test_service_initialization(self):
        """Test service initializes with dependencies."""
        pass
    
    def test_service_initialization_with_missing_dependencies(self):
        """Test service handles missing dependencies."""
        pass
    
    # =============================================================================
    # 2. Core Business Logic Tests  
    # =============================================================================
    
    def test_process_data_success(self):
        """Test successful data processing."""
        pass
    
    def test_process_data_failure(self):
        """Test data processing error handling."""
        pass
    
    # =============================================================================
    # 3. Configuration Integration Tests
    # =============================================================================
    
    def test_configuration_access(self):
        """Test service accesses configuration correctly."""
        pass
```

### 9.2 Mock Reset and Isolation

```python
def test_isolated_behavior(self):
    """Test with clean mock state."""
    # Reset mocks to ensure test isolation
    self.mock_config_service.reset_mock()
    self.mock_logging_service.reset_mock()
    
    # Test behavior
    self.service.perform_action()
    
    # Verify only expected calls were made
    self.mock_config_service.get_config.assert_called_once()
    self.assertEqual(self.mock_logging_service.get_class_logger.call_count, 0)
```

### 9.3 Realistic Test Data

```python
def test_with_realistic_data(self):
    """Test with realistic data scenarios."""
    # Use realistic configuration
    realistic_config = {
        "execution": {
            "timeout": 300,
            "max_retries": 3,
            "retry_delay": 1.0
        },
        "tracking": {
            "enabled": True,
            "track_inputs": True,
            "track_outputs": False
        }
    }
    
    self.mock_config_service.get_execution_config.return_value = realistic_config["execution"]
    self.mock_config_service.get_tracking_config.return_value = realistic_config["tracking"]
    
    # Test with realistic input data
    test_data = {
        "graph_name": "customer_onboarding_workflow",
        "initial_state": {"customer_id": "cust_12345", "account_type": "premium"},
        "node_inputs": {"validate_customer": {"strict_mode": True}}
    }
    
    result = self.service.process_workflow(test_data)
    self.assertIsNotNone(result)
```

---

## 10. Future Development Guidelines

### 10.1 Adding New Service Tests

When creating tests for new services:

1. **Use MockServiceFactory**: Always start with factory-created mocks
2. **Follow Template**: Use the established test class structure
3. **Test Interfaces**: Focus on public method interfaces, not implementation
4. **Document Patterns**: Add new patterns to this guide if needed

### 10.2 Extending MockServiceFactory

When adding new services to the factory:

```python
@staticmethod
def create_mock_new_service() -> Mock:
    """Create a pure Mock object for NewService."""
    mock_service = Mock()
    
    # Configure realistic default behavior
    mock_service.method_name.return_value = "default_value"
    mock_service.other_method.side_effect = lambda x: f"processed_{x}"
    
    return mock_service
```

### 10.3 Integration with Real Services

For integration tests, combine real services with minimal mocking:

```python
class TestServiceIntegration(unittest.TestCase):
    """Integration tests with real services and minimal mocking."""
    
    def setUp(self):
        # Use real config service with test configuration
        from agentmap.services.config.app_config_service import AppConfigService
        from agentmap.services.config.config_service import ConfigService
        
        config_service = ConfigService()
        config_service.load_config("tests/data/test_config.yaml")
        
        self.real_app_config = AppConfigService(config_service=config_service)
        
        # Mock only external dependencies
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        
        # Test with real + mock combination
        self.service = MyService(
            app_config_service=self.real_app_config,  # Real
            logging_service=self.mock_logging_service  # Mock
        )
```

---

## 11. Summary

**Key Benefits of Pure Mock Testing:**
- ✅ Standard Python testing patterns
- ✅ Better IDE support and debugging
- ✅ Cleaner, more maintainable tests
- ✅ Elimination of custom mock class maintenance
- ✅ Consistent behavior across all tests
- ✅ Easier refactoring and updates

**Migration Checklist:**
- [ ] Replace `migration_utils` imports with `MockServiceFactory`
- [ ] Update `setUp()` methods to use factory methods
- [ ] Verify logging call tracking still works
- [ ] Test configuration override patterns
- [ ] Remove @patch decorators where possible
- [ ] Update test documentation

**Remember:** The goal is clean, maintainable tests that focus on interface behavior rather than implementation details. Pure Mock objects provide the flexibility and standard patterns needed for robust test suites.

---

*This guide represents the established patterns for AgentMap's fresh test suite. Follow these patterns for consistency and maintainability across all service tests.*

---

## 12. Path and File System Mocking Patterns (CRITICAL)

### 12.1 The Path Mocking Problem

**This section addresses a recurring test failure pattern in AgentMap.** Many services create `Path` instances internally, which bypasses naive mocking attempts and causes tests to fail with "file not found" errors.

**Common Failure Pattern:**
```python
# Service does this internally:
def validate_csv_before_building(self, csv_path: Path) -> List[str]:
    csv_path = Path(csv_path)  # Creates new Path instance!
    
    if not csv_path.exists():  # Calls method on new instance
        return [f"CSV file not found: {csv_path}"]
    
    with csv_path.open() as f:  # Opens new instance
        # Process file...
```

**Why Basic Mocking Fails:**
```python
# ❌ WRONG: This doesn't work because service creates new Path instance
with unittest.mock.patch('pathlib.Path.exists', return_value=True):
    errors = service.validate_csv_before_building(Path('test.csv'))
    # FAILS: Still gets "file not found" error!
```

### 12.2 The Correct Solution: Service Module Patching

**Root Cause**: Services import `Path` at module level, then create new instances using that imported reference.

**Solution**: Patch the `Path` import in the specific service module:

```python
# ✅ CORRECT: Patch Path in the service module where it's imported
import unittest.mock
from unittest.mock import Mock, mock_open

def test_validate_csv_success(self):
    """Test CSV validation with proper Path mocking."""
    # Mock CSV content
    csv_content = "GraphName,Node,AgentType\ntest_graph,node1,default\n"
    
    # Create proper file mock
    mock_file = mock_open(read_data=csv_content)
    
    # Create mock Path instance
    mock_path = Mock()
    mock_path.exists.return_value = True
    mock_path.open = mock_file
    
    # Constructor function that always returns our mock
    def mock_path_constructor(*args, **kwargs):
        return mock_path
    
    # ✅ KEY: Patch Path in the SERVICE MODULE, not pathlib
    with unittest.mock.patch('agentmap.services.graph_builder_service.Path', 
                            side_effect=mock_path_constructor):
        errors = self.service.validate_csv_before_building(Path('test.csv'))
        self.assertEqual(errors, [])  # ✅ SUCCESS!
```

### 12.3 Essential Path Mocking Template

**Use this template for ANY service that works with files:**

```python
def test_method_with_file_operations(self):
    """Template for testing methods that use Path operations."""
    import unittest.mock
    
    # 1. Create test file content (if method reads files)
    file_content = "your,test,content\nrow1,value1,value2"
    mock_file = mock_open(read_data=file_content)
    
    # 2. Create mock Path instance with required behaviors
    mock_path = Mock()
    mock_path.exists.return_value = True  # File exists
    mock_path.open = mock_file            # File reading works
    # Add other Path methods as needed:
    # mock_path.is_file.return_value = True
    # mock_path.stat.return_value = Mock(st_mtime=1234567890)
    
    # 3. Create constructor function
    def mock_path_constructor(*args, **kwargs):
        return mock_path
    
    # 4. Patch Path in the SPECIFIC SERVICE MODULE
    with unittest.mock.patch('your.service.module.Path', 
                            side_effect=mock_path_constructor):
        # 5. Execute your test
        result = self.service.method_that_uses_files()
        
        # 6. Verify behavior
        self.assertEqual(result.status, "success")
        mock_path.exists.assert_called()  # Verify file check
```

### 12.4 Common Path Mocking Scenarios

#### Scenario 1: File Existence Checking
```python
def test_file_existence_behavior(self):
    """Test different file existence scenarios."""
    mock_path = Mock()
    
    def mock_path_constructor(*args, **kwargs):
        return mock_path
    
    with unittest.mock.patch('your.service.module.Path', 
                            side_effect=mock_path_constructor):
        
        # Test when file doesn't exist
        mock_path.exists.return_value = False
        result = self.service.process_file("missing.csv")
        self.assertEqual(result.error, "file_not_found")
        
        # Test when file exists
        mock_path.exists.return_value = True
        result = self.service.process_file("existing.csv")
        self.assertEqual(result.status, "success")
```

#### Scenario 2: File Reading with CSV Processing
```python
def test_csv_file_processing(self):
    """Test CSV file reading and processing."""
    csv_content = "Name,Age,City\nJohn,30,NYC\nJane,25,LA"
    mock_file = mock_open(read_data=csv_content)
    
    mock_path = Mock()
    mock_path.exists.return_value = True
    mock_path.open = mock_file
    
    def mock_path_constructor(*args, **kwargs):
        return mock_path
    
    with unittest.mock.patch('your.service.module.Path', 
                            side_effect=mock_path_constructor):
        result = self.service.load_csv_data("test.csv")
        
        self.assertEqual(len(result.rows), 2)
        self.assertEqual(result.rows[0]["Name"], "John")
        mock_path.open.assert_called_once()
```

#### Scenario 3: Multiple File Operations
```python
def test_multiple_file_operations(self):
    """Test service that works with multiple files."""
    # Different mock behavior for different file paths
    def mock_path_constructor(*args, **kwargs):
        path_str = str(args[0]) if args else "unknown"
        mock_path = Mock()
        
        if "config" in path_str:
            mock_path.exists.return_value = True
            mock_path.open = mock_open(read_data="config: value")
        elif "data" in path_str:
            mock_path.exists.return_value = True
            mock_path.open = mock_open(read_data="data,values\n1,2")
        else:
            mock_path.exists.return_value = False
        
        return mock_path
    
    with unittest.mock.patch('your.service.module.Path', 
                            side_effect=mock_path_constructor):
        result = self.service.load_config_and_data()
        self.assertTrue(result.config_loaded)
        self.assertTrue(result.data_loaded)
```

#### Scenario 4: File Writing Operations
```python
def test_file_writing(self):
    """Test service that writes files."""
    mock_path = Mock()
    mock_path.exists.return_value = False  # File doesn't exist yet
    mock_path.parent.mkdir = Mock()        # Parent directory creation
    
    # Mock the open for writing
    mock_file_handle = mock_open()
    mock_path.open = mock_file_handle
    
    def mock_path_constructor(*args, **kwargs):
        return mock_path
    
    with unittest.mock.patch('your.service.module.Path', 
                            side_effect=mock_path_constructor):
        self.service.save_results("output.json", {"key": "value"})
        
        # Verify file operations
        mock_path.parent.mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_path.open.assert_called_once_with('w')
        
        # Verify content was written
        written_content = mock_file_handle().write.call_args_list
        self.assertTrue(len(written_content) > 0)
```

### 12.5 Advanced Path Mocking Patterns

#### Pattern 1: Conditional File Existence
```python
def test_conditional_file_existence(self):
    """Test with different files existing/missing."""
    def mock_path_constructor(path_arg):
        mock_path = Mock()
        path_str = str(path_arg)
        
        # Configure different existence based on path
        if "compiled" in path_str:
            mock_path.exists.return_value = True   # Compiled files exist
        elif "source" in path_str:
            mock_path.exists.return_value = True   # Source files exist
        elif "temp" in path_str:
            mock_path.exists.return_value = False  # Temp files don't exist
        else:
            mock_path.exists.return_value = False  # Default: doesn't exist
        
        return mock_path
    
    with unittest.mock.patch('your.service.module.Path', 
                            side_effect=mock_path_constructor):
        result = self.service.resolve_execution_path("test_graph")
        self.assertEqual(result.path_type, "compiled")
```

#### Pattern 2: File Modification Time Mocking
```python
def test_file_modification_time(self):
    """Test service that checks file modification times."""
    import time
    
    mock_path = Mock()
    mock_path.exists.return_value = True
    
    # Mock file stats
    mock_stat = Mock()
    mock_stat.st_mtime = time.time() - 3600  # File modified 1 hour ago
    mock_path.stat.return_value = mock_stat
    
    def mock_path_constructor(*args, **kwargs):
        return mock_path
    
    with unittest.mock.patch('your.service.module.Path', 
                            side_effect=mock_path_constructor):
        result = self.service.check_if_rebuild_needed("source.csv", "compiled.pkl")
        self.assertTrue(result.rebuild_needed)
```

### 12.6 File System Error Handling

```python
def test_file_system_error_handling(self):
    """Test graceful handling of file system errors."""
    mock_path = Mock()
    mock_path.exists.return_value = True
    mock_path.open.side_effect = IOError("Permission denied")
    
    def mock_path_constructor(*args, **kwargs):
        return mock_path
    
    with unittest.mock.patch('your.service.module.Path', 
                            side_effect=mock_path_constructor):
        result = self.service.safe_file_operation("test.txt")
        
        # Service should handle error gracefully
        self.assertFalse(result.success)
        self.assertIn("Permission denied", result.error)
        
        # Should log the error
        logger_calls = self.mock_logger.calls
        error_calls = [call for call in logger_calls if call[0] == "error"]
        self.assertTrue(len(error_calls) > 0)
```

### 12.7 Troubleshooting Path Mocking Issues

#### Issue 1: "Still getting file not found errors"
**Cause**: Patching wrong module or wrong Path reference.
**Solution**: Find where Path is imported in your service:

```python
# In your service file, look for:
from pathlib import Path  # ← This is what you need to patch

# Then patch: 'your.exact.service.module.Path'
# NOT: 'pathlib.Path'
```

#### Issue 2: "Mock object has no attribute 'exists'"
**Cause**: Mock not properly configured.
**Solution**: Always configure required Path methods:

```python
mock_path = Mock()
mock_path.exists.return_value = True  # ✅ Always configure exists
mock_path.is_file.return_value = True # ✅ Configure other methods as needed
mock_path.is_dir.return_value = False
```

#### Issue 3: "Context manager error with open()"
**Cause**: `mock_open()` not used correctly.
**Solution**: Use `mock_open()` for file operations:

```python
# ✅ CORRECT
mock_file = mock_open(read_data="content")
mock_path.open = mock_file

# ❌ WRONG
mock_path.open.return_value = "content"  # Not a context manager
```

#### Issue 4: "Multiple Path() calls interfere with each other"
**Solution**: Use stateful constructor function:

```python
path_behaviors = {
    "file1.csv": {"exists": True, "content": "data1"},
    "file2.csv": {"exists": False, "content": ""}
}

def mock_path_constructor(path_arg):
    path_str = str(path_arg)
    behavior = path_behaviors.get(path_str, {"exists": False, "content": ""})
    
    mock_path = Mock()
    mock_path.exists.return_value = behavior["exists"]
    if behavior["content"]:
        mock_path.open = mock_open(read_data=behavior["content"])
    
    return mock_path
```

### 12.8 Path Mocking Checklist

Before writing Path-related tests, check:

- [ ] **Identified the correct service module** where Path is imported
- [ ] **Used `side_effect=mock_path_constructor`** not `return_value`
- [ ] **Configured `mock_path.exists.return_value`** appropriately
- [ ] **Used `mock_open(read_data=...)` for file reading**
- [ ] **Configured other Path methods** used by service (is_file, stat, etc.)
- [ ] **Tested both file exists and file missing scenarios**
- [ ] **Verified mock calls** with `assert_called()` methods

### 12.9 Quick Reference: Common Path Patches

```python
# GraphBuilderService
with unittest.mock.patch('agentmap.services.graph_builder_service.Path', side_effect=mock_constructor):

# CompilationService  
with unittest.mock.patch('agentmap.services.compilation_service.Path', side_effect=mock_constructor):

# StorageService
with unittest.mock.patch('agentmap.services.storage_service.Path', side_effect=mock_constructor):

# For services in subdirectories, use full path:
with unittest.mock.patch('agentmap.services.config.app_config_service.Path', side_effect=mock_constructor):
```

### 12.10 Path Mocking Best Practices

1. **Always patch the service module**, never `pathlib.Path` directly
2. **Use `side_effect` with constructor function** for flexibility
3. **Configure all Path methods** your service uses (`exists`, `open`, `is_file`, etc.)
4. **Use `mock_open()` for file content** with proper `read_data`
5. **Test both success and failure scenarios** (file exists/missing)
6. **Reset mocks between tests** to avoid state leakage
7. **Use descriptive test data** that matches expected file formats
8. **Verify file operations** with `assert_called()` methods

**Remember**: Path mocking issues are the #1 cause of recurring test failures in AgentMap. Follow these patterns consistently to avoid "file not found" test failures!

---

## 13. CLI Testing Patterns

### 13.1 CLI Test Suite Overview

The CLI test suite provides comprehensive testing for all AgentMap CLI commands using `typer.testing.CliRunner` and established mock patterns.

**Test Structure:**
```
tests/fresh_suite/cli/
├── base_cli_test.py              # Base classes and utilities
├── test_main_workflow_commands.py # run, compile, scaffold, export
├── test_validation_commands.py    # validate-csv, validate-config, validate-all
├── test_diagnostic_commands.py    # diagnose, config, validate-cache
├── test_cli_integration.py        # Cross-command workflows
├── test_cli_error_handling.py     # Error handling and edge cases
└── cli_test_runner.py             # Test runner with categories
```

### 13.2 CLI Test Base Class Pattern

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

### 13.3 CLI Service Integration Testing

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

### 13.4 CLI Error Handling Testing

```python
def test_cli_error_handling(self):
    """Test CLI graceful error handling."""
    # Configure service to fail
    self.configure_service_failure(
        self.mock_validation_service,
        "validate_csv",
        "Validation error"
    )
    
    mock_container = self.create_mock_container()
    
    with self.patch_container_creation(mock_container):
        result = self.run_cli_command(["validate-csv", "--csv", "test.csv"])
    
    # Verify graceful failure
    self.assert_cli_failure(result, expected_error_contains=["❌", "Validation error"])
    
    # Ensure no stack traces in user output
    self.assertNotIn("Traceback", result.stdout)
```

### 13.5 CLI Workflow Integration Testing

```python
def test_complete_cli_workflow(self):
    """Test end-to-end CLI workflow."""
    csv_file = self.create_test_csv_file()
    mock_container = self.create_mock_container()
    
    # Step 1: Validate
    with self.patch_container_creation(mock_container):
        validate_result = self.run_cli_command(["validate-csv", "--csv", str(csv_file)])
    self.assert_cli_success(validate_result)
    
    # Step 2: Compile
    with self.patch_container_creation(mock_container):
        compile_result = self.run_cli_command(["compile", "--graph", "test_graph"])
    self.assert_cli_success(compile_result)
    
    # Step 3: Run
    mock_adapter = self.create_adapter_mock()
    with self.patch_container_creation(mock_container), \
         patch('agentmap.core.cli.run_commands.create_service_adapter', return_value=mock_adapter):
        run_result = self.run_cli_command(["run", "--graph", "test_graph"])
    self.assert_cli_success(run_result)
    
    # Verify complete workflow executed
    self.mock_validation_service.validate_csv.assert_called()
    self.mock_graph_compilation_service.compile_graph.assert_called()
    self.mock_graph_runner_service.run_graph.assert_called()
```

### 13.6 CLI Test Utilities and Helpers

```python
# Available utility methods from BaseCLITest:

# File creation
csv_file = self.create_test_csv_file("custom.csv", custom_content)
config_file = self.create_test_config_file("config.yaml", config_data)

# Command execution
result = self.run_cli_command(["command", "--option", "value"])

# Assertions
self.assert_cli_success(result, ["expected", "strings"])
self.assert_cli_failure(result, expected_exit_code=1)
self.assert_service_called(mock_service, "method", call_count=2)
self.assert_output_contains_success_marker(result.stdout)

# Container and adapter mocking
mock_container = self.create_mock_container()
mock_adapter = self.create_adapter_mock()
with self.patch_container_creation(mock_container):
    # CLI commands use mocked services
```

### 13.7 CLI Test Categories

**Run CLI tests by category:**
```bash
# All CLI tests
python -m pytest tests/fresh_suite/cli/ -v

# Specific categories
python tests/fresh_suite/cli/cli_test_runner.py workflow
python tests/fresh_suite/cli/cli_test_runner.py validation  
python tests/fresh_suite/cli/cli_test_runner.py integration
python tests/fresh_suite/cli/cli_test_runner.py error
```

**Coverage Areas:**
- ✅ All 10+ CLI commands (run, compile, scaffold, export, validate-*, diagnose, config, cache)
- ✅ Success and failure scenarios for each command
- ✅ Option parsing and argument validation
- ✅ File system operations and error handling
- ✅ Service integration and proper delegation
- ✅ Cross-command workflows and data consistency
- ✅ User experience and output formatting
- ✅ Error recovery and graceful degradation

### 13.8 CLI Testing Best Practices

1. **Use BaseCLITest**: Always inherit from `BaseCLITest` for consistent patterns
2. **Mock Services, Not CLI**: Mock the underlying services, not the CLI framework
3. **Test User Experience**: Verify output formatting, error messages, and exit codes
4. **Real File Operations**: Use real temporary files for realistic testing
5. **Service Integration**: Test that CLI properly delegates to services
6. **Error Scenarios**: Test graceful handling of various error conditions
7. **Workflow Testing**: Test complete multi-command workflows

**Key Pattern**: CLI tests focus on the integration between the CLI interface and the service layer, ensuring commands properly delegate to services and provide good user experience.

---

*This guide represents the established patterns for AgentMap's fresh test suite. Follow these patterns for consistency and maintainability across all service and CLI tests.*

---

## 12. Path and File System Mocking Patterns

### 12.1 Path.exists() Mocking (CRITICAL)

**Problem**: Path.exists() mocking can be tricky and has caused multiple test failures. The wrong approach doesn't properly intercept Path.exists() calls.

```python
# ❌ WRONG: This often doesn't work correctly
import unittest.mock
with unittest.mock.patch.object(Path, 'exists', side_effect=mock_exists):
    # Path.exists() calls may not be intercepted

# ❌ ALSO WRONG: Instance-level patching
with unittest.mock.patch.object(Path, 'exists', return_value=False):
    # May not work with Path() constructor calls
```

**Solution**: Use module-level patching for reliable Path.exists() interception:

```python
# ✅ CORRECT: Module-level patching
import unittest.mock
with unittest.mock.patch('pathlib.Path.exists', return_value=False):
    # All Path.exists() calls are properly intercepted
    result = service.method_that_checks_file_existence()
    
# ✅ ALSO CORRECT: For multiple return values
with unittest.mock.patch('pathlib.Path.exists', side_effect=[False, True, False]):
    # First call returns False, second True, third False
    service.check_multiple_files()
```

### 12.2 Path Operations Testing Pattern

```python
def test_method_with_file_operations(self):
    """Test method that performs file system operations."""
    # Mock Path.exists for controlled file existence testing
    with unittest.mock.patch('pathlib.Path.exists') as mock_exists:
        # Configure file existence behavior
        mock_exists.return_value = False  # No files exist
        
        # Test behavior when files don't exist
        result = self.service.process_with_file_check()
        self.assertEqual(result.status, "files_missing")
        
        # Verify Path.exists was called
        mock_exists.assert_called()
        
        # Reset and test when files exist
        mock_exists.reset_mock()
        mock_exists.return_value = True
        
        result = self.service.process_with_file_check()
        self.assertEqual(result.status, "files_found")
```

### 12.3 Complex Path Scenarios

```python
def test_selective_file_existence(self):
    """Test with different files existing or not."""
    def mock_exists(path_self):
        """Mock that returns different values based on file path."""
        path_str = str(path_self)
        if "compiled" in path_str:
            return False  # No compiled files
        elif "source" in path_str:
            return True   # Source files exist
        else:
            return False  # Other files don't exist
    
    with unittest.mock.patch('pathlib.Path.exists', side_effect=mock_exists):
        # Now Path.exists() returns different values based on path
        result = self.service.resolve_execution_path("test_graph")
        self.assertEqual(result.execution_type, "from_source")
```

### 12.4 File Reading/Writing Mocking

```python
def test_file_reading(self):
    """Test method that reads files."""
    mock_file_content = "test,data,content\nrow1,value1,value2"
    
    # Mock both file existence and reading
    with unittest.mock.patch('pathlib.Path.exists', return_value=True), \
         unittest.mock.patch('builtins.open', unittest.mock.mock_open(read_data=mock_file_content)):
        
        result = self.service.process_csv_file(Path("test.csv"))
        self.assertEqual(len(result.rows), 1)
        self.assertEqual(result.rows[0]["test"], "row1")
```

### 12.5 Directory Operations

```python
def test_directory_operations(self):
    """Test methods that work with directories."""
    with unittest.mock.patch('pathlib.Path.exists') as mock_exists, \
         unittest.mock.patch('pathlib.Path.mkdir') as mock_mkdir, \
         unittest.mock.patch('pathlib.Path.is_dir', return_value=True):
        
        # Configure directory existence
        mock_exists.return_value = False  # Directory doesn't exist initially
        
        # Test directory creation
        self.service.ensure_output_directory(Path("output"))
        
        # Verify mkdir was called with correct arguments
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
```

### 12.6 Multiple Path Patches in One Test

```python
def test_complex_file_workflow(self):
    """Test complex workflow with multiple file operations."""
    with unittest.mock.patch('pathlib.Path.exists') as mock_exists, \
         unittest.mock.patch('pathlib.Path.stat') as mock_stat, \
         unittest.mock.patch('builtins.open', unittest.mock.mock_open()) as mock_open:
        
        # Configure file system state
        mock_exists.return_value = True
        mock_stat.return_value.st_mtime = 1234567890  # Mock modification time
        
        # Test the workflow
        result = self.service.compile_if_newer("source.csv", "compiled.pkl")
        
        # Verify all file operations
        mock_exists.assert_called()  # File existence checked
        mock_stat.assert_called()    # File stats retrieved
        self.assertTrue(result.compilation_needed)
```

### 12.7 Common Path Mocking Pitfalls

#### Pitfall 1: Wrong Patch Target
```python
# ❌ WRONG: Patching the class instead of the module
with unittest.mock.patch.object(pathlib.Path, 'exists'):
    pass  # May not work reliably

# ✅ CORRECT: Patching the module path
with unittest.mock.patch('pathlib.Path.exists'):
    pass  # Works reliably
```

#### Pitfall 2: Not Accounting for Multiple Path Calls
```python
# ❌ PROBLEMATIC: Only accounts for one call
with unittest.mock.patch('pathlib.Path.exists', return_value=False):
    # If service checks multiple files, they all return False
    # This might not be the intended test scenario

# ✅ BETTER: Account for multiple calls
with unittest.mock.patch('pathlib.Path.exists', side_effect=[False, True]):
    # First file doesn't exist, second file exists
    # More realistic test scenario
```

#### Pitfall 3: Forgetting to Reset Mocks
```python
def test_first_scenario(self):
    with unittest.mock.patch('pathlib.Path.exists', return_value=False):
        # Test when no files exist
        pass

def test_second_scenario(self):
    # ❌ WRONG: Previous mock state might interfere
    with unittest.mock.patch('pathlib.Path.exists', return_value=True):
        # ✅ CORRECT: Each test gets fresh mock state
        pass
```

### 12.8 Path Mocking Test Template

```python
def test_method_with_path_operations(self):
    """Template for testing methods that use Path operations."""
    # Configure mock dependencies first
    self.mock_config_service.get_compiled_graphs_path.return_value = Path("compiled")
    self.mock_config_service.get_csv_path.return_value = Path("graphs/test.csv")
    
    # Configure path existence behavior
    with unittest.mock.patch('pathlib.Path.exists', return_value=False):
        # Execute the method under test
        result = self.service.method_that_checks_files()
        
        # Verify the expected behavior occurred
        self.assertEqual(result.execution_path, "fallback")
        
        # Verify expected service calls were made
        self.mock_other_service.fallback_method.assert_called_once()
```

### 12.9 Real-World Example: Graph Execution Path Resolution

```python
def test_run_graph_execution_path_priority(self):
    """Test graph execution follows correct path priority."""
    # Configure services
    self.mock_app_config_service.get_compiled_graphs_path.return_value = Path("compiled")
    
    # Test 1: Compiled graph exists (highest priority)
    with unittest.mock.patch('pathlib.Path.exists', return_value=True):
        mock_result = Mock(success=True, compiled_from="precompiled")
        self.mock_graph_execution_service.execute_compiled_graph.return_value = mock_result
        
        result = self.service.run_graph("test_graph")
        
        # Should use compiled path
        self.mock_graph_execution_service.execute_compiled_graph.assert_called_once()
        self.mock_compilation_service.auto_compile_if_needed.assert_not_called()
        self.assertEqual(result.compiled_from, "precompiled")
    
    # Reset for next test
    self.mock_graph_execution_service.reset_mock()
    
    # Test 2: No compiled graph, fall back to other paths
    with unittest.mock.patch('pathlib.Path.exists', return_value=False):
        # Configure fallback behavior
        # ... rest of test
```

**Key Takeaway**: Always use `unittest.mock.patch('pathlib.Path.exists')` for reliable Path.exists() mocking. This pattern has been tested and works consistently across different test scenarios.

### 12.10 Debugging Hidden Exception Patterns

**Problem**: Services with broad exception handling can mask test failures. Tests expect method calls that never happen because exceptions are caught and converted to error results.

```python
# ❌ PROBLEMATIC: Service catches all exceptions
def run_graph(self, graph_name: str) -> ExecutionResult:
    try:
        # Complex preparation pipeline
        resolved_execution = self._complex_preparation(graph_name)
        return self.execution_service.execute(...)  # ← Never called if exception occurs
    except Exception as e:
        return ExecutionResult(success=False, error=str(e))  # ← Hides real issues
```

**Solution**: Use systematic mock setup to prevent exceptions in the preparation pipeline:

```python
def test_service_with_complex_preparation(self):
    """Test service method that has complex internal preparation."""
    # 1. Mock the data models
    mock_domain_model = Mock()
    mock_domain_model.nodes = {
        "node1": Mock(name="node1", agent_type="default", inputs=["input1"], 
                     output="output1", prompt="Test prompt", description="Test node",
                     context={}, edges=[])
    }
    self.mock_definition_service.build_from_csv.return_value = mock_domain_model
    
    # 2. Mock intermediate processing steps
    mock_registry = {"node1": Mock()}
    self.mock_registry_service.prepare_for_assembly.return_value = mock_registry
    
    # 3. Mock complex internal methods to avoid dependency chains
    def mock_simple_agent_class(agent_type):
        return type('MockAgent', (), {
            '__init__': lambda self, **kwargs: None,
            'run': lambda self, **kwargs: {},
            'name': 'mock_agent'
        })
    
    # 4. Patch all complex internal methods
    with unittest.mock.patch.object(self.service, '_resolve_complex_dependency', side_effect=mock_simple_agent_class), \
         unittest.mock.patch.object(self.service, '_inject_complex_services'), \
         unittest.mock.patch.object(self.service, '_validate_complex_configuration'):
        
        # 5. Configure expected result
        mock_result = Mock(success=True, data="expected_output")
        self.mock_execution_service.execute.return_value = mock_result
        
        # 6. Execute test
        result = self.service.run_complex_operation("test_input")
        
        # 7. Verify the expected delegation happened
        self.mock_execution_service.execute.assert_called_once()
        self.assertEqual(result, mock_result)
```

### 12.11 Common Mock Setup Patterns for Complex Services

#### Pattern 1: Agent Resolution Mocking
```python
# Mock agent class resolution to avoid dependency checking
def mock_resolve_agent_class(agent_type):
    return type('MockAgent', (), {
        '__init__': lambda self, **kwargs: None,
        'run': lambda self, **kwargs: {},
        'name': f'mock_{agent_type}_agent'
    })

with unittest.mock.patch.object(service, '_resolve_agent_class', side_effect=mock_resolve_agent_class):
    # Test code that depends on agent resolution
```

#### Pattern 2: Service Injection Mocking
```python
# Mock service injection to avoid complex dependency setup
with unittest.mock.patch.object(service, '_inject_llm_service'), \
     unittest.mock.patch.object(service, '_inject_storage_services'), \
     unittest.mock.patch.object(service, '_validate_agent_configuration'):
    # Test code that depends on service injection
```

#### Pattern 3: Registry and Assembly Mocking
```python
# Mock registry preparation
mock_node_registry = {"node1": Mock(), "node2": Mock()}
self.mock_node_registry_service.prepare_for_assembly.return_value = mock_node_registry

# Mock assembly service
mock_assembled_graph = Mock()
self.mock_assembly_service.assemble_graph.return_value = mock_assembled_graph
```

### 12.12 Debugging Test Failures Systematically

#### Step 1: Add Temporary Exception Debugging
```python
def test_failing_method_debug(self):
    """Debug version of failing test to see what exceptions are thrown."""
    # Temporarily patch the service to print exceptions instead of catching them
    original_method = self.service.run_graph
    
    def debug_method(*args, **kwargs):
        try:
            return original_method(*args, **kwargs)
        except Exception as e:
            print(f"DEBUG: Exception caught: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            raise  # Re-raise to see the actual error
    
    self.service.run_graph = debug_method
    
    # Run the test to see what exceptions occur
    with self.assertRaises(Exception):
        result = self.service.run_graph("test_graph")
```

#### Step 2: Systematic Mock Verification
```python
def test_mock_verification(self):
    """Verify all mocks are properly configured before running the test."""
    # Check that all required mocks are set up
    required_mocks = [
        self.mock_definition_service.build_from_csv,
        self.mock_registry_service.prepare_for_assembly,
        self.mock_execution_service.execute_from_definition
    ]
    
    for mock in required_mocks:
        self.assertIsNotNone(mock, f"Mock not configured: {mock}")
    
    # Proceed with test...
```

#### Step 3: Progressive Mock Setup
```python
def test_progressive_mock_setup(self):
    """Build up mocks progressively to identify which dependency is missing."""
    # Start with minimal mocks
    mock_model = Mock()
    mock_model.nodes = {"node1": Mock(name="node1", agent_type="default")}
    self.mock_definition_service.build_from_csv.return_value = mock_model
    
    try:
        result = self.service.run_graph("test_graph")
        print("SUCCESS: Minimal mocks work")
    except Exception as e:
        print(f"FAILED with minimal mocks: {e}")
        
        # Add registry mock
        self.mock_registry_service.prepare_for_assembly.return_value = {"node1": Mock()}
        
        try:
            result = self.service.run_graph("test_graph")
            print("SUCCESS: With registry mock")
        except Exception as e:
            print(f"FAILED with registry mock: {e}")
            
            # Add agent resolution mock
            with unittest.mock.patch.object(self.service, '_resolve_agent_class'):
                try:
                    result = self.service.run_graph("test_graph")
                    print("SUCCESS: With agent resolution mock")
                except Exception as e:
                    print(f"FAILED with agent resolution mock: {e}")
                    # Continue adding mocks until success...
```

### 12.13 Test Template for Complex Service Methods

```python
def test_complex_service_method_template(self):
    """Template for testing methods with complex internal dependencies."""
    # 1. Configure basic data mocks
    mock_input_data = Mock()
    mock_input_data.field1 = "value1"
    mock_input_data.field2 = "value2"
    
    # 2. Configure service method mocks (in dependency order)
    self.mock_step1_service.process.return_value = mock_input_data
    self.mock_step2_service.transform.return_value = Mock()
    self.mock_step3_service.validate.return_value = True
    
    # 3. Mock complex internal operations
    def mock_complex_operation(input_data):
        return f"processed_{input_data}"
    
    with unittest.mock.patch.object(self.service, '_complex_internal_method', side_effect=mock_complex_operation), \
         unittest.mock.patch.object(self.service, '_another_complex_method'), \
         unittest.mock.patch.object(self.service, '_final_complex_method'):
        
        # 4. Configure expected result
        expected_result = Mock(success=True, data="expected")
        self.mock_final_service.execute.return_value = expected_result
        
        # 5. Execute test
        result = self.service.complex_method("test_input")
        
        # 6. Verify delegation chain
        self.mock_step1_service.process.assert_called_once()
        self.mock_step2_service.transform.assert_called_once()
        self.mock_final_service.execute.assert_called_once()
        
        # 7. Verify result
        self.assertEqual(result, expected_result)
```

### 12.14 Common Failure Patterns and Solutions

#### Pattern: "Expected X to be called once. Called 0 times."
**Cause**: Exception in preparation pipeline prevents expected method call.
**Solution**: Mock all preparation dependencies or add debugging to see the exception.

#### Pattern: "Mock object has no attribute 'Y'"
**Cause**: Test is accessing an attribute that wasn't configured on the mock.
**Solution**: Configure the mock attribute or use `spec` parameter.

#### Pattern: "TypeError: X() missing required argument"
**Cause**: Mock is being called with unexpected arguments or missing arguments.
**Solution**: Check the actual method signature and configure side_effect properly.

#### Pattern: "AttributeError during agent resolution"
**Cause**: Agent class resolution involves complex dependency checking.
**Solution**: Mock `_resolve_agent_class` method directly.

```python
# ✅ SOLUTION for agent resolution issues
with unittest.mock.patch.object(service, '_resolve_agent_class') as mock_resolve:
    mock_resolve.return_value = type('MockAgent', (), {'run': lambda self: {}})
    # Test continues without complex agent dependency checking
```
