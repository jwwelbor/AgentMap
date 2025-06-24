# AgentMap Development Guide

This guide provides detailed technical information for developers working on the AgentMap project.

## 🏗️ Architecture Overview

### Core Components

```
AgentMap
├── Core Framework
│   ├── Graph Builder Service
│   ├── Execution Engine
│   ├── Agent Registry
│   └── Dependency Injection
├── Agents
│   ├── LLM Agents (OpenAI, Claude, Gemini)
│   ├── Storage Agents (CSV, JSON, File)
│   ├── Utility Agents (Branching, Echo)
│   └── Custom Agents
├── Services
│   ├── Configuration Management
│   ├── Validation Services
│   ├── Storage Services
│   └── Execution Tracking
└── CLI & API
    ├── Command Line Interface
    ├── FastAPI Server
    └── Web Interface
```

### Design Patterns

- **Dependency Injection**: Service management and configuration
- **Factory Pattern**: Agent creation and instantiation
- **Registry Pattern**: Component discovery and registration
- **Builder Pattern**: Graph construction and validation
- **Observer Pattern**: Execution tracking and monitoring

## 🔧 Development Setup

### Environment Requirements

```bash
# Python 3.11+
python --version

# Poetry (recommended)
curl -sSL https://install.python-poetry.org | python3 -

# Pre-commit hooks
pip install pre-commit
pre-commit install
```

### Local Development

```bash
# Clone and setup
git clone https://github.com/jwwelbor/AgentMap.git
cd AgentMap

# Install dependencies
poetry install --with dev

# Setup pre-commit
pre-commit install

# Verify setup
poetry run pytest
```

### IDE Configuration

#### VS Code
```json
{
    "python.defaultInterpreterPath": "./.venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.formatting.provider": "black",
    "python.sortImports.args": ["--profile", "black"],
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
        "source.organizeImports": true
    }
}
```

#### PyCharm
- Set project interpreter to `.venv/bin/python`
- Enable Black formatter
- Configure isort for import sorting
- Enable flake8 inspection

## 🧪 Testing Strategy

### Test Categories

#### Unit Tests (`tests/unit/`)
- **Purpose**: Test individual components in isolation
- **Scope**: Single class or function
- **Dependencies**: Mocked external dependencies
- **Speed**: Fast execution (< 1 second per test)

#### Integration Tests (`tests/integration/`)
- **Purpose**: Test component interactions
- **Scope**: Multiple services working together
- **Dependencies**: Real DI container, mocked external APIs
- **Speed**: Medium execution (1-10 seconds per test)

#### End-to-End Tests (`tests/e2e/`)
- **Purpose**: Test complete workflows
- **Scope**: Full application with real dependencies
- **Dependencies**: Real services and external APIs
- **Speed**: Slow execution (10+ seconds per test)

### Test Patterns

#### Service Testing
```python
import pytest
from unittest.mock import Mock, patch
from agentmap.services.graph_builder_service import GraphBuilderService

class TestGraphBuilderService:
    def test_build_graph_success(self, mock_di_container):
        # Arrange
        service = GraphBuilderService(mock_di_container)
        graph_spec = {"name": "test", "nodes": []}
        
        # Act
        result = service.build_graph(graph_spec)
        
        # Assert
        assert result is not None
        assert result.name == "test"
```

#### Agent Testing
```python
import pytest
from agentmap.agents.base_agent import BaseAgent

class TestCustomAgent(BaseAgent):
    def test_agent_execution(self, mock_context):
        # Arrange
        agent = TestCustomAgent()
        input_data = {"test": "data"}
        
        # Act
        result = agent.execute(input_data, mock_context)
        
        # Assert
        assert result.success is True
        assert "output" in result.data
```

#### Integration Testing
```python
import pytest
from agentmap.di.containers import CoreContainer

class TestServiceIntegration:
    def test_service_coordination(self, di_container: CoreContainer):
        # Arrange
        graph_service = di_container.graph_builder_service()
        execution_service = di_container.graph_execution_service()
        
        # Act
        graph = graph_service.build_graph(graph_spec)
        result = execution_service.execute_graph(graph, initial_state)
        
        # Assert
        assert result.success is True
        assert result.execution_steps is not None
```

### Test Utilities

#### Mock Factories
```python
# tests/utils/mock_factory.py
class MockFactory:
    @staticmethod
    def create_mock_service():
        mock = Mock()
        mock.method.return_value = {"success": True}
        return mock
    
    @staticmethod
    def create_mock_di_container():
        container = Mock()
        container.service.return_value = MockFactory.create_mock_service()
        return container
```

