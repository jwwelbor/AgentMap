---
sidebar_position: 99
title: Contributing to AgentMap - Developer Guide
description: Complete guide for contributing to AgentMap including setup, coding standards, testing requirements, and pull request process. Help build the future of agentic AI workflows.
keywords: [contributing, open source, developer guide, agentmap contribution, python development, agentic AI development, multi-agent systems, code contribution]
image: /img/agentmap-hero.png
---

# Contributing to AgentMap

Welcome to the AgentMap community! 🎉 We're excited that you want to contribute to the future of agentic AI workflows and multi-agent systems. This guide will help you get started with contributing to AgentMap, from your first bug report to major feature development.

## 🚀 Quick Start for Contributors

### Prerequisites
- **Python 3.11+** - AgentMap is built for modern Python
- **Poetry** - Our preferred package manager
- **Git** - For version control and collaboration

### Development Environment Setup

```bash
# 1. Fork and clone the repository
git clone https://github.com/jwwelbor/AgentMap.git
cd AgentMap

# 2. Install dependencies with development tools
poetry install --with dev

# 3. Set up pre-commit hooks (optional but recommended)
poetry run pre-commit install

# 4. Run tests to verify setup
poetry run pytest

# 5. Format code to match project standards
poetry run black src/ tests/
poetry run isort src/ tests/

# 6. Start developing!
```

## 📋 Project Overview

AgentMap is a declarative orchestration framework that transforms CSV files into powerful AI agent workflows. Our mission is to make agentic AI accessible while maintaining enterprise-grade reliability and performance.

### Core Principles
- **Clean Architecture**: Clear separation of concerns with domain boundaries
- **Dependency Injection**: Service management through DI containers
- **Service-Oriented Design**: Modular services with well-defined interfaces
- **Test-Driven Development**: Comprehensive testing at all levels
- **Developer Experience**: Tools and patterns that make development enjoyable

## 🏗️ Architecture Overview

Understanding AgentMap's architecture will help you contribute effectively:

```
src/agentmap/
├── agents/           # Agent implementations and types
├── core/            # Core framework components
├── di/              # Dependency injection containers
├── exceptions/      # Custom exception classes
├── models/          # Data models and schemas
├── services/        # Business logic services
├── templates/       # Code generation templates
└── prompts.py       # Prompt management system
```

### Key Components
- **Agents**: Individual AI components that perform specific tasks
- **Services**: Business logic that orchestrates agents and manages state
- **Models**: Data structures using Pydantic for validation
- **DI Container**: Manages service dependencies and lifecycle

## 🐍 Code Standards

### Code Style
We use automated tooling to maintain consistent code quality:

- **Black**: Code formatting with 88-character line length
- **isort**: Import sorting compatible with Black
- **flake8**: Code quality and complexity enforcement
- **Type Hints**: Required for all public APIs

### Naming Conventions
```python
# Classes - PascalCase
class GraphBuilderService:
    pass

# Functions and methods - snake_case
def build_agent_graph(self):
    pass

# Constants - UPPER_SNAKE_CASE
DEFAULT_TIMEOUT = 30

# Private methods - leading underscore
def _internal_helper(self):
    pass

# Files - snake_case
# graph_builder_service.py
```

### Import Organization
Follow this import order in all Python files:

```python
# 1. Standard library imports
import os
import sys
from typing import Dict, List, Optional

# 2. Third-party imports
import pandas as pd
from pydantic import BaseModel

# 3. Local imports
from agentmap.models.graph import Graph
from agentmap.services.base import BaseService
```

## 🧪 Testing Standards

Quality testing is crucial for AgentMap's reliability. We use a three-tier testing approach:

### Test Structure
- **Unit Tests** (`tests/unit/`) - Fast, isolated tests with mocked dependencies
- **Integration Tests** (`tests/integration/`) - Service coordination tests
- **End-to-End Tests** (`tests/e2e/`) - Complete workflow tests

### Coverage Requirements
- **Overall Minimum**: 80% code coverage
- **Critical Paths**: 95% coverage for core functionality
- **Public APIs**: 100% coverage for all public interfaces

