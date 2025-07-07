---
sidebar_position: 1
title: AgentMap Testing Documentation
description: Comprehensive testing documentation for AgentMap development including patterns, troubleshooting, and best practices
keywords: [testing documentation, AgentMap testing, test patterns, development testing, CI testing]
slug: /testing
---

# AgentMap Testing Documentation

Comprehensive testing documentation designed to support both independent development and **AI-assisted conversations** for troubleshooting and implementing tests in AgentMap.

:::tip Documentation Purpose
This testing documentation is optimized for:
- 🚀 **Quick problem resolution** during development
- 🤖 **AI-assisted troubleshooting** conversations
- 📚 **Learning testing patterns** for AgentMap
- 🔧 **Reference during implementation**
:::

## 📋 Documentation Structure

### 🔧 [Quick Reference](/docs/testing/quick-reference)
**Essential patterns and immediate problem solving**

Perfect for:
- ⚡ **Immediate fixes** for common testing issues
- 🐛 **Python 3.11 compatibility** problems (most common CI failures)
- 🔄 **MockServiceFactory** usage patterns
- 🛣️ **Path mocking** quick solutions
- 📊 **Anti-patterns** to avoid

**Use when:** You have a specific testing problem and need a quick solution.

### 📖 [Comprehensive Guide](/docs/testing/comprehensive-guide)
**Detailed examples and implementation patterns**

Perfect for:
- 🏗️ **Service integration testing** with multiple dependencies
- 🔄 **End-to-end workflow testing** from CSV to execution
- ⚡ **Performance testing** patterns and benchmarks
- 🎛️ **Advanced mock coordination** scenarios
- 📊 **Test data management** strategies

**Use when:** You're implementing new tests or need detailed examples.

### 🔍 [Troubleshooting Guide](/docs/testing/troubleshooting)
**Debugging reference for testing issues**

Perfect for:
- 🚨 **CI failure debugging** with diagnostic scripts
- 🔧 **Mock call debugging** step-by-step
- 🛣️ **Path mocking issues** with solutions
- ⚡ **Performance test failures** analysis
- 🔐 **Security test problems** resolution

**Use when:** Tests are failing and you need debugging guidance.

### 🚀 [Advanced Patterns](/docs/testing/advanced-patterns)
**Specialized testing for complex scenarios**

Perfect for:
- 📊 **Performance and load testing** comprehensive patterns
- 🔐 **Security testing** authentication and validation
- 🔄 **Integration testing** multi-service coordination
- 📈 **Monitoring and observability** testing
- 🎯 **CI/CD pipeline** testing strategies

**Use when:** You need specialized testing patterns for complex requirements.

## 🎯 Quick Problem Resolution

### Most Common Issues (Start Here)

