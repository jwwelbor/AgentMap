# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AgentMap is a declarative orchestration framework that transforms CSV files into LangGraph agentic workflows. Users define multi-agent systems in spreadsheet format instead of writing boilerplate code. Python 3.11+, built with hatchling.

## Common Commands

```bash
# Install dev dependencies
uv sync --with dev

# Run all tests
uv run pytest tests/

# Run a single test file
uv run pytest tests/unit/path/to/test_file.py

# Run a single test
uv run pytest tests/unit/path/to/test_file.py::TestClass::test_method -v

# Format code
uv run isort --sp pyproject.toml src/ tests/ && uv run black src/ tests/

# Lint
uv run flake8 src/ tests/

# Type check
uv run mypy src/

# Run with coverage
uv run pytest --cov=src --cov-report=html tests/
```

All Makefile targets use `uv run` — `make format`, `make lint`, `make type-check`, `make test`, `make coverage`.

## Architecture

### Dependency Injection (Core Pattern)

The entire application is wired through `dependency_injector`. The DI container is the central architectural concept.

- **`src/agentmap/di/containers.py`** — `ApplicationContainer` composed from modular container parts (`CoreContainer`, `LLMContainer`, `StorageContainer`, `GraphAgentContainer`, etc.) in `di/container_parts/`
- **`src/agentmap/di/__init__.py`** — `initialize_di()` is the main bootstrap function used by all entry points (CLI, FastAPI, serverless). It discovers `agentmap_config.yaml` and creates the container.
- Services are resolved lazily from the container. To get a service: `container.some_service()`

### Runtime API (Public Facade)

**`src/agentmap/runtime_api.py`** re-exports functions from split runtime modules in `src/agentmap/runtime/`:
- `init_ops.py` — `ensure_initialized()`, `get_container()`
- `workflow_ops.py` — `run_workflow()`, `resume_workflow()`, `list_graphs()`, `inspect_graph()`, `validate_workflow()`
- `bundle_ops.py` — `scaffold_agents()`, `update_bundle()`
- `system_ops.py` — `diagnose_system()`, `get_config()`, `refresh_cache()`

### Graph Pipeline

CSV → `csv_graph_parser_service` → `GraphBundle` model → `graph_builder_service` → LangGraph `StateGraph` → `graph_runner_service` executes

- **`services/csv_graph_parser/`** — Parses CSV into graph specifications
- **`services/graph/`** — Building, running, scaffolding, and registry services
- **`models/graph_bundle.py`** — `GraphBundle` is the serializable intermediate representation of a compiled graph

### Agents

- **`agents/base_agent.py`** — `BaseAgent` that all agents extend
- **`agents/builtins/`** — Built-in agent types: `default`, `echo`, `input`, `branching`, `success`, `failure`, `human`, `suspend`, `tool`, `graph` (sub-workflows), `orchestrator`, `summary`
- **`agents/builtins/llm/`** — LLM agents for OpenAI, Claude, Gemini
- **`agents/builtins/storage/`** — CSV/JSON/file reader/writer agents

### Services Layer

- **`services/config/`** — Configuration hierarchy: `app_config_service.py` (main config), `storage_config_service.py`, `llm_routing_config_service.py`, `llm_models_config_service.py`
- **`services/llm_service.py`** — LLM client creation and invocation
- **`services/routing/`** — Intelligent LLM routing
- **`services/storage/`** — Storage adapters (Firebase, Chroma, CSV, JSON)
- **`services/validation/`** — Workflow validation

### Entry Points

- **CLI**: `src/agentmap/cli.py` (Typer app, registered as `agentmap` console script)
- **HTTP**: `src/agentmap/deployment/http/` (FastAPI server)
- **Serverless**: `src/agentmap/deployment/serverless/`

### Configuration

Two config files created by `agentmap init-config`:
- `agentmap_config.yaml` — Main config (paths, LLM providers, memory, execution, routing, logging)
- `agentmap_config_storage.yaml` — Storage config (CSV, JSON, vector DBs, cloud storage)

Templates in `src/agentmap/templates/config/`.

## Test Structure

Tests are organized into three directories:
- **`tests/unit/`** — Unit tests mirroring `src/` structure
- **`tests/fresh_suite/`** — Newer test suite (also has `unit/` and `integration/` subdirs) with service-focused tests
- **`tests/integration/`** — Integration tests for workflows, suspend/resume, HTTP, etc.
- **`tests/utils/`** — Test utilities including `PathOperationsMocker` for mocking `pathlib.Path` operations (see `tests/PATH_MOCKING_GUIDE.md`)

## Configuration Change Checklist

When modifying `src/agentmap/services/config/app_config_service.py` or adding new `get_*_config()` / `get_value()` accessors:

1. **Update the template** — `src/agentmap/templates/config/agentmap_config.yaml.template`
2. **Update the root config** — keep `agentmap_config.yaml` in sync with the template
3. **Update template tests** — `tests/fresh_suite/unit/services/config/test_config_template_completeness.py`
4. **Update docs** — `docs-docusaurus/docs/reference/services/`

## Code Style

- Black formatter, line length 88
- isort with black profile
- flake8 for linting
- mypy for type checking (strict: `disallow_untyped_defs = true`)
