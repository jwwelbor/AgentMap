# AgentMap Developer Guide

This guide is for developers who want to contribute to AgentMap or understand its development workflow.

## 🚀 Quick Start for Contributors

### Prerequisites

- **Python 3.11+** (required)
- **Poetry** (recommended) - [Install Poetry](https://python-poetry.org/docs/#installation)
- **Git** for version control

### Development Setup

```bash
# 1. Fork and clone the repository
git clone https://github.com/jwwelbor/AgentMap.git
cd AgentMap

# 2. Install Poetry (if not already installed)
curl -sSL https://install.python-poetry.org | python3 -

# 3. Install dependencies and AgentMap in development mode
poetry install --with dev

# 4. Activate the Poetry shell (optional)
poetry shell

# 5. Verify installation
poetry run python -c "import agentmap; print(f'AgentMap {agentmap.__version__} ready!')"
```

### Development Workflow

```bash
# Run tests
poetry run pytest

# Run tests with coverage
poetry run pytest --cov=agentmap --cov-report=html

# Format code
poetry run black src/ tests/
poetry run isort src/ tests/

# Lint code
poetry run flake8 src/

# Run all quality checks at once
poetry run pytest && poetry run black src/ tests/ && poetry run isort src/ tests/ && poetry run flake8 src/
```

## 🏗️ Project Architecture

### Directory Structure

```
AgentMap/
├── src/agentmap/           # Main package source
│   ├── agents/             # Agent implementations
│   ├── graph/              # Graph building and execution
│   ├── services/           # Storage and external services
│   ├── config/             # Configuration management
│   ├── cli.py              # Command-line interface
│   └── runner.py           # Main graph runner
├── tests/                  # Test suite
├── examples/               # Example workflows
├── docs/                   # Documentation
├── .github/workflows/      # CI/CD pipelines
├── pyproject.toml          # Poetry configuration
└── poetry.lock             # Locked dependencies
```

### Key Components

- **Agents**: Modular components that perform specific tasks (LLM calls, file operations, etc.)
- **Graph Builder**: Converts CSV definitions into executable LangGraph workflows
- **Runner**: Executes workflows and manages state transitions
- **Services**: Storage backends (local files, cloud storage, vector databases)
- **CLI**: Command-line tools for running, scaffolding, and managing workflows

## 🔧 Development Tasks

### Adding a New Agent

1. **Create the agent class**:
```python
# src/agentmap/agents/my_custom_agent.py
from agentmap.agents.base_agent import BaseAgent
from typing import Dict, Any

class MyCustomAgent(BaseAgent):
    def process(self, inputs: Dict[str, Any]) -> Any:
        # Your agent logic here
        return {"result": "processed"}
```

2. **Register the agent**:
```python
# In the appropriate registry file
from .my_custom_agent import MyCustomAgent

AGENT_REGISTRY["my_custom"] = MyCustomAgent
```

3. **Add tests**:
```python
# tests/agents/test_my_custom_agent.py
def test_my_custom_agent():
    agent = MyCustomAgent()
    result = agent.process({"input": "test"})
    assert result["result"] == "processed"
```

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run specific test file
poetry run pytest tests/test_runner.py

# Run with verbose output
poetry run pytest -v

# Run with coverage report
poetry run pytest --cov=agentmap --cov-report=term-missing

# Run tests for specific functionality
poetry run pytest -k "test_csv" -v
```

### Building and Testing Locally

```bash
# Clean old builds
rm -rf dist/ src/agentmap.egg-info/

# Build the package
poetry build

# Test the built package
pip install dist/agentmap-*.whl
python -c "import agentmap; print('Success!')"

# Test optional dependencies
pip install "agentmap[llm]" --find-links dist/
pip install "agentmap[storage]" --find-links dist/
```

## 🧪 Testing Your Changes

### Pre-Release Testing Script

```bash
# Run the comprehensive test suite
poetry run python test_release.py
```

This script tests:
- Version consistency across files
- Package build process
- Import functionality
- Optional dependencies

### Manual Testing

```bash
# Test CLI commands
poetry run agentmap --help
poetry run agentmap run --graph TestGraph --csv examples/simple.csv

# Test specific workflows
poetry run python examples/run_example.py
```

## 📦 Release Process (for Maintainers)

### Version Bumping

```bash
# Update version in pyproject.toml and __init__.py
# Then run the test script
poetry run python test_release.py
```

### Creating a Release

1. **Prepare the release**:
```bash
# Update CHANGELOG.md with new version
# Commit all changes
git add .
git commit -m "Release v0.3.0"

# Create and push tag
git tag v0.3.0
git push origin main --tags
```

2. **GitHub Release**:
   - Go to GitHub → Releases → Create new release
   - Select the tag you just created
   - Add release notes from CHANGELOG.md
   - Publish release (this triggers automatic PyPI publication)

3. **Verify PyPI release**:
```bash
# Wait a few minutes, then test
pip install agentmap==0.3.0
pip install "agentmap[all]==0.3.0"
```

### Testing on TestPyPI (Optional)

```bash
# Configure TestPyPI
poetry config repositories.testpypi https://test.pypi.org/legacy/
poetry config pypi-token.testpypi YOUR_TEST_PYPI_TOKEN

# Publish to TestPyPI
poetry publish -r testpypi

# Test installation from TestPyPI  
pip install --index-url https://test.pypi.org/simple/ agentmap
```

## 🤝 Contributing Guidelines

### Code Style

- **Black** for code formatting
- **isort** for import sorting  
- **flake8** for linting
- **Type hints** where appropriate
- **Docstrings** for public APIs

### Commit Messages

Follow conventional commits:
```
feat: add new vector storage agent
fix: resolve memory leak in graph execution
docs: update installation instructions
test: add coverage for CSV parsing
```

### Pull Request Process

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feature/amazing-feature`
3. **Make** your changes and add tests
4. **Run** the full test suite: `poetry run pytest`
5. **Format** your code: `poetry run black src/ tests/`
6. **Commit** your changes with clear messages
7. **Push** to your fork and create a pull request

### Pull Request Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature  
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Tests pass locally
- [ ] Added tests for new functionality
- [ ] Updated documentation if needed

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Changes are documented
```

## 🐛 Debugging and Troubleshooting

### Common Development Issues

**Poetry Installation Issues:**
```bash
# If Poetry command not found
export PATH="$HOME/.local/bin:$PATH"

# If dependencies conflict
poetry lock --no-update
poetry install
```

**Import Issues:**
```bash
# Ensure you're in the Poetry environment
poetry shell

# Or run with Poetry prefix
poetry run python your_script.py
```

**Testing Issues:**
```bash
# Clear pytest cache
poetry run pytest --cache-clear

# Run tests in verbose mode
poetry run pytest -v -s
```

### Useful Development Commands

```bash
# See all Poetry commands
poetry --help

# Show current environment info
poetry env info

# Export requirements.txt for compatibility
poetry export -f requirements.txt --output requirements.txt

# Check for dependency issues
poetry check

# Update dependencies
poetry update
```

## 📚 Additional Resources

- **Poetry Documentation**: https://python-poetry.org/docs/
- **LangGraph Documentation**: https://langchain-ai.github.io/langgraph/
- **Pytest Documentation**: https://docs.pytest.org/
- **Black Documentation**: https://black.readthedocs.io/

## 🆘 Getting Help

- **GitHub Issues**: Report bugs and request features
- **GitHub Discussions**: Ask questions and share ideas  
- **Discord/Slack**: Join our community (links in main README)

---

**Happy coding! 🚀**
