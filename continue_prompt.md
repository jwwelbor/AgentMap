---
timestamp: 2026-01-24T02:30:00Z
task: DI Container Performance Optimization - Phase 4 Bundle-Aware Injection Complete
branch: performance-phase3
status: Ready for Commit
---

# Resume: AgentMap Startup Performance Optimization

## Current Status

**Phases 1-4 COMPLETE** - All lazy loading + bundle-aware injection implemented and tested.

### Results Achieved
| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| CLI --help | 10-12s | 0.50s | 96% faster |
| Storage package import | 1.5s | 0.3s | 80% faster |
| graph_bundle_service | 1.8s | 1.1s | 39% faster |

All tests passing: 76 DI unit tests, 179 integration tests

---

## Phase 4: Bundle-Aware Injection (NEW)

### Changes Made

1. **CoreServiceConfigurator** (`src/agentmap/services/agent/core_service_configurator.py`)
   - Added `required_services: Optional[Set[str]]` parameter to `configure_core_services()`
   - Added `SERVICE_ATTR_TO_CANONICAL` mapping for service name matching
   - Filters specs to only check services declared in agent requirements

2. **StorageServiceConfigurator** (`src/agentmap/services/agent/storage_service_configurator.py`)
   - Added `required_services: Optional[Set[str]]` parameter to `configure_storage_services()`
   - Added `STORAGE_SERVICE_NAMES` set for early exit check
   - Early exit when no storage services are in required_services

3. **AgentServiceInjectionService** (`src/agentmap/services/agent/agent_service_injection_service.py`)
   - Updated `configure_all_services()` to accept and pass `required_services`
   - Updated `configure_core_services()` and `configure_storage_services()` signatures

4. **GraphAgentInstantiationService** (`src/agentmap/services/graph/graph_agent_instantiation_service.py`)
   - Added `declaration_registry_service: Optional[DeclarationRegistryService]` dependency
   - Added `_get_required_services_for_agent()` method to look up agent declarations
   - Updated `_inject_services()` to pass agent_type for optimization lookup

5. **DI Container**
   - `src/agentmap/di/container_parts/graph_agent.py` - Added declaration_registry_service dependency
   - `src/agentmap/di/containers.py` - Wired declaration_registry_service to GraphAgentContainer

### How It Works

```
GraphAgentInstantiationService._inject_services(agent, node_name, tracker, agent_type)
    ↓
_get_required_services_for_agent(agent_type)
    ↓ Uses DeclarationRegistryService
get_agent_declaration(agent_type) → AgentDeclaration.get_all_services()
    ↓ Returns set of declared services (e.g., {"llm", "storage"})
AgentServiceInjectionService.configure_all_services(agent, tracker, required_services)
    ↓
CoreServiceConfigurator - only checks specs in required_services
StorageServiceConfigurator - early exit if no storage services needed
```

---

## Uncommitted Changes

### Phase 3 (Previous commit 8c44704)
- Already committed: `DeclarationRegistryService.load_for_bundle()` integration

### Phase 4 (This session - UNCOMMITTED)
- `src/agentmap/services/agent/core_service_configurator.py`
- `src/agentmap/services/agent/storage_service_configurator.py`
- `src/agentmap/services/agent/agent_service_injection_service.py`
- `src/agentmap/services/graph/graph_agent_instantiation_service.py`
- `src/agentmap/di/container_parts/graph_agent.py`
- `src/agentmap/di/containers.py`

---

## Quick Verification Commands

```bash
# Performance checks
time uv run agentmap --help

# Run tests
uv run pytest tests/fresh_suite/unit/di/ tests/unit/test_di_services_instantiation.py -v
uv run pytest tests/fresh_suite/integration/ -v -k "not blob"
```

---

## Commit Message (Ready to commit)

```
perf: Bundle-aware service injection optimization

Phase 4: Bundle-aware injection
- CoreServiceConfigurator filters specs by required_services
- StorageServiceConfigurator early exit when no storage needed
- AgentServiceInjectionService passes required_services to configurators
- GraphAgentInstantiationService uses DeclarationRegistryService to
  look up agent's declared service requirements
- DI container wired with declaration_registry_service

This reduces isinstance() calls and service lookups by only checking
services that the agent actually declares as requirements.

All 76 DI unit tests and 179 integration tests passing.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```

---

## Next Steps (Optional)

1. **Commit and push** the Phase 4 changes
2. **Create PR** for performance-phase3 branch
3. **Measure actual improvement** with profiling on a real workflow
4. **Clean up** dev-artifacts directories
