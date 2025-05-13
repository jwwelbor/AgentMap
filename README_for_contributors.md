# AgentMap Developer Guide

This guide is for developers who want to contribute to AgentMap or use it as a dependency in their projects.

## Development Setup

### Prerequisites

- Python 3.11 or higher
- Poetry (recommended) or pip

### Installing for Development

```bash
# Clone the repository
git clone https://github.com/yourusername/agentmap.git
cd agentmap

# Install with Poetry (recommended)
poetry install

# Or install in development mode with pip
pip install -e .
```

### Running Tests

```bash
# Using Poetry
poetry run pytest

# Using pytest directly
pytest
```

## Using AgentMap as a Dependency

### In a Poetry Project

```bash
# Add AgentMap to your project
poetry add agentmap

# Or directly from GitHub
poetry add git+https://github.com/yourusername/agentmap.git
```

### In a pip Project

```bash
# Install from PyPI
pip install agentmap

# Or directly from GitHub
pip install git+https://github.com/jwwelbor/agentmap.git
```

### Example Code

```python
from agentmap.runner import run_graph
from agentmap.logging import get_logger

# Configure logging
logger = get_logger("MyApplication")

# Run a graph defined in a CSV file
result = run_graph(
    graph_name="MyWorkflow",
    initial_state={"input": "My workflow input"},
    csv_path="path/to/workflow.csv"
)

# Access the result
logger.info(f"Workflow output: {result}")
```

## Building and Publishing

### Build the Package

```bash
# Using Poetry
poetry build

# Using setuptools
python -m build
```

### Publish to PyPI

```bash
# Using Poetry
poetry publish

# To publish to TestPyPI first
poetry publish -r testpypi
```

## Project Structure

- `agentmap/`: Main package
  - `agents/`: Agent implementations
  - `graph/`: Graph building and execution
  - `logging/`: Logging utilities
  - `templates/`: Templates for scaffolding
- `tests/`: Test suite
- `examples/`: Example workflows and applications