---
sidebar_position: 3
title: Testing Troubleshooting Guide
description: Debugging guide for AgentMap testing issues with solutions, error patterns, and diagnostic steps
keywords: [testing troubleshooting, debugging tests, mock issues, CI failures, test debugging]
---

# Testing Troubleshooting Guide

Practical debugging guide for AgentMap testing issues. **Use this during troubleshooting conversations** to quickly identify and resolve common testing problems.

:::tip For AI-Assisted Debugging
When asking for help with specific errors:
1. **Identify the error pattern** using the sections below
2. **Share the specific error message** and relevant code
3. **Reference the diagnostic steps** you've tried
4. **Mention your Python version** (critical for compatibility issues)
:::

## 🚨 Critical CI Failure Patterns

### Pattern 1: Tests Pass Locally, Fail on CI

**Symptoms:**
```
AssertionError: Expected 'add_edge' to be called once. Called 0 times.
```
```
FAILED: Unexpected orchestrator count: expected 1, got 6
```

**Root Cause:** Python 3.11 Mock protocol detection issue

**Immediate Fix:**
```python
# ❌ BROKEN (causes CI failures)
mock_agent = Mock()
mock_agent.run = Mock(return_value={"result": "output"})

# ✅ FIXED (works on all Python versions)  
from unittest.mock import create_autospec

class BasicAgent:
    def run(self, state):
        return {"result": "output"}

mock_agent = create_autospec(BasicAgent, instance=True)
mock_agent.run.return_value = {"result": "output"}
```

**Diagnostic Steps:**
1. Check if test uses `Mock()` for agents
2. Verify Python version in CI vs local (usually 3.11 vs 3.12+)
3. Look for protocol-related errors (NodeRegistryUser, etc.)

### Pattern 2: Read-Only Path Attribute Errors

**Symptoms:**
```
AttributeError: can't set attribute 'exists' on Windows/PosixPath
AttributeError: WindowsPath attribute 'exists' is read-only
```

**Root Cause:** Direct assignment to Path object attributes

**Immediate Fix:**
```python
# ❌ BROKEN (read-only attributes)
mock_path.exists = Mock(return_value=True)
mock_path.stat = Mock(return_value=stat_result)

# ✅ FIXED (use utilities)
from tests.utils.path_mocking_utils import mock_compilation_currency

with mock_compilation_currency(out_path, csv_path, is_current=True):
    result = self.service._is_compilation_current(...)

# OR manual patching of service module
with patch('agentmap.services.my_service.Path', 
           side_effect=lambda *p, **k: mock_path):
    result = self.service.method_that_creates_paths()
```

**Diagnostic Steps:**
1. Search for `mock_path.exists =` or similar direct assignments
2. Check if service creates new `Path()` instances internally
3. Use path utilities or patch the service module's Path import

## 🔍 Mock Call Debugging

### Pattern 3: Expected Call Not Made

**Symptoms:**
```
AssertionError: Expected 'process_data' to be called once. Called 0 times.
```

**Diagnostic Script:**
```python
def debug_mock_calls(self):
    """Use this to debug mock call issues."""
    
    # 1. Check if mock was called at all
    print("Method called:", self.mock_service.process_data.called)
    print("Call count:", self.mock_service.process_data.call_count)
    
    # 2. See actual calls made
    print("All method calls:", self.mock_service.method_calls)
    print("process_data calls:", self.mock_service.process_data.call_args_list)
    
    # 3. Check for exceptions that prevent the call
    try:
        result = self.service.method_under_test("input")
        print("Method executed successfully:", result)
    except Exception as e:
        print("Exception prevented call:", e)
        import traceback
        traceback.print_exc()
    
    # 4. Verify mock configuration
    print("Mock configured methods:", dir(self.mock_service))
    print("process_data configured:", hasattr(self.mock_service, 'process_data'))
```

