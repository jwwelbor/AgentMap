# Contributing to AgentMap

Thank you for your interest in contributing to AgentMap! This guide will help you get started with contributing to the project.

## 🚀 Quick Start

### Prerequisites
- Python 3.11 or higher
- Git
- Poetry (recommended) or pip

### Setup Development Environment

1. **Fork and Clone**
   ```bash
   git clone https://github.com/YOUR_USERNAME/AgentMap.git
   cd AgentMap
   ```

2. **Install Dependencies**
   ```bash
   # Using Poetry (recommended)
   poetry install --with dev
   
   # Or using pip
   pip install -e ".[dev]"
   ```

3. **Install Pre-commit Hooks**
   ```bash
   pre-commit install
   ```

4. **Verify Setup**
   ```bash
   # Run tests
   poetry run pytest
   
   # Check code quality
   poetry run flake8 src/ tests/
   poetry run black --check src/ tests/
   ```

## 🔧 Development Workflow

### 1. Create a Feature Branch
```bash
git checkout -b feature/your-feature-name
# or
git checkout -b bugfix/issue-description
```

### 2. Make Your Changes
- Follow the coding standards in `PROJECT_RULES.md`
- Write tests for new functionality
- Update documentation as needed

### 3. Test Your Changes
```bash
# Run all tests
poetry run pytest

# Run specific test categories
poetry run pytest tests/unit/
poetry run pytest tests/integration/
poetry run pytest tests/e2e/

# Run with coverage
poetry run pytest --cov=agentmap --cov-report=html
```

### 4. Format and Lint
```bash
# Format code
poetry run black src/ tests/
poetry run isort src/ tests/

# Check linting
poetry run flake8 src/ tests/
```

### 5. Commit Your Changes
```bash
git add .
git commit -m "feat(component): add new feature description"
```

### 6. Push and Create Pull Request
```bash
git push origin feature/your-feature-name
```

## 📝 Code Standards

### Python Code Style
- Use **Black** for formatting (line length: 88)
- Use **isort** for import sorting
- Follow **PEP 8** guidelines
- Use type hints for all public APIs

### Naming Conventions
- **Classes**: `PascalCase` (e.g., `GraphBuilderService`)
- **Functions/Methods**: `snake_case` (e.g., `build_graph`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_TIMEOUT`)
- **Files**: `snake_case` (e.g., `graph_builder_service.py`)

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

## 🧪 Testing Guidelines

### Test Structure
- **Unit Tests**: `tests/unit/` - Fast, isolated tests
- **Integration Tests**: `tests/integration/` - Service coordination
- **End-to-End Tests**: `tests/e2e/` - Full workflow tests

### Test Naming
- **Files**: `test_*.py`
- **Classes**: `Test*`
- **Functions**: `test_*`

### Test Patterns
```python
import pytest
from unittest.mock import Mock, patch

class TestYourService:
    def test_specific_behavior(self, mock_dependency):
        # Arrange
        service = YourService(mock_dependency)
        
        # Act
        result = service.method_under_test()
        
        # Assert
        assert result == expected_value
```

### Coverage Requirements
- **Minimum**: 80% overall coverage
- **Critical Paths**: 95% coverage
- **Public APIs**: 100% coverage

## 📚 Documentation

### Code Documentation
- Use Google-style docstrings
- Include type hints
- Add examples for complex functions
- Document public APIs thoroughly

### Example Docstring
```python
def process_data(data: Dict[str, Any]) -> ProcessedResult:
    """Process input data and return structured results.
    
    Args:
        data: Input data dictionary containing raw information.
        
    Returns:
        ProcessedResult: Structured and validated data.
        
    Raises:
        ValidationError: If data format is invalid.
        
    Example:
        >>> data = {"input": "test", "config": {"option": "value"}}
        >>> result = process_data(data)
        >>> print(result.status)
        'success'
    """
```

### Documentation Updates
- Update README.md for user-facing changes
- Update docstrings for API changes
- Add examples for new features
- Update architecture docs for structural changes

## 🔍 Code Review Process

### Before Submitting
- [ ] All tests pass
- [ ] Code follows style guidelines
- [ ] Documentation is updated
- [ ] No security vulnerabilities
- [ ] Performance impact considered

### Pull Request Template
```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Refactoring
- [ ] Performance improvement

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing completed

## Checklist
- [ ] Code follows project standards
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No breaking changes (or documented)
```

## 🐛 Reporting Issues

### Bug Reports
When reporting bugs, please include:
- **Description**: Clear explanation of the issue
- **Steps to Reproduce**: Detailed reproduction steps
- **Expected Behavior**: What should happen
- **Actual Behavior**: What actually happens
- **Environment**: OS, Python version, AgentMap version
- **Additional Context**: Logs, screenshots, etc.

### Feature Requests
For feature requests, include:
- **Use Case**: Why this feature is needed
- **Proposed Solution**: How it should work
- **Alternatives**: Other approaches considered
- **Impact**: Who benefits from this feature

## 🤝 Community Guidelines

### Communication
- Be respectful and constructive
- Use inclusive language
- Help others learn and grow
- Provide constructive feedback

### Getting Help
- Check existing documentation
- Search existing issues
- Ask questions in discussions
- Join community channels

## 🏆 Recognition

Contributors are recognized through:
- **Contributors List**: GitHub contributors page
- **Release Notes**: Credit in changelog
- **Documentation**: Attribution in docs
- **Community**: Recognition in discussions

## 📋 Contributor License Agreement

By contributing to AgentMap, you agree that your contributions will be licensed under the MIT License.

## 🆘 Need Help?

If you need help with contributing:
1. Check the documentation
2. Search existing issues
3. Create a new issue with the "help wanted" label
4. Ask in discussions

Thank you for contributing to AgentMap! 🎉 