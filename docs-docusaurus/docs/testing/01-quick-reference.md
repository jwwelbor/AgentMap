---
sidebar_position: 1
title: Testing Quick Reference
description: Essential testing patterns, Python 3.11 compatibility, and quick reference for AgentMap testing
keywords: [testing standards, mock patterns, Python compatibility, quick reference, MockServiceFactory]
---

# Testing Quick Reference

Essential patterns and standards for AgentMap testing. **Start here** for immediate testing guidance or when troubleshooting issues.

:::tip For AI-Assisted Troubleshooting
When asking for help with testing issues, reference specific sections from this guide to get targeted assistance:
- 🚨 **Python 3.11 Compatibility** - Most common CI failures
- 🔧 **MockServiceFactory Patterns** - Service mocking standards  
- 🛣️ **Path Mocking Quick Fix** - Filesystem operation issues
- 🚫 **Anti-Patterns** - What not to do
:::

## 🚨 CRITICAL: Python 3.11 Compatibility

**#1 cause of CI failures:** Tests pass locally (Python 3.12+) but fail on CI (Python 3.11).

### The Problem
```python
# ❌ BROKEN: Mock accidentally implements protocols in Python 3.11
mock_agent = Mock()
mock_agent.run = Mock(return_value={"result": "output"})
# isinstance(mock_agent, NodeRegistryUser) might return True!
```

### ✅ Solution: Use `create_autospec()`
```python
from unittest.mock import create_autospec

class BasicAgent:
    def run(self, state):
        return {"result": "output"}

# Constrained mock - only has BasicAgent attributes  
mock_agent = create_autospec(BasicAgent, instance=True)
mock_agent.run.return_value = {"result": "output"}
```

### Test Isolation (Required)
```python
def setUp(self):
    # CRITICAL: Reset state between tests
    self.service.orchestrator_nodes = []
    self.service.injection_stats = {
        "orchestrators_found": 0,
        "orchestrators_injected": 0,
        "injection_failures": 0
    }
```

## 🔧 MockServiceFactory Patterns

### Standard Service Mocks
```python
from tests.utils.mock_service_factory import MockServiceFactory

# Core service mocks
mock_logging = MockServiceFactory.create_mock_logging_service()
mock_config = MockServiceFactory.create_mock_app_config_service({
    "my_config": {"enabled": True, "timeout": 30}
})
mock_registry = MockServiceFactory.create_mock_node_registry_service()

# Service initialization
service = MyService(
    app_config_service=mock_config,
    logging_service=mock_logging
)
logger = service.logger  # For verification
```

### Service Test Template
```python
class TestMyService(unittest.TestCase):
    def setUp(self):
        self.mock_config = MockServiceFactory.create_mock_app_config_service()
        self.mock_logging = MockServiceFactory.create_mock_logging_service()
        
        self.service = MyService(
            app_config_service=self.mock_config,
            logging_service=self.mock_logging
        )
        self.logger = self.service.logger

    def test_method_behavior(self):
        result = self.service.public_method("input")
        
        # Verify via logger calls, not private state
        logger_calls = self.logger.calls
        self.assertTrue(any("Expected log" in call[1] 
                          for call in logger_calls if call[0] == "info"))
```

## 🛣️ Path Mocking Quick Fix

### Use Utilities First
```python
from tests.utils.path_mocking_utils import mock_compilation_currency

with mock_compilation_currency(out_path, csv_path, is_current=True):
    result = self.service._is_compilation_current(...)
```

### Fallback: Service Module Patching
```python
# Patch Path in the SERVICE MODULE, not pathlib
with patch('agentmap.services.my_service.Path', 
           side_effect=lambda *p, **k: mock_path):
    result = self.service.method_that_creates_paths()
```

### CSV File Mocking Template
```python
def test_csv_processing(self):
    csv_content = "name,value\ntest,123\n"
    mock_file = mock_open(read_data=csv_content)
    
    mock_path = Mock()
    mock_path.exists.return_value = True
    mock_path.open = mock_file
    
    def mock_path_constructor(*args, **kwargs):
        return mock_path
    
    with patch('your.service.module.Path', side_effect=mock_path_constructor):
        result = self.service.load_csv_data("test.csv")
        self.assertEqual(len(result.rows), 1)
```

## 🚫 Anti-Patterns (Avoid These)

| ❌ Don't Do | ✅ Do Instead | Reason |
|-------------|---------------|---------|
| `Mock()` for agents | `create_autospec(BasicAgent)` | Python 3.11 protocol detection |
| `Path.exists = Mock()` | Use path utilities | Read-only attribute errors |
| Header bypass tests | Config-driven auth tests | Security-first principle |
| Custom mock classes | `MockServiceFactory` | Consistency and maintenance |
| `@patch` + DI containers | Pure DI or pure patching | Confusing test setup |

## 🛡️ Security Testing Standards

```python
# ✅ CORRECT: Config-only auth testing
auth = self.create_api_key_auth_service(valid_key)
headers = {"X-AgentMap-Embedded": "true"}  # Should have NO effect
resp = self.client.get('/info/cache', headers=headers)
self.assertEqual(resp.status_code, 401)  # Still requires proper auth
```

## 🔍 Quick Troubleshooting

| Problem | Quick Fix | Reference |
|---------|-----------|-----------|
| Tests pass locally, fail CI | Use `create_autospec()` | [Python 3.11 section](#-critical-python-311-compatibility) |
| "read-only" Path errors | Use path utilities | [Path mocking](#-path-mocking-quick-fix) |
| Mock call not made | Check exception in setup | [Troubleshooting Guide](/docs/testing/troubleshooting#mock-call-issues) |
| Mock has no attribute | Configure mock or use `spec` | [MockServiceFactory patterns](#-mockservicefactory-patterns) |

## 🏃‍♂️ Running Tests

```bash
# Quick test categories
python -m pytest tests/fresh_suite/services/ -v    # Services only
python -m pytest tests/fresh_suite/cli/ -v         # CLI only
python -m pytest tests/ -k "test_path_mocking" -v  # Pattern matching

# Coverage and quality
python -m pytest tests/ --cov=agentmap --cov-report=html -v
```

## 📚 Related Documentation

- **[Comprehensive Guide](/docs/testing/comprehensive-guide)** - Detailed examples and advanced patterns
- **[Troubleshooting](/docs/testing/troubleshooting)** - Detailed debugging help
- **[Advanced Patterns](/docs/testing/advanced-patterns)** - Performance and integration testing

---

**Need Help?** Reference specific sections when asking for testing assistance to get targeted guidance.