**Common Causes & Fixes:**
```python
# Cause 1: Exception in method setup
# Fix: Mock all required dependencies
self.mock_config.get_required_setting.return_value = "default_value"

# Cause 2: Method called with different arguments
# Fix: Check actual vs expected arguments
try:
    self.mock_service.process_data.assert_called_once_with("expected_input")
except AssertionError:
    print("Actually called with:", self.mock_service.process_data.call_args)

# Cause 3: Method not configured on mock
# Fix: Ensure mock has the method
if not hasattr(self.mock_service, 'process_data'):
    self.mock_service.process_data = Mock(return_value="default")
```

### Pattern 4: Mock Has No Attribute

**Symptoms:**
```
AttributeError: Mock object has no attribute 'expected_method'
```

**Immediate Fix:**
```python
# Method 1: Configure the attribute
self.mock_service.expected_method = Mock(return_value="default")

# Method 2: Use spec parameter
self.mock_service = Mock(spec=ActualServiceClass)

# Method 3: Use MockServiceFactory (recommended)
self.mock_service = MockServiceFactory.create_mock_my_service()
```

**Diagnostic Steps:**
1. Check if attribute exists: `hasattr(mock_service, 'method_name')`
2. List available attributes: `dir(mock_service)`
3. Verify spelling and case sensitivity
4. Ensure mock was created with proper spec

## 🔧 Configuration and Setup Issues

### Pattern 5: Mock Configuration Not Working

**Symptoms:**
```python
# Mock configured but service gets different value
self.mock_config.get_setting.return_value = "test_value"
actual = self.service.get_config_value()  # Returns None or default
```

**Diagnostic Script:**
```python
def debug_mock_configuration(self):
    """Debug mock configuration issues."""
    
    # 1. Verify mock is properly injected
    print("Service config is mock:", self.service.config is self.mock_config)
    
    # 2. Check if method is called
    result = self.service.get_config_value()
    print("get_setting called:", self.mock_config.get_setting.called)
    print("get_setting call args:", self.mock_config.get_setting.call_args_list)
    
    # 3. Test mock directly
    direct_result = self.mock_config.get_setting("test_key")
    print("Direct mock call result:", direct_result)
    
    # 4. Check for side_effect override
    if hasattr(self.mock_config.get_setting, 'side_effect'):
        print("side_effect set:", self.mock_config.get_setting.side_effect)
```

**Common Fixes:**
```python
# Issue: side_effect overrides return_value
# Fix: Use side_effect properly or remove it
self.mock_config.get_setting.side_effect = None  # Remove side_effect
self.mock_config.get_setting.return_value = "correct_value"

# Issue: Wrong method name or signature
# Fix: Check actual service method signature
# Service expects: get_setting(key, default=None)
self.mock_config.get_setting.return_value = "value"
# OR with specific args:
self.mock_config.get_setting.side_effect = lambda key, default=None: "value"

# Issue: Mock not properly injected
# Fix: Verify service constructor
service = MyService(config_service=self.mock_config)  # Explicit injection
```

### Pattern 6: Service Initialization Failures

**Symptoms:**
```
Exception during setUp(): Cannot initialize service
KeyError: 'required_config_key'
AttributeError: 'NoneType' object has no attribute 'method'
```

**Diagnostic Script:**
```python
def debug_service_initialization(self):
    """Debug service initialization issues."""
    
    try:
        # Test with minimal mock setup
        basic_mock = Mock()
        service = MyService(dependency=basic_mock)
        print("Basic initialization successful")
    except Exception as e:
        print("Basic initialization failed:", e)
        
        # Check required dependencies
        import inspect
        sig = inspect.signature(MyService.__init__)
        print("Required parameters:", list(sig.parameters.keys()))
        
        # Test each dependency
        for param in sig.parameters:
            if param != 'self':
                try:
                    mock_dep = Mock()
                    kwargs = {param: mock_dep}
                    test_service = MyService(**kwargs)
                    print(f"{param}: OK")
                except Exception as dep_error:
                    print(f"{param}: FAILED - {dep_error}")
```

