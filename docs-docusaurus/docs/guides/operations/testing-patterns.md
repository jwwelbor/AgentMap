---
sidebar_position: 2
title: Testing Patterns & Best Practices
description: Comprehensive testing patterns for AgentMap using pure Mock objects, path mocking, and CLI testing strategies
keywords: [testing patterns, mock objects, unit testing, CLI testing, path mocking, test automation, AgentMap testing]
---

# AgentMap Testing Patterns & Best Practices

This comprehensive guide documents the **pure Mock testing patterns** used in AgentMap's test suite. These patterns provide clean, maintainable tests using standard Python testing conventions with `unittest.Mock` objects.

## Overview

AgentMap uses modern testing patterns that prioritize:

- ✅ **Pure `unittest.Mock` objects** instead of custom mock classes
- ✅ **MockServiceFactory** for consistent service mocking
- ✅ **Interface testing** with realistic behavior
- ✅ **Dependency injection** instead of @patch decorators
- ✅ **Standard Python testing conventions**
- ✅ **Proper Path/filesystem mocking** to prevent test failures

## Core Testing Architecture

### MockServiceFactory Approach

Replace custom mock classes with pure Mock objects using our centralized factory:

```python
from tests.utils.mock_service_factory import MockServiceFactory

# ✅ NEW: Pure Mock objects
mock_logging = MockServiceFactory.create_mock_logging_service()
mock_config = MockServiceFactory.create_mock_app_config_service()
mock_registry = MockServiceFactory.create_mock_node_registry_service()
```

### ❌ Deprecated Hybrid Approach

```python
# ❌ OLD: Don't use custom mock classes + patching
from agentmap.migration_utils import MockLoggingService
from unittest.mock import patch

@patch('agentmap.services.some_service.LoggingService')
def test_with_patch(self, mock_logging_class):
    mock_logging_class.return_value = MockLoggingService()
    # Complex patching logic...
```

## Service Testing Template

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

## MockServiceFactory Usage Patterns

### Logging Service Mocking

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

### App Config Service Mocking

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

### Node Registry Service Mocking

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

## Path and File System Mocking (CRITICAL)

### The Path Mocking Problem

Many AgentMap services create `Path` instances internally, which bypasses naive mocking attempts and causes tests to fail with "file not found" errors.

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

### The Correct Solution: Service Module Patching

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

### Essential Path Mocking Template

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

### Common Path Mocking Scenarios

#### File Existence Checking
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

#### CSV File Processing
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

## CLI Testing Patterns

### CLI Test Suite Overview

The CLI test suite provides comprehensive testing for all AgentMap CLI commands using `typer.testing.CliRunner`:

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

### CLI Service Integration Testing

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

## Advanced Testing Patterns

### Configuration Flexibility

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

### Exception Testing

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

### Multiple Service Dependencies

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

## Workflow Testing Patterns

### End-to-End Workflow Testing

```python
def test_complete_workflow(self):
    """Test complete AgentMap workflow execution."""
    # Create test CSV
    csv_content = """GraphName,Node,AgentType,Context,NextNode,Input_Fields,Output_Field,Prompt
test_workflow,start,input,Get user input,process,user_input,processed_input,Please enter your request
test_workflow,process,llm,Process the request,end,processed_input,result,Process this request: {processed_input}
test_workflow,end,output,Return result,,result,,"""
    
    csv_file = self.create_test_csv_file("workflow.csv", csv_content)
    
    # Configure all required services
    self.configure_workflow_services()
    
    # Execute workflow
    result = run_graph("test_workflow", {"user_input": "test request"})
    
    # Verify workflow execution
    self.assertTrue(result["graph_success"])
    self.assertIn("result", result)
    
    # Verify service calls
    self.verify_workflow_service_calls()
```

### Integration Testing with Real Components

```python
def test_integration_with_real_config(self):
    """Integration test with real configuration service."""
    # Use real config service with test configuration
    from agentmap.services.config.app_config_service import AppConfigService
    from agentmap.services.config.config_service import ConfigService
    
    config_service = ConfigService()
    config_service.load_config("tests/data/test_config.yaml")
    
    real_app_config = AppConfigService(config_service=config_service)
    
    # Mock only external dependencies
    mock_logging_service = MockServiceFactory.create_mock_logging_service()
    
    # Test with real + mock combination
    service = MyService(
        app_config_service=real_app_config,  # Real
        logging_service=mock_logging_service  # Mock
    )
    
    result = service.process_with_real_config()
    self.assertTrue(result.success)
```

## Performance Testing

### Timing and Performance Verification