### Test Naming and Organization
```python
# File: test_graph_builder_service.py
import pytest
from unittest.mock import Mock, patch

class TestGraphBuilderService:
    """Test suite for GraphBuilderService"""
    
    def test_build_graph_success(self, mock_di_container):
        """Test successful graph building with valid input"""
        # Arrange
        service = GraphBuilderService(mock_di_container)
        
        # Act
        result = service.build_graph("test_graph")
        
        # Assert
        assert result is not None
        assert result.name == "test_graph"
    
    def test_build_graph_invalid_input_raises_exception(self):
        """Test that invalid input raises appropriate exception"""
        # Test implementation here
        pass
```

### Running Tests
```bash
# Run all tests
poetry run pytest

# Run with coverage report
poetry run pytest --cov=src/agentmap --cov-report=html

# Run specific test categories
poetry run pytest tests/unit/
poetry run pytest tests/integration/
poetry run pytest tests/e2e/

# Run tests matching a pattern
poetry run pytest -k "test_graph_builder"
```

## 🔧 Development Workflow

### Branch Strategy
We follow a structured branching model:

- **main** - Production-ready code, always deployable
- **develop** - Integration branch for ongoing development
- **feature/\*** - New features (`feature/add-anthropic-agent`)
- **bugfix/\*** - Bug fixes (`bugfix/fix-memory-leak`)
- **hotfix/\*** - Critical production fixes

### Commit Standards
Use conventional commits for clear project history:

**Format**: `type(scope): description`

**Types**:
- `feat` - New features
- `fix` - Bug fixes  
- `docs` - Documentation updates
- `style` - Code style changes (formatting, etc.)
- `refactor` - Code refactoring without feature changes
- `test` - Test additions or modifications
- `chore` - Build process or tool changes

**Examples**:
```bash
feat(agents): add new anthropic agent implementation
fix(core): resolve circular import in graph builder
docs(api): update CSV schema documentation
test(services): add integration tests for storage services
refactor(di): simplify service registration pattern
```

### Pull Request Process

#### 1. Before You Start
- Check existing issues and PRs to avoid duplication
- Open an issue for discussion before major changes
- Ensure your local environment is properly set up

#### 2. Development Process
```bash
# Create feature branch from develop
git checkout develop
git pull origin develop
git checkout -b feature/your-feature-name

# Make your changes following coding standards
# Add tests for new functionality
# Update documentation as needed

# Run quality checks
poetry run black src/ tests/
poetry run isort src/ tests/
poetry run flake8 src/ tests/
poetry run pytest --cov=src/agentmap
```

#### 3. Pull Request Requirements
Your PR must include:

- [ ] **Clear title and description** - Explain what and why
- [ ] **Tests** - All new code must have tests
- [ ] **Documentation** - Update relevant docs
- [ ] **Passing CI** - All automated checks must pass
- [ ] **Code review** - At least one approval required
- [ ] **Changelog entry** - Add to CHANGELOG if applicable

#### 4. PR Template
Use this template for your pull requests:

```markdown
## Description
Brief description of changes and motivation.

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] All tests passing
- [ ] Manual testing completed

## Documentation
- [ ] Code comments updated
- [ ] Documentation updated
- [ ] CHANGELOG updated (if applicable)

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review of code completed
- [ ] Tests added for new functionality
- [ ] Documentation updated
- [ ] No new security vulnerabilities introduced
```

## 📦 Dependencies and Package Management

### Adding Dependencies
When adding new dependencies:

1. **Consider necessity** - Is this dependency essential?
2. **Evaluate alternatives** - Are there lighter alternatives?
3. **Check security** - Review the package's security history
4. **Update documentation** - Document the purpose and usage

```bash
# Add a production dependency
poetry add package-name

# Add a development dependency
poetry add --group dev package-name

# Update requirements.txt for pip users
poetry export -f requirements.txt --output requirements.txt
```

