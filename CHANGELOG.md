# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - Unreleased

AgentMap 1.0.0 establishes the stable compatibility contract. It supports Python 3.12 and later, below Python 4.0. Python 3.11 is no longer supported; upgrade to Python 3.12 or later before installing or upgrading AgentMap.

### Added
- Async runtime APIs and provider-agnostic batch LLM execution.
- Token streaming, graph progress streaming, and server-sent events (SSE).
- Provider-independent prompt caching, cost receipts, and structured tool results.
- Opt-in daily LLM attempt logs, including retries and fallbacks.
- Safe receipts for successful provider responses without text blocks.

### Changed
- **Breaking:** Require Python 3.12 or later. Python 3.11 environments cannot install AgentMap 1.0.0.
- Provider exclusions now apply through model selection, configured and emergency fallback, retries, caches, streaming, and routing-error recovery.

### Fixed
- Preserve safe response and usage metadata when a provider returns a successful non-text response.
- Preserve explicitly excluded providers across fallback and routing recovery paths.

## Selected history from 0.9.x

These entries summarize product milestones from the published GitHub releases. Routine maintenance and dependency-only releases are omitted.

### [0.9.213] - 2026-10-09
- Govern physical LLM attempts with admission and completion callbacks, durable response evidence, and complete attempt accounting.
- Preserve runtime and HTTP lifecycle cleanup through cancellation, scheduling, cache publication, refresh, and shutdown.

### [0.9.212] - 2026-09-11
- Preserve safe receipts for successful provider responses that contain no text blocks.

### [0.9.211] - 2026-08-08
- Add token streaming, graph progress streaming, and server-sent events (SSE).
- Add LLM cost receipts and structured tool results; expose the async runtime API at the package root.
- Fix GraphAgent input and output remapping for nested workflows.

### [0.9.210] - 2026-06-13
- Add async runtime and graph execution APIs, including asynchronous CLI entry points.
- Add provider prompt caching and failover-safe routing; replace Chroma storage with FAISS.
- Add asynchronous vision requests and preserve provider finish reasons.

### [0.9.209] - 2026-06-01
- Add asynchronous multi-call fan-out for LLM requests.
- Preserve temperature and model parameters through routed LLM calls.

### [0.9.208] - 2026-04-09
- Add multimodal vision support and allow tool sources to load modules from a directory.
- Fix workflow resumption after human interaction uses the fallback path.

### [0.9.207] - 2026-03-22
- Add input-field mapping with three binding modes and max-token support for LLM routing.
- Add OpenTelemetry instrumentation for agent, workflow, and LLM execution, with Grafana dashboard templates.

### [0.9.203] - 2026-02-28
- Add LLM retries and circuit-breaker resilience.
- Add YAML-backed host service declarations.

### [0.9.201] - 2026-02-23
- Improve GraphAgent support for dynamic workflows and CSV subgraph declarations.

### [0.9.200] - 2026-01-27
- Add multiple-output support for agents and CSV workflows.
- Refactor service modules and add lazy imports to improve maintainability and startup time.

## [0.3.0] - 2025-05-27

### Changed
- **BREAKING**: Migrated from setuptools to Poetry for modern Python packaging
- Updated build system to use Poetry for better dependency management
- Improved GitHub Actions workflows with proper Poetry integration and caching
- Enhanced pyproject.toml with comprehensive project metadata and classifiers
- Added development dependencies (black, isort, flake8, pytest-cov) for code quality

### Added
- Added code formatting and linting tools configuration
- Enhanced CI pipeline with multi-Python version testing (3.11, 3.12)
- Added coverage reporting to CI pipeline
- Improved package classifiers for better PyPI discoverability

### Fixed
- Fixed version consistency across all project files
- Cleaned up old build artifacts from setuptools era
- Fixed optional dependencies configuration for better `pip install agentmap[llm]` experience

### Technical
- Replaced `setuptools.build_meta` with `poetry.core.masonry.api`
- Updated GitHub workflows to use modern actions (v4)
- Added proper dependency caching for faster CI builds
- Enhanced project metadata for PyPI presentation

## [0.2.0] - Previous Release

### Added
- Initial setuptools-based release
- Core AgentMap functionality
- CSV-driven workflow definitions
- LLM integrations (OpenAI, Claude, Gemini)
- Storage backends (local, cloud, vector databases)
- CLI interface with scaffolding capabilities

## [0.1.0] - Initial Release

- Initial release with the first version of the code