```python
import time
from unittest.mock import patch

def test_performance_requirements(self):
    """Test that operations meet performance requirements."""
    
    # Mock fast external service
    self.mock_external_service.process.return_value = "fast_result"
    
    start_time = time.time()
    result = self.service.time_critical_operation()
    execution_time = time.time() - start_time
    
    # Verify performance requirement
    self.assertLess(execution_time, 1.0, "Operation took too long")
    self.assertEqual(result.status, "success")

def test_caching_behavior(self):
    """Test that caching improves performance."""
    
    # First call should hit the service
    result1 = self.service.cached_operation("test_key")
    self.mock_external_service.expensive_call.assert_called_once()
    
    # Second call should use cache
    result2 = self.service.cached_operation("test_key")
    # Still only called once (cached)
    self.mock_external_service.expensive_call.assert_called_once()
    
    self.assertEqual(result1, result2)
```

## Best Practices Summary

### 1. Mock Object Guidelines

- ✅ Use `MockServiceFactory` for consistent service mocking
- ✅ Configure all required methods before testing
- ✅ Use `Mock` for most cases, `MagicMock` when magic methods needed
- ✅ Reset mocks between tests for isolation

### 2. Path Mocking (Critical)

- ✅ Always patch Path in the **service module**, not `pathlib`
- ✅ Use `side_effect` with constructor function for flexibility
- ✅ Configure all Path methods your service uses (`exists`, `open`, `is_file`)
- ✅ Use `mock_open()` for file content with proper `read_data`

### 3. CLI Testing

- ✅ Use `BaseCLITest` for consistent patterns
- ✅ Mock services, not CLI framework
- ✅ Test user experience (output formatting, error messages)
- ✅ Use real temporary files for realistic testing

### 4. Test Organization

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
    # 3. Configuration Integration Tests
    # =============================================================================
    
    def test_configuration_access(self):
        """Test service accesses configuration correctly."""
        pass
```

### 5. Error Handling Testing

- ✅ Test both success and failure scenarios
- ✅ Verify error logging and messages
- ✅ Test exception handling and recovery
- ✅ Ensure graceful degradation

## Troubleshooting Common Issues

### "Expected X to be called once. Called 0 times."
**Cause**: Exception in preparation pipeline prevents expected method call.
**Solution**: Mock all preparation dependencies or add debugging to see the exception.

### "Mock object has no attribute 'Y'"
**Cause**: Test is accessing an attribute that wasn't configured on the mock.
**Solution**: Configure the mock attribute or use `spec` parameter.

### "Still getting file not found errors"
**Cause**: Patching wrong module or wrong Path reference.
**Solution**: Find where Path is imported in your service and patch that exact module.

### "Context manager error with open()"
**Cause**: `mock_open()` not used correctly.
**Solution**: Use `mock_open()` for file operations:

```python
# ✅ CORRECT
mock_file = mock_open(read_data="content")
mock_path.open = mock_file

# ❌ WRONG
mock_path.open.return_value = "content"  # Not a context manager
```

## Testing Checklist

Before writing tests, verify:

- [ ] **Used MockServiceFactory** for service dependencies
- [ ] **Configured all required mock methods** before testing
- [ ] **Identified correct service module** for Path mocking
- [ ] **Used `side_effect=mock_path_constructor`** not `return_value`
- [ ] **Configured Path methods** used by service (`exists`, `open`, etc.)
- [ ] **Tested both success and failure scenarios**
- [ ] **Verified mock calls** with `assert_called()` methods
- [ ] **Reset mocks between tests** for isolation

## Migration from Old Patterns

### Import Changes

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

### Setup Method Changes

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

## Running Tests

### Test Categories

```bash
# All tests
python -m pytest tests/ -v

# Service tests only
python -m pytest tests/fresh_suite/services/ -v

# CLI tests only
python -m pytest tests/fresh_suite/cli/ -v

# Specific test patterns
python -m pytest tests/ -k "test_path_mocking" -v
```

### Coverage Analysis

```bash
# Run with coverage
python -m pytest tests/ --cov=agentmap --cov-report=html

# Generate coverage report
open htmlcov/index.html
```

The goal is clean, maintainable tests that focus on interface behavior rather than implementation details. Pure Mock objects provide the flexibility and standard patterns needed for robust test suites.

## See Also

- [Execution Tracking](execution-tracking.md) - Monitoring and debugging workflows
- [CLI Commands Reference](../../reference/cli-commands.md) - CLI testing targets
- [Configuration Guide](../basics/configuration.md) - Configuration testing patterns
- [Quick Start Guide](../../getting-started/quick-start.md) - Basic workflow testing