#### Test Fixtures
```python
# tests/conftest.py
import pytest
from agentmap.di.containers import CoreContainer

@pytest.fixture
def di_container():
    """Create a test DI container with mocked external dependencies."""
    container = CoreContainer()
    container.config.from_dict({
        "llm": {"provider": "mock"},
        "storage": {"provider": "memory"}
    })
    return container

@pytest.fixture
def sample_graph_spec():
    """Provide a sample graph specification for testing."""
    return {
        "name": "test_graph",
        "nodes": [
            {
                "name": "start",
                "agent_type": "echo",
                "input_fields": ["input"],
                "output_field": "output"
            }
        ]
    }
```

## 🔍 Code Quality Tools

### Static Analysis

#### flake8 Configuration
```ini
# .flake8
[flake8]
max-line-length = 88
extend-ignore = E203, W503
exclude = 
    .git,
    __pycache__,
    .venv,
    build,
    dist,
    *.egg-info
```

#### Black Configuration
```toml
# pyproject.toml
[tool.black]
line-length = 88
target-version = ['py311']
include = '\.pyi?$'
extend-exclude = '''
/(
  \.eggs
  | \.git
  | \.hg
  | \.mypy_cache
  | \.tox
  | \.venv
  | build
  | dist
)/
'''
```

#### isort Configuration
```toml
# pyproject.toml
[tool.isort]
profile = "black"
multi_line_output = 3
line_length = 88
include_trailing_comma = true
force_grid_wrap = 0
use_parentheses = true
ensure_newline_before_comments = true
```

### Security Scanning

#### Bandit Configuration
```yaml
# .bandit
exclude_dirs: ['tests']
skips: ['B101', 'B601']
```

#### Security Checklist
- [ ] No hardcoded secrets
- [ ] Input validation implemented
- [ ] SQL injection prevention
- [ ] XSS protection
- [ ] CSRF protection
- [ ] Secure headers configured

## 📦 Package Management

### Dependency Categories

#### Core Dependencies
```toml
[tool.poetry.dependencies]
python = ">=3.11,<4.0"
pydantic = ">=2.6.3"
typer = ">=0.12.3"
fastapi = ">=0.111.0"
```

#### LLM Dependencies
```toml
[tool.poetry.extras.llm]
langchain-openai = ">=0.3.17"
langchain-anthropic = ">=0.3.13"
langchain-google-genai = "*"
```

#### Storage Dependencies
```toml
[tool.poetry.extras.storage]
firebase = "*"
firebase-admin = "*"
chromadb = "*"
```

#### Development Dependencies
```toml
[tool.poetry.group.dev.dependencies]
pytest = ">=8.0.0"
pytest-mock = ">=3.12.0"
pytest-cov = ">=4.0.0"
black = ">=23.0.0"
isort = ">=5.12.0"
flake8 = ">=6.0.0"
```

### Adding Dependencies

1. **Core Dependencies**
   ```bash
   poetry add package-name
   ```

2. **Optional Dependencies**
   ```bash
   poetry add --group llm package-name
   poetry add --group storage package-name
   ```

3. **Development Dependencies**
   ```bash
   poetry add --group dev package-name
   ```

4. **Update Requirements**
   ```bash
   poetry export -f requirements.txt --output requirements.txt
   ```

## 🚀 Performance Guidelines

### Optimization Strategies

#### Async/Await Usage
```python
import asyncio
from typing import Dict, Any

class AsyncService:
    async def process_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        # Use async for I/O operations
        result = await self.external_api_call(data)
        return result
```

#### Caching Implementation
```python
from functools import lru_cache
from typing import Dict, Any

class CachedService:
    @lru_cache(maxsize=128)
    def get_configuration(self, key: str) -> Dict[str, Any]:
        # Expensive operation cached
        return self.load_configuration(key)
```

#### Memory Management
```python
import gc
from contextlib import contextmanager

@contextmanager
def memory_management():
    """Context manager for memory-intensive operations."""
    try:
        yield
    finally:
        gc.collect()
```

### Performance Monitoring

#### Profiling
```python
import cProfile
import pstats
from io import StringIO

def profile_function(func, *args, **kwargs):
    """Profile a function and return statistics."""
    profiler = cProfile.Profile()
    profiler.enable()
    result = func(*args, **kwargs)
    profiler.disable()
    
    s = StringIO()
    stats = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
    stats.print_stats()
    return result, s.getvalue()
```

#### Memory Profiling
```python
import tracemalloc

def memory_profile(func):
    """Decorator to profile memory usage."""
    def wrapper(*args, **kwargs):
        tracemalloc.start()
        result = func(*args, **kwargs)
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        print(f"Memory usage: {current / 1024 / 1024:.2f} MB")
        return result
    return wrapper
```

