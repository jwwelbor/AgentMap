# AgentMap Testing Patterns Guide

## Mock Service Usage Patterns for Migration

This guide documents the correct patterns for using mock services during the migration phase of AgentMap.

## 1. Mock Service Creation

### Correct Pattern
```python
from agentmap.migration_utils import (
    MockLoggingService,
    MockAppConfigService,
    MockNodeRegistryService
)

class TestMyService(unittest.TestCase):
    def setUp(self):
        # Create mock services
        self.mock_logging_service = MockLoggingService()
        self.mock_config_service = MockAppConfigService()
        self.mock_node_registry_service = MockNodeRegistryService()
        
        # Create service with mocked dependencies
        self.service = MyService(
            logging_service=self.mock_logging_service,
            app_config_service=self.mock_config_service,
            node_registry_service=self.mock_node_registry_service
        )
```

## 2. Logger Call Verification

### Correct Pattern
```python
def test_my_method_logs_correctly(self):
    # Execute method
    self.service.my_method()
    
    # Check logger calls using the established pattern
    logger_calls = self.service.logger.calls
    self.assertTrue(any(call[1] == "[MyService] Expected message" 
                      for call in logger_calls if call[0] == "info"))
```

### ❌ Incorrect Pattern (DO NOT USE)
```python
def test_my_method_logs_correctly(self):
    # DON'T DO THIS - self.mock_logger doesn't exist
    self.mock_logger.info.assert_called_with("[MyService] Expected message")
```

## 3. MockLoggingService Architecture

The MockLoggingService creates MockLogger instances that track all log calls:

```python
class MockLogger:
    def __init__(self, name: str):
        self.name = name
        self.calls = []  # List of (level, message) tuples
    
    def info(self, message: str):
        self.calls.append(("info", message))
    
    def debug(self, message: str):
        self.calls.append(("debug", message))
    # ... etc for other log levels
```

## 4. Service Testing Template

```python
import unittest
from agentmap.services.my_service import MyService
from agentmap.migration_utils import (
    MockLoggingService,
    MockAppConfigService
)

class TestMyService(unittest.TestCase):
    def setUp(self):
        # Create mock dependencies
        self.mock_logging_service = MockLoggingService()
        self.mock_config_service = MockAppConfigService()
        
        # Create service instance
        self.service = MyService(
            logging_service=self.mock_logging_service,
            app_config_service=self.mock_config_service
        )
    
    def test_service_initialization(self):
        """Test service initializes with dependencies."""
        # Verify dependencies are stored
        self.assertEqual(self.service.logger.name, "MyService")
        self.assertEqual(self.service.config, self.mock_config_service)
        
        # Verify initialization log message
        logger_calls = self.service.logger.calls
        self.assertTrue(any(call[1] == "[MyService] Initialized" 
                          for call in logger_calls if call[0] == "info"))
```

## 5. Integration Test Patterns

For integration tests, use real services where possible but still mock external dependencies:

```python
class TestMyServiceIntegration(unittest.TestCase):
    def setUp(self):
        # Use minimal mocks for integration tests
        self.logging_service = MockLoggingService()
        self.config_service = MockAppConfigService()
        
        # Create real service instance
        self.service = MyService(
            logging_service=self.logging_service,
            app_config_service=self.config_service
        )
```

## 6. Model Test Patterns

Model tests should focus only on data storage and retrieval:

```python
import unittest
from agentmap.models import MyModel

class TestMyModel(unittest.TestCase):
    def test_model_creation(self):
        """Test model data storage."""
        model = MyModel(name="test", value=42)
        
        self.assertEqual(model.name, "test")
        self.assertEqual(model.value, 42)
    
    # NO business logic testing in model tests
    # NO service method testing in model tests
```

## 7. Import Patterns

### Correct Imports
```python
# For services
from agentmap.services.my_service import MyService

# For models  
from agentmap.models import MyModel, OtherModel
from agentmap.models.my_model import MyModel

# For migration utilities
from agentmap.migration_utils import MockLoggingService
```

### ❌ Incorrect Imports (DO NOT USE)
```python
# DON'T USE src_new prefix in tests
from src_new.agentmap.models import MyModel  # WRONG
```

## 8. Common Mistakes to Avoid

1. **Don't access non-existent mock attributes**: `self.mock_logger` doesn't exist
2. **Don't use wrong import paths**: No `src_new.` prefix in imports  
3. **Don't test business logic in model tests**: Keep model tests simple
4. **Don't patch at wrong locations**: Import mock functions at module level
5. **Don't forget to use migration_utils**: Always use provided mock services

## 9. Debugging Tips

- Check `self.service.logger.calls` to see all logged messages
- Verify mock service setup in `setUp()` method
- Use `self.assertEqual(self.service.logger.name, "ExpectedServiceName")` to verify logger setup
- Print `logger_calls` if assertions fail to see actual logged messages

## 10. Future Development

When adding new services:
1. Follow the established dependency injection pattern
2. Use MockLoggingService for all tests
3. Create comprehensive unit tests with full mock isolation
4. Add integration tests with minimal mocking
5. Update this guide with new patterns if needed

---

*This guide should be followed for all migration-phase testing to ensure consistency and prevent mock-related test failures.*
