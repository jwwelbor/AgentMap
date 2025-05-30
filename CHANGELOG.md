# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