## 🔧 Debugging

### Debug Configuration

#### VS Code Debug
```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Current File",
            "type": "python",
            "request": "launch",
            "program": "${file}",
            "console": "integratedTerminal",
            "cwd": "${workspaceFolder}",
            "env": {
                "PYTHONPATH": "${workspaceFolder}/src"
            }
        }
    ]
}
```

#### PyCharm Debug
- Set breakpoints in code
- Configure run configurations
- Use debug console for inspection

### Logging Configuration

```python
import logging
from typing import Dict, Any

def setup_logging(level: str = "INFO") -> None:
    """Configure logging for the application."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('agentmap.log'),
            logging.StreamHandler()
        ]
    )

class LoggerMixin:
    """Mixin to add logging capabilities to classes."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def log_debug(self, message: str, **kwargs: Any) -> None:
        self.logger.debug(message, extra=kwargs)
    
    def log_info(self, message: str, **kwargs: Any) -> None:
        self.logger.info(message, extra=kwargs)
    
    def log_error(self, message: str, **kwargs: Any) -> None:
        self.logger.error(message, extra=kwargs)
```

## 📚 Documentation Standards

### Code Documentation

#### Class Documentation
```python
class GraphBuilderService:
    """Service responsible for building and validating graph specifications.
    
    This service takes graph specifications and converts them into executable
    graph objects. It handles validation, dependency resolution, and error
    handling for graph construction.
    
    Attributes:
        di_container: Dependency injection container for service resolution
        validator: Graph validation service
        registry: Agent registry for component discovery
        
    Example:
        >>> service = GraphBuilderService(di_container)
        >>> graph = service.build_graph(graph_spec)
        >>> print(graph.name)
        'my_graph'
    """
    
    def __init__(self, di_container: CoreContainer):
        """Initialize the graph builder service.
        
        Args:
            di_container: Dependency injection container
            
        Raises:
            ConfigurationError: If required services are not available
        """
        self.di_container = di_container
        self.validator = di_container.graph_validation_service()
        self.registry = di_container.agent_registry_service()
```

#### Method Documentation
```python
def build_graph(self, spec: Dict[str, Any]) -> Graph:
    """Build a graph from specification.
    
    Args:
        spec: Graph specification dictionary containing nodes, edges, and
              configuration. Must include 'name' and 'nodes' keys.
              
    Returns:
        Graph: Executable graph object
        
    Raises:
        ValidationError: If specification is invalid
        ConfigurationError: If required agents are not available
        BuildError: If graph construction fails
        
    Example:
        >>> spec = {
        ...     "name": "test_graph",
        ...     "nodes": [{"name": "start", "agent_type": "echo"}]
        ... }
        >>> graph = service.build_graph(spec)
        >>> graph.name
        'test_graph'
    """
```

### API Documentation

#### OpenAPI/Swagger
```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(
    title="AgentMap API",
    description="API for building and executing AI agent workflows",
    version="0.3.0"
)

class GraphRequest(BaseModel):
    """Request model for graph execution."""
    graph_name: str
    initial_state: Dict[str, Any]
    
    class Config:
        schema_extra = {
            "example": {
                "graph_name": "hello_world",
                "initial_state": {"input": "Hello, AgentMap!"}
            }
        }

@app.post("/execute", response_model=ExecutionResult)
async def execute_graph(request: GraphRequest):
    """Execute a graph with the provided initial state.
    
    This endpoint takes a graph name and initial state, then executes
    the corresponding workflow and returns the results.
    """
    try:
        result = await execution_service.execute_graph(
            request.graph_name, 
            request.initial_state
        )
        return result
    except GraphNotFoundError:
        raise HTTPException(status_code=404, detail="Graph not found")
```

## 🔄 Release Process

### Version Management

#### Semantic Versioning
- **MAJOR**: Breaking changes
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes, backward compatible

#### Release Checklist
- [ ] All tests pass
- [ ] Documentation updated
- [ ] Changelog updated
- [ ] Version bumped
- [ ] Release notes prepared
- [ ] PyPI package built
- [ ] GitHub release created

### Deployment Pipeline

```yaml
# .github/workflows/release.yml
name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install poetry
          poetry install
      - name: Run tests
        run: poetry run pytest
      - name: Build package
        run: poetry build
      - name: Publish to PyPI
        run: poetry publish
        env:
          POETRY_PYPI_TOKEN_PYPI: ${{ secrets.PYPI_TOKEN }}
```

---

*This guide is a living document. Please update it as the project evolves.* 