**Common Fixes:**
```python
# Issue: Missing required mock methods
# Fix: Use MockServiceFactory or configure all methods
self.mock_config = MockServiceFactory.create_mock_app_config_service()

# Issue: Mock returns None for required calls
# Fix: Configure return values for all called methods
self.mock_config.get_required_setting.return_value = "default_value"
self.mock_config.initialize.return_value = True

# Issue: Service calls methods during initialization
# Fix: Configure initialization-time method calls
self.mock_logging.create_logger.return_value = Mock()
```

## 🏃‍♂️ Performance Testing Issues

### Pattern 7: Performance Tests Failing

**Symptoms:**
```
AssertionError: Operation took 2.5s (too slow)
Performance test timeout after 10s
```

**Diagnostic Script:**
```python
import time
import cProfile
import pstats

def debug_performance_issues(self):
    """Debug performance test failures."""
    
    # 1. Profile the operation
    profiler = cProfile.Profile()
    profiler.enable()
    
    start_time = time.time()
    result = self.service.slow_operation()
    execution_time = time.time() - start_time
    
    profiler.disable()
    
    print(f"Execution time: {execution_time:.2f}s")
    
    # 2. Find time consumers
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    print("Top time consumers:")
    stats.print_stats(10)
    
    # 3. Check for real operations (should be mocked)
    stats_dict = stats.get_stats()
    real_file_ops = [func for func in stats_dict if 'open' in str(func) or 'read' in str(func)]
    if real_file_ops:
        print("WARNING: Real file operations detected:", real_file_ops)
    
    # 4. Check mock call counts
    if hasattr(self.mock_llm, 'process'):
        print("LLM mock calls:", self.mock_llm.process.call_count)
        if self.mock_llm.process.call_count == 0:
            print("WARNING: LLM mock not called - real LLM might be used")
```

**Common Fixes:**
```python
# Issue: Real file operations instead of mocks
# Fix: Ensure all file operations are mocked
with patch('agentmap.services.my_service.Path') as mock_path:
    mock_path.return_value.exists.return_value = True
    result = self.service.file_operation()

# Issue: Real LLM calls instead of mocks  
# Fix: Verify LLM service is properly mocked
self.mock_llm.process.return_value = {"result": "fast_mock_response"}
# Verify it's actually called:
self.service.llm_operation()
self.mock_llm.process.assert_called()

# Issue: Synchronous operations in async context
# Fix: Use proper async testing patterns
import asyncio
async def test_async_operation(self):
    result = await self.service.async_operation()
    self.assertTrue(result.success)
```

## 🔄 CLI Testing Issues

### Pattern 8: CLI Tests Not Working

**Symptoms:**
```
CLI command failed with exit code 1
Expected success message not found in output
CliRunner timeout after 30s
```

**Diagnostic Script:**
```python
def debug_cli_issues(self):
    """Debug CLI testing issues."""
    
    from typer.testing import CliRunner
    from agentmap.core.cli.main_cli import app
    
    runner = CliRunner()
    
    # 1. Test basic CLI functionality
    help_result = runner.invoke(app, ["--help"])
    print("Help command exit code:", help_result.exit_code)
    print("Help output length:", len(help_result.stdout))
    
    # 2. Test with verbose output
    result = runner.invoke(app, ["your-command", "--verbose"])
    print("Command exit code:", result.exit_code)
    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)
    
    # 3. Check for exception details
    if result.exception:
        print("Exception occurred:", result.exception)
        import traceback
        traceback.print_exception(type(result.exception), 
                                 result.exception, 
                                 result.exception.__traceback__)
    
    # 4. Verify mock container setup
    print("Mock container configured:", hasattr(self, 'mock_container'))
    if hasattr(self, 'mock_container'):
        print("Services in container:", dir(self.mock_container))
```

