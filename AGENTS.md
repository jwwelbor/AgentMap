# Repository Guidelines

## Project Structure & Module Organization
AgentMap follows a clean architecture split: `src/agentmap/models` stays data-only, `services/` contains business logic, `di/` wires dependencies, and `agents/` holds runtime implementations. CLI entry points (`cli.py`, `server_cli.py`) sit beside deployment helpers in `src/agentmap/deployment` and `deployment_scripts/`. Shared configs live in the repo root (`agentmap_config.yaml`, `agentmap_local_config.yaml`), while documentation sources are under `docs-docusaurus/docs`. Tests mirror runtime layers in `tests/unit`, `tests/integration`, and `tests/e2e`.

## Build, Test, and Development Commands
Install toolchains with `poetry install --with dev`. Execute workflows locally via `poetry run agentmap run --csv workflows.csv`, or launch the FastAPI host using `poetry run agentmap-server`. Run checks with `poetry run pytest` (coverage reports enabled by default) and `poetry run mypy src`. Format code through `poetry run black src tests` followed by `poetry run isort src tests`.

## Coding Style & Naming Conventions
Stick to Black (88 chars, 4-space indent) and the matching isort profile. Modules are snake_case (`graph_runner_service.py`), classes PascalCase, methods snake_case, and constants UPPER_SNAKE_CASE. Services should depend on protocol types defined in `src/agentmap/services/protocols.py`, injected via constructors only. Keep public APIs fully typed and avoid files over ~350 lines or methods over 50 lines.

## Testing Guidelines
Pytest powers the suite; name files `test_*.py`, classes `Test*`, and functions `test_*`. Unit tests should mock dependencies (see `tests/utils/MockServiceFactory`), while integration tests use the real DI container. Maintain ≥80% overall coverage and inspect `htmlcov/index.html` when `poetry run pytest` flags gaps. Add regression tests when altering agents, DI wiring, or service contracts.

## Commit & Pull Request Guidelines
Use `type(scope): summary` commit messages (e.g., `feat(services): add graph replay support`). PRs need clear descriptions, linked issues when available, passing checks, and documentation updates referencing `claude_documentation.md` for tone and structure. Include config migrations or CLI output screenshots when behavior changes and request at least one review before merge.

## Documentation & Workspace Tips
Create temporary investigation artifacts under `dev-artifacts/YYYY-MM-DD-task-name/` with subfolders for analysis, scripts, and verification; remove them once merged unless still valuable. Keep secrets out of source control—copy `agentmap_local_config.yaml` for local overrides and load credentials through environment variables. Review `claude.md` when planning architecture changes to stay aligned with DRY, SOLID, and YAGNI.
