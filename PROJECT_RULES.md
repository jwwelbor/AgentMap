# AgentMap Project Rules

## 📋 Overview

This document defines the rules, standards, and best practices for contributing to the AgentMap project. AgentMap is a declarative orchestration framework that transforms CSV files into powerful AI agent workflows.

## 🏗️ Project Architecture

### Core Principles
- **Clean Architecture**: Separation of concerns with clear domain boundaries
- **Dependency Injection**: Use of dependency injection for service management
- **Service-Oriented Design**: Modular services with well-defined interfaces
- **Test-Driven Development**: Comprehensive testing at all levels

### Directory Structure
```
src/agentmap/
├── agents/           # Agent implementations
├── core/            # Core framework components
├── di/              # Dependency injection containers
├── exceptions/      # Custom exception classes
├── models/          # Data models and schemas
├── services/        # Business logic services
├── templates/       # Code generation templates
└── prompts.py       # Prompt management
```

## 🐍 Python Standards

### Code Style
- **Black**: Line length 88, Python 3.11+ target
- **isort**: Black-compatible import sorting
- **flake8**: Code quality enforcement
- **Type Hints**: Required for all public APIs

### Naming Conventions
- **Classes**: PascalCase (`GraphBuilderService`)
- **Functions/Methods**: snake_case (`build_graph`)
- **Constants**: UPPER_SNAKE_CASE (`DEFAULT_TIMEOUT`)
- **Private Methods**: Leading underscore (`_internal_helper`)
- **Files**: snake_case (`graph_builder_service.py`)

### Import Organization
```python
# Standard library imports
import os
import sys
from typing import Dict, List, Optional

# Third-party imports
import pandas as pd
from pydantic import BaseModel

# Local imports
from agentmap.models.graph import Graph
from agentmap.services.base import BaseService
```

## 🧪 Testing Standards

### Test Structure
- **Unit Tests**: `tests/unit/` - Fast, isolated tests with mocked dependencies
- **Integration Tests**: `tests/integration/` - Service coordination tests
- **End-to-End Tests**: `tests/e2e/` - Full workflow tests

### Test Naming
- **Files**: `test_*.py`
- **Classes**: `Test*`
- **Functions**: `test_*`
- **Fixtures**: `*_fixture`

### Test Coverage Requirements
- **Minimum Coverage**: 80% overall
- **Critical Paths**: 95% coverage
- **Public APIs**: 100% coverage

### Test Patterns
```python
import pytest
from unittest.mock import Mock, patch

class TestGraphBuilderService:
    def test_build_graph_success(self, mock_di_container):
        # Arrange
        service = GraphBuilderService(mock_di_container)
        
        # Act
        result = service.build_graph("test_graph")
        
        # Assert
        assert result is not None
        assert result.name == "test_graph"
```

## 🔧 Development Workflow

