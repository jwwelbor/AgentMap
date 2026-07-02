# AgentMap Workspace Notes

Use [claude.md](/home/jwwel/projects/agentmap/claude.md) as the primary repository guidance. This file only captures repo-local overrides and high-signal reminders.

## Tooling

- Use `uv`, not `poetry`.
- Sync dependencies with `uv sync --dev`.
- Run the CLI with `uv run agentmap run --csv workflows.csv`.
- Start the server with `uv run agentmap-server`.
- Run tests with `uv run pytest`.
- Run type checks with `uv run mypy src`.
- Format with `uv run black src tests` and `uv run isort src tests`.

## Project Structure

- Runtime code lives under `src/agentmap/`.
- Keep `src/agentmap/models` data-only.
- Put business logic in `src/agentmap/services`.
- Keep dependency wiring in `src/agentmap/di`.
- Agent implementations live in `src/agentmap/agents`.
- Documentation sources live in `docs-docusaurus/docs`.
- Tests are organized under `tests/unit`, `tests/integration`, and `tests/e2e`.

## Testing

- Use `test_*.py` filenames, `Test*` classes, and `test_*` functions.
- Unit tests should prefer mocks and `tests/utils/MockServiceFactory`.
- Integration tests should use the real DI container.
- Add regression coverage for agent behavior, DI wiring, and service contracts when those change.

## Documentation And Workflow Notes

- Slash-prefixed forms like `/shark deep-review high` are skill invocations, not shell commands.
- Shell commands should be written without the leading slash, for example `shark get b003`.
- Create temporary investigation artifacts under `dev-artifacts/YYYY-MM-DD-task-name/`.
- Keep secrets out of source control; use local config overrides and environment variables.