### Dependency Categories
- **Core** - Essential framework dependencies
- **LLM** - Language model provider integrations
- **Storage** - Database and storage backends
- **Dev** - Development and testing tools

## 🔍 Code Quality and Review

### Automated Quality Checks
We use several tools to maintain code quality:

```bash
# Format code
poetry run black src/ tests/

# Sort imports
poetry run isort src/ tests/

# Check style and complexity
poetry run flake8 src/ tests/

# Security analysis
poetry run bandit -r src/

# Remove unused imports
poetry run autoflake --remove-all-unused-imports --recursive src/ tests/
```

### Code Review Guidelines

#### For Authors
- Keep PRs focused and reasonably sized
- Write clear commit messages and PR descriptions
- Respond promptly to review feedback
- Test thoroughly before requesting review

#### For Reviewers
- Review for correctness, performance, and maintainability
- Check test coverage and documentation
- Provide constructive, specific feedback
- Approve when the code meets our quality standards

### Review Checklist
- [ ] Code follows style guidelines and conventions
- [ ] Tests are comprehensive and pass
- [ ] Documentation is updated and accurate
- [ ] No obvious security vulnerabilities
- [ ] Performance impact is acceptable
- [ ] Backward compatibility is maintained (unless breaking change)

## 🚀 Documentation Contributions

Good documentation is just as important as good code. You can contribute by:

### Documentation Types
- **API Documentation** - Code reference and examples
- **User Guides** - Step-by-step instructions and tutorials
- **Architecture Docs** - System design and patterns
- **Examples** - Working code samples and use cases

### Documentation Standards
- **Clear Writing** - Use simple, direct language
- **Code Examples** - Include working examples
- **Consistency** - Follow established patterns
- **SEO Optimization** - Include proper metadata

### Docstring Format
Use Google-style docstrings for all public APIs:

```python
def build_agent_graph(self, config: Dict[str, Any]) -> AgentGraph:
    """Build an agent graph from configuration.
    
    Creates a new agent graph by parsing the provided configuration
    and instantiating the necessary agents and connections.
    
    Args:
        config: Dictionary containing agent and connection definitions.
            Must include 'agents' and 'connections' keys.
    
    Returns:
        AgentGraph: A configured graph ready for execution.
    
    Raises:
        ConfigurationError: If config is invalid or missing required keys.
        ServiceError: If required services are unavailable.
    
    Example:
        >>> config = {
        ...     "agents": [{"name": "weather", "type": "api"}],
        ...     "connections": [{"from": "start", "to": "weather"}]
        ... }
        >>> graph = service.build_agent_graph(config)
        >>> graph.run()
    """
```

## 🐛 Bug Reports and Feature Requests

### Reporting Bugs
When reporting bugs, please include:

- **Environment details** - Python version, OS, AgentMap version
- **Steps to reproduce** - Clear, minimal reproduction steps
- **Expected behavior** - What should happen
- **Actual behavior** - What actually happens
- **Error messages** - Full stack traces and logs
- **Minimal example** - Code that demonstrates the issue

### Feature Requests
For new features, please provide:

- **Use case** - Why is this feature needed?
- **Proposed solution** - How should it work?
- **Alternatives** - What other approaches did you consider?
- **Breaking changes** - Would this affect existing code?

## 🔒 Security

### Security Guidelines
- **Never commit secrets** - Use environment variables
- **Validate inputs** - Sanitize all external inputs
- **Follow security best practices** - Regular dependency updates
- **Report vulnerabilities responsibly** - Use private disclosure

### Security Checklist
- [ ] No hardcoded secrets or credentials
- [ ] Input validation implemented
- [ ] Dependencies are up-to-date
- [ ] Error messages don't leak sensitive information
- [ ] Access controls follow principle of least privilege

## 🤝 Community Guidelines

### Communication Standards
- **Be respectful and inclusive** - Welcome diverse perspectives
- **Be constructive** - Focus on solutions, not problems
- **Be patient** - Help newcomers learn and contribute
- **Be collaborative** - Work together toward shared goals