**Common Fixes:**
```python
# Issue: CLI can't find services
# Fix: Ensure proper container mocking
mock_container = self.create_mock_container()
with self.patch_container_creation(mock_container):
    result = self.run_cli_command(["your-command"])

# Issue: Missing command-line arguments
# Fix: Provide all required arguments
result = self.run_cli_command([
    "compile", 
    "--graph", "test_graph",
    "--csv", str(self.test_csv_file)  # Convert Path to string
])

# Issue: Service exceptions not handled
# Fix: Configure services to not raise exceptions
self.mock_service.method.return_value = {"success": True}
# OR handle exceptions in CLI code

# Issue: File not found errors
# Fix: Use real temporary files for CLI tests
csv_file = self.create_test_csv_file("test.csv", "content")
result = self.run_cli_command(["command", "--file", str(csv_file)])
```

## 🔐 Security Testing Issues

### Pattern 9: Authentication Tests Failing

**Symptoms:**
```
Expected 401, got 200 (authentication bypassed)
Expected 503, got 401 (wrong error code)
Security test passed when it should fail
```

**Diagnostic Script:**
```python
def debug_auth_issues(self):
    """Debug authentication testing issues."""
    
    # 1. Check auth service configuration
    print("Auth service enabled:", self.auth_service.is_enabled())
    print("Auth method:", type(self.auth_service).__name__)
    
    # 2. Test direct auth service
    valid_result = self.auth_service.validate_key("valid_key")
    invalid_result = self.auth_service.validate_key("invalid_key")
    print("Valid key result:", valid_result)
    print("Invalid key result:", invalid_result)
    
    # 3. Check container configuration
    app_container = get_app_container()
    auth_from_container = app_container.get_auth_service()
    print("Container auth service:", type(auth_from_container).__name__)
    print("Same instance:", auth_from_container is self.auth_service)
    
    # 4. Test request flow
    headers = {"Authorization": "Bearer valid_key"}
    response = self.client.get('/protected-endpoint', headers=headers)
    print("Response status:", response.status_code)
    print("Response data:", response.json() if response.content else "No content")
```

**Common Fixes:**
```python
# Issue: Auth service not properly configured
# Fix: Use proper auth service setup
auth_service = self.create_api_key_auth_service(valid_keys=["test_key"])
self.set_app_container_auth_service(auth_service)

# Issue: Wrong HTTP status codes
# Fix: Test the correct status for each scenario
# Disabled auth service -> 503 Service Unavailable
# Enabled auth, invalid key -> 401 Unauthorized  
# Enabled auth, valid key -> 200 OK

# Issue: Authentication bypass working
# Fix: Ensure bypass is config-controlled, not header-controlled
# ❌ WRONG: Headers should not bypass auth
headers = {"X-AgentMap-Embedded": "true"}  # Should have NO effect
response = self.client.get('/endpoint', headers=headers)
self.assertEqual(response.status_code, 401)  # Still requires auth

# ✅ RIGHT: Only config should disable auth
auth_service = self.create_disabled_auth_service()
self.set_app_container_auth_service(auth_service)
response = self.client.get('/endpoint')
self.assertEqual(response.status_code, 200)  # Auth disabled by config
```

## 🧪 Test Data Issues

### Pattern 10: Test Data Problems

**Symptoms:**
```
CSV parsing failed: missing required columns
Invalid graph structure: circular dependencies
Test data inconsistent between runs
```

**Diagnostic Script:**
```python
def debug_test_data_issues(self):
    """Debug test data generation and usage."""
    
    # 1. Validate CSV structure
    csv_content = self.test_csv_content
    lines = csv_content.strip().split('\n')
    header = lines[0].split(',')
    print("CSV header:", header)
    print("CSV rows:", len(lines) - 1)
    
    # 2. Check required columns
    required_columns = ["graph_name", "node_name", "agent_type"]
    missing_columns = [col for col in required_columns if col not in header]
    if missing_columns:
        print("MISSING COLUMNS:", missing_columns)
    
    # 3. Validate data consistency
    for i, line in enumerate(lines[1:], 1):
        row = line.split(',')
        if len(row) != len(header):
            print(f"Row {i} has {len(row)} columns, expected {len(header)}")
    
    # 4. Check for parsing issues
    try:
        import csv
        import io
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        print("Successfully parsed rows:", len(rows))
        print("Sample row:", rows[0] if rows else "No rows")
    except Exception as e:
        print("CSV parsing failed:", e)
```