### Branch Strategy
- **main**: Production-ready code
- **develop**: Integration branch
- **feature/***: New features
- **bugfix/***: Bug fixes
- **hotfix/***: Critical production fixes

### Commit Standards
- **Format**: `type(scope): description`
- **Types**: feat, fix, docs, style, refactor, test, chore
- **Scope**: Component or module affected
- **Description**: Clear, concise explanation

Examples:
```
feat(agents): add new anthropic agent implementation
fix(core): resolve circular import in graph builder
docs(api): update CSV schema documentation
test(services): add integration tests for storage services
```

### Pull Request Requirements
- **Title**: Clear, descriptive title
- **Description**: Detailed explanation of changes
- **Tests**: All tests must pass
- **Coverage**: Maintain or improve test coverage
- **Documentation**: Update relevant docs
- **Review**: At least one approval required

## 📦 Package Management

### Dependencies
- **Poetry**: Primary package manager
- **Requirements**: Minimal `requirements.txt` for pip users
- **Version Pinning**: Use exact versions in production

### Dependency Categories
- **Core**: Essential framework dependencies
- **LLM**: Language model providers
- **Storage**: Database and storage integrations
- **Dev**: Development and testing tools

### Adding Dependencies
1. Add to appropriate section in `pyproject.toml`
2. Update `requirements.txt` if needed
3. Document purpose in commit message
4. Consider impact on package size

## 🔍 Code Quality

### Static Analysis
- **flake8**: Code style and complexity
- **mypy**: Type checking (when implemented)
- **bandit**: Security analysis
- **autoflake**: Remove unused imports

### Pre-commit Hooks
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.0.0
    hooks:
      - id: black
  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort
  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
```

### Code Review Checklist
- [ ] Code follows style guidelines
- [ ] Tests are comprehensive and pass
- [ ] Documentation is updated
- [ ] No security vulnerabilities
- [ ] Performance impact considered
- [ ] Backward compatibility maintained

## 🚀 Deployment

### Version Management
- **Semantic Versioning**: MAJOR.MINOR.PATCH
- **Changelog**: Document all changes
- **Release Notes**: User-facing documentation

### CI/CD Pipeline
- **Build**: Poetry build and package
- **Test**: Unit, integration, and e2e tests
- **Quality**: Static analysis and coverage
- **Deploy**: PyPI publication

### Environment Configuration
- **Development**: `agentmap_local_config.yaml`
- **Testing**: Environment variables in CI
- **Production**: Secure configuration management

## 📚 Documentation

### Documentation Standards
- **README**: Project overview and quick start
- **API Docs**: Comprehensive API reference
- **Examples**: Working code examples
- **Architecture**: System design documentation

### Documentation Structure
```
docs/
├── index.html          # Main documentation site
├── usage/              # User guides
├── architecture/       # System design docs
├── api/               # API reference
└── examples/          # Code examples
```

### Code Documentation
- **Docstrings**: Google-style docstrings
- **Type Hints**: Comprehensive type annotations
- **Comments**: Explain complex logic
- **Examples**: Include usage examples

## 🔒 Security

### Security Standards
- **Secrets Management**: Never commit secrets
- **Input Validation**: Validate all external inputs
- **Dependency Scanning**: Regular security audits
- **Access Control**: Principle of least privilege

### Security Checklist
- [ ] No hardcoded secrets
- [ ] Input sanitization implemented
- [ ] Dependencies are up-to-date
- [ ] Security headers configured
- [ ] Error messages don't leak information

## 🐛 Issue Management

### Issue Templates
- **Bug Report**: Structured bug reporting
- **Feature Request**: New feature proposals
- **Documentation**: Documentation improvements

### Issue Labels
- **bug**: Software defects
- **enhancement**: New features
- **documentation**: Documentation updates
- **good first issue**: Beginner-friendly
- **help wanted**: Community assistance needed

## 🤝 Contributing

### Getting Started
1. Fork the repository
2. Create a feature branch
3. Set up development environment
4. Make changes following standards
5. Submit pull request

### Development Environment
```bash
# Clone and setup
git clone https://github.com/jwwelbor/AgentMap.git
cd AgentMap

# Install dependencies
poetry install --with dev

# Run tests
poetry run pytest

# Format code
poetry run black src/ tests/
poetry run isort src/ tests/
```

### Community Guidelines
- **Respectful Communication**: Be kind and constructive
- **Inclusive Environment**: Welcome diverse perspectives
- **Help Others**: Support new contributors
- **Follow Standards**: Adhere to project rules

## 📊 Performance

### Performance Standards
- **Response Time**: Sub-second for simple workflows
- **Memory Usage**: Efficient resource utilization
- **Scalability**: Support for concurrent execution
- **Monitoring**: Comprehensive metrics collection

### Performance Guidelines
- Use async/await for I/O operations
- Implement caching where appropriate
- Profile code for bottlenecks
- Monitor resource usage

## 🔄 Maintenance

### Regular Tasks
- **Dependency Updates**: Monthly security updates
- **Code Review**: Regular architecture reviews
- **Documentation**: Keep docs current
- **Testing**: Maintain test coverage

### Technical Debt
- **Track Issues**: Document technical debt
- **Prioritize**: Address high-impact items
- **Refactor**: Regular code improvements
- **Monitor**: Track debt metrics

---

## 📝 Enforcement

These rules are enforced through:
- **Automated Checks**: CI/CD pipeline validation
- **Code Review**: Peer review process
- **Documentation**: Clear guidelines and examples
- **Community**: Shared understanding and support

## 🔄 Updates

This document is living and should be updated as the project evolves. Major changes require:
- Team discussion and consensus
- Documentation updates
- Communication to contributors
- Gradual migration period

---

*Last updated: [Current Date]*
*Version: 1.0* 