### Getting Help
- **Documentation** - Check our comprehensive docs first
- **Discussions** - Use GitHub Discussions for questions
- **Issues** - Report bugs and request features
- **Community** - Join our developer community

### Recognition
We believe in recognizing our contributors:
- **Contributors file** - All contributors are acknowledged
- **Release notes** - Major contributions are highlighted
- **Community spotlight** - Outstanding contributions are featured

## 📊 Performance and Optimization

### Performance Guidelines
- **Response Time** - Sub-second for simple workflows
- **Memory Usage** - Efficient resource utilization
- **Scalability** - Support concurrent execution
- **Monitoring** - Comprehensive metrics collection

### Optimization Best Practices
- Use async/await for I/O operations
- Implement caching where appropriate
- Profile code to identify bottlenecks
- Monitor resource usage in production

## 🔄 Release Process

### Version Management
We follow semantic versioning (MAJOR.MINOR.PATCH):
- **MAJOR** - Breaking changes
- **MINOR** - New features (backward compatible)
- **PATCH** - Bug fixes (backward compatible)

### Release Checklist
- [ ] All tests passing
- [ ] Documentation updated
- [ ] CHANGELOG updated
- [ ] Version number bumped
- [ ] Release notes prepared
- [ ] Security review completed

## 📚 Learning Resources

### Getting Started
- **[Quick Start Guide](../getting-started)** - Build your first workflow
- **[Core Concepts](../core-features)** - Understand AgentMap fundamentals
- **[Architecture Overview](./clean-architecture-overview)** - System design patterns

### Advanced Topics
- **[Agent Development Contract](/docs/guides/development/agents/agent-development)** - Build custom agents
- **[Service Injection Patterns](/docs/contributing/service-injection)** - DI system usage
- **[Memory Management](/docs/guides/development/agent-memory/memory-management)** - State and context

### Examples and Tutorials
- **[Tutorial Collection](../tutorials/)** - Step-by-step tutorials
- **[Example Workflows](../examples/)** - Real-world implementations
- **[Best Practices](/docs/guides/development/best-practices)** - Proven patterns and approaches

## ❓ Frequently Asked Questions

### Development Environment
**Q: Which Python version should I use?**
A: Python 3.11+ is required. We recommend using the latest stable version.

**Q: Can I use pip instead of Poetry?**
A: While possible, Poetry is strongly recommended for development as it manages dependencies and virtual environments more effectively.

### Contributing Process
**Q: How do I know what to work on?**
A: Check our GitHub issues for "good first issue" labels, or open a discussion about features you'd like to add.

**Q: How long does code review take?**
A: We aim to provide initial feedback within 48 hours. Complex changes may require additional review cycles.

### Technical Questions
**Q: How do I add a new agent type?**
A: See our [Agent Development Contract](/docs/guides/development/agents/agent-development) guide for comprehensive instructions.

**Q: Can I contribute integrations for new LLM providers?**
A: Absolutely! New LLM integrations are always welcome. Follow our service patterns for consistency.

## 📞 Getting Support

If you need help contributing to AgentMap:

- **📖 Documentation** - Start with our comprehensive guides
- **💬 GitHub Discussions** - Ask questions and share ideas
- **🐛 GitHub Issues** - Report bugs and request features
- **📧 Direct Contact** - Reach out to maintainers for urgent issues

## 🎉 Thank You!

Thank you for your interest in contributing to AgentMap! Every contribution, whether it's code, documentation, bug reports, or feature ideas, helps make AgentMap better for everyone.

Together, we're building the future of agentic AI workflows and multi-agent systems. Your contributions make that vision a reality.

**Ready to contribute?** 🚀

1. **[Set up your development environment](#-quick-start-for-contributors)**
2. **[Check out our current issues](https://github.com/jwwelbor/AgentMap/issues)**
3. **[Join the discussion](https://github.com/jwwelbor/AgentMap/discussions)**

Welcome to the AgentMap community! 🎊

---

*This contributing guide is a living document. If you find ways to improve it, please submit a pull request!*

**Last updated**: June 27, 2025  
**Version**: 1.0
