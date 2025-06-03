# AgentMap Graph Refactor & Migration Tracker

This document tracks the migration of core graph-building and execution logic from legacy files into service-oriented components aligned with AgentMap architecture.

---

## ✅ Completed Migrations

| Legacy Component       | New Service/Class               | Notes |
|------------------------|----------------------------------|-------|
| `compiler.py`          | `compilation_service.py`        | Fully service-ified with DI, supports registry injection |
| `runner.py`            | `graph_runner_service.py`       | Execution pipeline now modular and DI-driven |
| `GraphAssembler`       | Reused in new services          | Works with injected node registry |

---

## 🧠 Migrating / In Progress

| Legacy Function                 | Proposed New Location           | Notes |
|--------------------------------|----------------------------------|-------|
| `build_source_lines`           | `SourceGeneratorService`        | Generates `.src` file, currently still in compiler |
| `resolve_agent_class`          | `AgentResolverService`          | Handles fallback, LLM checks, custom loading |
| `add_dynamic_routing`          | `DynamicEdgeService` or assembler | Orchestrator edge routing by `__next_node` |
| `create_serializable_result`   | `ResultSerializer` or utils     | Converts result to JSON-compatible output |
| `GraphBuilder` logic reuse     | `GraphDefinitionService`        | Centralized CSV → dict loading logic |
| Execution deduplication guard  | `ExecutionGuardService`         | Prevents re-entry loops on run_graph |

---

## 🆕 Proposed New Services

| Service Name             | Purpose |
|--------------------------|---------|
| `AgentFactoryService`    | Creates fully-initialized agent instances with LLM/storage/etc. |
| `AgentResolverService`   | Handles type → class resolution with fallback to custom agent |
| `SourceGeneratorService` | Produces readable `.src` build output from graph_def |
| `ExecutionGuardService`  | Prevents recursive or concurrent execution of same graph params |
| `GraphDefinitionService` | Loads and resolves graph_def from CSV or cache |
| `ResultSerializer`       | Converts result dict to safe JSON-compatible version |
| `DynamicEdgeService`     | Optionally splits dynamic routing logic for orchestrators |

---

## 📋 Additional TODOs

- [ ] Extract `build_source_lines` into `SourceGeneratorService`
- [ ] Extract and test `resolve_agent_class` into `AgentResolverService`
- [ ] Move dynamic routing to standalone logic
- [ ] Add unit tests for `compile_graph`, `run_graph`, and registry injection
- [ ] Consider removing legacy methods like `create_graph_builder`

---

## 📁 Folder Mapping

| Folder             | Purpose |
|--------------------|---------|
| `services/`        | Core logic modules (runner, compiler, etc.) |
| `models/`          | Data-only objects like NodeDefinition, GraphDefinition |
| `graph/`           | Assembly + compatibility layers |
| `functions/`       | Custom edge functions invoked dynamically |
| `agents/`          | Built-in + user-defined agent types |
| `di/`              | Dependency injection config |

---

## 🧱 Scaffold System Migration

| Legacy Component | Proposed New Location     | Notes |
|------------------|---------------------------|-------|
| `scaffold.py`    | `GraphScaffoldService`    | Service handles graph/agent/function scaffolds |
| Templates        | `templates/` or embedded  | Store .tpl/.txt scaffold templates here |
| CLI support      | `cli/commands/scaffold.py`| Add argparse or Typer CLI commands |

---
class GraphScaffoldService:
    def scaffold_graph_csv(self, name: str) -> Path:
        """Create a starter CSV for a new graph."""
        ...

    def scaffold_agent_class(self, name: str) -> Path:
        """Create a starter agent class in user-defined directory."""
        ...

    def scaffold_edge_function(self, name: str) -> Path:
        """Scaffold a Python function for dynamic edge routing."""
        ...

### Suggested Service Methods

- `scaffold_graph_csv(name: str) -> Path`
- `scaffold_agent_class(name: str) -> Path`
- `scaffold_edge_function(name: str) -> Path`