| Problem | Quick Fix | Reference |
|---------|-----------|-----------|
| **Tests pass locally, fail CI** | Use `create_autospec()` for agents | [Python 3.11 Compatibility](/docs/testing/quick-reference#-critical-python-311-compatibility) |
| **Path "read-only" errors** | Use path utilities | [Path Mocking](/docs/testing/quick-reference#-path-mocking-quick-fix) |
| **Mock call not made** | Check setup exceptions | [Mock Debugging](/docs/testing/troubleshooting#pattern-3-expected-call-not-made) |
| **Service initialization fails** | Configure all dependencies | [Service Setup](/docs/testing/troubleshooting#pattern-6-service-initialization-failures) |
| **Performance tests failing** | Check for real operations | [Performance Issues](/docs/testing/troubleshooting#pattern-7-performance-tests-failing) |

### 🤖 For AI-Assisted Conversations

When asking for testing help, reference specific sections:

```markdown
**Problem:** My tests pass locally (Python 3.12) but fail on CI (Python 3.11) with:
```
AssertionError: Expected 'add_edge' to be called once. Called 0 times.
```

**Current Code:** [share your mock setup]

**Reference:** I've checked [Python 3.11 Compatibility](/docs/testing/quick-reference#-critical-python-311-compatibility) 
but need help applying the solution to my specific case.
```

## 🏗️ Testing Philosophy & Standards

### Core Principles
- 🎯 **Test behavior, not implementation** - Focus on what services do
- 🔄 **Use realistic scenarios** - Test with production-like data
- 🛡️ **Security by default** - Never test insecure patterns
- ⚡ **Performance awareness** - Include timing assertions
- 🧩 **Isolation and repeatability** - Independent test execution

### Essential Patterns
- ✅ **MockServiceFactory for consistency** - Standard service mocking
- ✅ **create_autospec() for agents** - Python 3.11 compatibility
- ✅ **Path utilities first** - Avoid manual Path mocking
- ✅ **Security-first testing** - Config-driven auth, no bypasses
- ✅ **Comprehensive error testing** - Test failure scenarios

## 🎭 Testing Categories

### Unit Testing
- **Focus**: Single service/component with mocked dependencies
- **Speed**: Fast (< 100ms per test)
- **Isolation**: Complete - no external dependencies
- **Tools**: MockServiceFactory, create_autospec()

### Integration Testing
- **Focus**: Multi-service coordination with real DI container
- **Speed**: Medium (100ms - 5s per test)
- **Isolation**: Partial - real services, mocked externals
- **Tools**: Real containers, hybrid mock/real services

### End-to-End Testing
- **Focus**: Complete workflows from CSV to execution
- **Speed**: Slow (5s+ per test)
- **Isolation**: Minimal - realistic data flows
- **Tools**: Real temporary files, full workflow execution

### Performance Testing
- **Focus**: Timing, memory, and scalability requirements
- **Speed**: Variable (depends on load)
- **Isolation**: Controlled - consistent mock responses
- **Tools**: Timing assertions, profiling, load testing

## 🔧 Essential Tools & Utilities

### MockServiceFactory
```python
from tests.utils.mock_service_factory import MockServiceFactory

# Standard service mocks
mock_logging = MockServiceFactory.create_mock_logging_service()
mock_config = MockServiceFactory.create_mock_app_config_service()
mock_registry = MockServiceFactory.create_mock_node_registry_service()
```

### Path Mocking Utilities
```python
from tests.utils.path_mocking_utils import mock_compilation_currency

with mock_compilation_currency(out_path, csv_path, is_current=True):
    result = self.service._is_compilation_current(...)
```

### CLI Testing Base
```python
from tests.fresh_suite.cli.base_cli_test import BaseCLITest

class TestMyCommand(BaseCLITest):
    def test_command_success(self):
        result = self.run_cli_command(["my-command", "--option", "value"])
        self.assert_cli_success(result)
```

## 🏃‍♂️ Running Tests

### Test Categories
```bash
# Quick validation
python -m pytest tests/fresh_suite/services/ -v          # Services only
python -m pytest tests/fresh_suite/cli/ -v               # CLI only

# Comprehensive testing
python -m pytest tests/ --cov=agentmap --cov-report=html # With coverage
python -m pytest tests/ -m "not slow"                    # Skip slow tests
python -m pytest tests/ -k "test_path_mocking"           # Pattern matching
```

### Performance & Quality
```bash
# Performance testing
python -m pytest tests/ -m "performance" --durations=10

# Code quality
python -m pytest tests/ --cov-fail-under=80
python -m pytest tests/ --benchmark-json=benchmark.json
```

## 🚀 Development Workflow

### When Writing New Tests
1. **Start with [Quick Reference](/docs/testing/quick-reference)** - Check standards and patterns
2. **Use [Comprehensive Guide](/docs/testing/comprehensive-guide)** - Find similar examples
3. **Reference [Troubleshooting](/docs/testing/troubleshooting)** - When tests fail
4. **Apply [Advanced Patterns](/docs/testing/advanced-patterns)** - For complex scenarios

### When Tests Fail
1. **Check [Quick Reference](/docs/testing/quick-reference#-quick-troubleshooting)** - Common fixes
2. **Use [Troubleshooting Guide](/docs/testing/troubleshooting)** - Diagnostic scripts
3. **Ask for help** - Reference specific sections for targeted assistance

### For AI-Assisted Development
- **Reference specific sections** when asking questions
- **Share error messages** and relevant code
- **Mention Python version** (critical for compatibility)
- **Use diagnostic scripts** from troubleshooting guide

## 🔗 Integration with Development

### Related Documentation
- **[Contributing Guide](/docs/contributing/)** - Overall development standards
- **[Architecture Overview](/docs/guides/development/best-practices)** - Understanding service structure
- **[CLI Commands](/docs/deployment/cli-commands)** - Commands for CLI testing

### Code Quality Standards
- **Coverage**: 80% minimum, 95% for critical paths
- **Performance**: Sub-second for simple operations
- **Security**: No authentication bypasses, config-driven only
- **Compatibility**: Python 3.11+ support required

## 💡 Testing Tips

### For New Contributors
- Start with the [Quick Reference](/docs/testing/quick-reference) for immediate guidance
- Use MockServiceFactory for all service dependencies
- Always use `create_autospec()` for agent mocks (Python 3.11 compatibility)
- Reference specific sections when asking for help

### For Experienced Developers
- Leverage [Advanced Patterns](/docs/testing/advanced-patterns) for complex scenarios
- Use the [Troubleshooting Guide](/docs/testing/troubleshooting) for debugging
- Consider performance implications in test design
- Contribute new patterns back to the documentation

### For AI-Assisted Development
- Reference specific documentation sections for context
- Use diagnostic scripts from the troubleshooting guide
- Share complete error messages and relevant code
- Mention your specific use case and Python version

---

**Ready to start testing?** Begin with the [Quick Reference](/docs/testing/quick-reference) for immediate guidance, or dive into the [Comprehensive Guide](/docs/testing/comprehensive-guide) for detailed examples.

**Need help?** Use the [Troubleshooting Guide](/docs/testing/troubleshooting) for debugging assistance, and reference specific sections when asking questions for targeted help.
