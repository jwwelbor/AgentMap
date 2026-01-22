.PHONY: help format lint type-check test coverage clean install

help:
	@echo "AgentMap development tasks:"
	@echo "  make format       - Format code with isort and black"
	@echo "  make lint         - Run linters (flake8, ruff)"
	@echo "  make type-check   - Run mypy type checker"
	@echo "  make test         - Run pytest tests"
	@echo "  make coverage     - Run tests with coverage report"
	@echo "  make clean        - Clean build artifacts and cache"
	@echo "  make install      - Install development dependencies"

# Format code
format:
	@echo "Sorting imports with isort..."
	uv run isort --sp pyproject.toml src/ tests/
	@echo "Formatting code with Black..."
	uv run black src/ tests/
	@echo "✓ Formatting complete"

# Run linters
lint:
	@echo "Running flake8 linter..."
	uv run flake8 src/ tests/
	@echo "✓ Linting complete"

# Type checking
type-check:
	@echo "Running mypy type checker..."
	uv run mypy src/
	@echo "✓ Type checking complete"

# Run tests
test:
	@echo "Running pytest..."
	uv run pytest tests/
	@echo "✓ Tests complete"

# Run tests with coverage
coverage:
	@echo "Running tests with coverage..."
	uv run pytest --cov=src --cov-report=html tests/
	@echo "✓ Coverage report generated in htmlcov/index.html"

# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .mypy_cache .coverage htmlcov/ dist/ build/ *.egg-info/
	@echo "✓ Clean complete"

# Install dev dependencies
install:
	@echo "Installing development dependencies..."
	uv sync --with dev
	@echo "✓ Installation complete"

.DEFAULT_GOAL := help
