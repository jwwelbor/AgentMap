# API Infrastructure Organization

This directory contains all API infrastructure implementations following clean architecture principles.

## Directory Structure

### `/adapters/`
Framework-agnostic adapter interfaces that bridge core business logic with specific API frameworks.
These adapters implement the ports defined in the core layer.

### `/fastapi/`
FastAPI-specific implementation containing:
- **`/routes/`** - FastAPI route definitions (thin controllers)
- **`/middleware/`** - FastAPI middleware (auth, error handling, etc.)

## Architecture Principles

1. **Framework Independence**: Core business logic has no knowledge of FastAPI
2. **Dependency Inversion**: Infrastructure depends on core, not vice versa
3. **Single Responsibility**: Each module has one clear purpose
4. **Interface Segregation**: Adapters provide only necessary methods

## Migration Status

This structure is part of the clean architecture migration from `/core/api/`.
Routes and middleware are being moved here to achieve proper separation of concerns.