**Common Fixes:**
```python
# Issue: Missing CSV columns
# Fix: Use complete header structure
csv_content = '''graph_name,node_name,agent_type,context,NextNode,input_fields,output_field,prompt
test_graph,start,input,Start node,process,user_input,processed_input,Enter your input
test_graph,process,llm,Process data,end,processed_input,result,Process: {processed_input}
test_graph,end,output,End node,,result,,Final result: {result}'''

# Issue: Inconsistent data between test runs
# Fix: Use deterministic test data generation
def create_test_data(seed=12345):
    import random
    random.seed(seed)
    # Generate consistent test data
    return test_data

# Issue: Complex CSV escaping issues
# Fix: Use proper CSV generation
import csv
import io

def generate_test_csv(rows_data):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['graph_name', 'node_name', 'agent_type', 'context', 'NextNode'])
    for row in rows_data:
        writer.writerow(row)
    return output.getvalue()
```

## 🚀 Quick Diagnostic Checklist

When you encounter a test failure, run through this checklist:

### ⚡ Immediate Actions

- [ ] **Check Python version** - Local vs CI (3.11 vs 3.12+ issues)
- [ ] **Look for Mock() usage** - Replace with `create_autospec()` for agents
- [ ] **Check Path operations** - Use utilities, not direct assignment
- [ ] **Verify mock injection** - Services getting proper mocks
- [ ] **Check for exceptions** - Mock setup might be incomplete

### 🔍 Diagnostic Commands

```bash
# Run single failing test with verbose output
python -m pytest tests/path/to/failing_test.py::TestClass::test_method -v -s

# Run with debugging
python -m pytest tests/path/to/failing_test.py --pdb

# Check coverage for specific module
python -m pytest tests/ --cov=agentmap.services.specific_service --cov-report=term-missing

# Run only failed tests from last run
python -m pytest --lf
```

### 🛠️ Code Investigation

```python
# Add this to failing test for debugging
def debug_failure(self):
    import traceback
    try:
        result = self.service.failing_method()
    except Exception as e:
        print("Exception details:")
        traceback.print_exc()
        print("\nMock states:")
        for attr_name in dir(self):
            if attr_name.startswith('mock_'):
                mock_obj = getattr(self, attr_name)
                print(f"{attr_name}: {mock_obj.method_calls}")
        raise
```

## 📞 Getting Help

When asking for testing help, include:

1. **Error message** (full stack trace)
2. **Python version** (local and CI if different)
3. **Relevant test code** (setup and failing test)
4. **Mock configuration** (how mocks are created)
5. **Expected vs actual behavior**

### Effective Help Request Template

```markdown
**Problem:** Tests pass locally (Python 3.12) but fail on CI (Python 3.11)

**Error:**
```
AssertionError: Expected 'add_edge' to be called once. Called 0 times.
```

**Code:**
```python
# Current setup (failing)
mock_agent = Mock()
mock_agent.run.return_value = {"result": "output"}

# Test that fails
def test_agent_coordination(self):
    result = self.service.coordinate_agents([mock_agent])
    # Fails here on CI
    self.mock_service.add_edge.assert_called_once()
```

**Environment:**
- Local: Python 3.12.1 ✅ passing
- CI: Python 3.11.8 ❌ failing

**Question:** How do I fix the Python 3.11 compatibility issue?
```

This format helps get targeted, effective assistance quickly.

## 📚 Related Documentation

- **[Quick Reference](/docs/testing/quick-reference)** - Essential patterns and standards
- **[Comprehensive Guide](/docs/testing/comprehensive-guide)** - Detailed examples and scenarios
- **[Advanced Patterns](/docs/testing/advanced-patterns)** - Performance and specialized testing

---

**Remember:** Most testing issues fall into these common patterns. Use the diagnostic scripts to quickly identify the root cause, then apply the corresponding fix.
